"""Agent layer on student B's backend, with B's synthetic source and a scripted fake model."""

import json
import re
from secrets import token_urlsafe
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agent.chat import AgentConfig
from agent.main import create_app
from student_b.main import Settings
from student_b.tests.synthetic import SyntheticSource

ROUTE = "groq/openai/test-model"


class FakeModel:
    """Scripted stand-in for the OpenAI-compatible client; records what the model was sent."""

    def __init__(self, *script, route=ROUTE):
        self.script, self.seen, self.route = list(script), [], route
        self.chat = SimpleNamespace(completions=SimpleNamespace(with_raw_response=SimpleNamespace(create=self.create)))

    async def create(self, model, messages, tools, extra_body=None):
        self.seen.append(messages)
        step = self.script.pop(0)
        if isinstance(step, str):
            message = SimpleNamespace(content=step, tool_calls=None)
        else:
            name, args = step
            message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(
                id=f"call{len(self.seen)}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))])
        return SimpleNamespace(headers={"x-routed-via": self.route},
                               parse=lambda: SimpleNamespace(choices=[SimpleNamespace(message=message)]))


def make(model, monkeypatch, **config):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    key = token_urlsafe(32)
    defaults = dict(models=("test-model",), expected_routes=frozenset({ROUTE}), allow_real_data=True, rate_limit_waits=())
    app = create_app(Settings(api_key=key, requests_per_minute=1000), SyntheticSource(),
                     AgentConfig(**{**defaults, **config}), model)
    return TestClient(app, raise_server_exceptions=False), {"X-API-Key": key}


def say(client, headers, text, conversation=None):
    response = client.post("/api/v1/chat", json={"message": text, "conversation_id": conversation}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_full_journey_one_model_call_per_turn(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "synthetic-station"}), ("get_evidence", {"evidence_id": "2"}),
                      ("record_answer", {"answer_text": "Yes, the fixture was re-clamped."}), ("get_handover", {}),
                      "I can't advise on replacement; I can show the data or the handover.")
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "Investigate SYNTHETIC-STATION")
        conv, case_id = first["data"]["conversation_id"], first["case_id"]
        reply = first["data"]["reply"]
        assert re.fullmatch(r"[0-9a-f]{32}", case_id) and f"`{case_id}`" in reply
        # breach first, then the in-range coded row, then the not evaluable row; values as returned
        rows = [line for line in reply.splitlines() if line.startswith("| SYNTHETIC")]
        assert [r.split("|")[1].strip() for r in rows] == ["SYNTHETIC Torque", "SYNTHETIC Count", "SYNTHETIC Invalid"]
        assert "| 10.5 Nm | 8.0..10.0 | ABOVE | 0.5 | none |" in rows[0]
        assert "| SYNTHETIC-SERIAL | 2026-01-01 10:00:00 |" in rows[0]
        assert "| WITHIN_RECORDED_BOUNDS | 0 | 1001 |" in rows[1]
        assert "SYNTHETIC Count is listed because a fail code is recorded" in reply
        assert "UNDETERMINED" in reply and "**Question for you:**" in reply
        assert first["data"]["open_question"] is True
        assert first["data"]["tool_calls"][0]["name"] == "open_case" and first["data"]["model"] == ROUTE

        evidence = say(client, headers, "Where does 0.5 come from?", conv)["data"]["reply"]
        assert f"`E-{case_id}-2` **(CALCULATED)**" in evidence and "deviation **0.5**" in evidence
        assert "raw value `10.5` Nm" in evidence  # input observation resolved from the case

        answered = say(client, headers, "Yes, the fixture was re-clamped.", conv)["data"]
        assert "Recorded your answer as technician report" in answered["reply"]
        assert "not independently verified" in answered["reply"] and "UNDETERMINED" in answered["reply"]
        assert answered["open_question"] is False

        handover = say(client, headers, "Handover please", conv)["data"]["reply"]
        assert "MAGNA TRACE handover" in handover and "Yes, the fixture was re-clamped." in handover
        assert "No approved maintenance procedure was consulted" in handover

        refusal = say(client, headers, "Which part should I replace?", conv)["data"]
        assert refusal["tool_calls"] == [] and "can't advise" in refusal["reply"]
        assert len(model.seen) == 5  # exactly one model call per technician turn
        # the model gets a compact result (IDs, status, value, deviation), not the full rows
        sent = json.dumps(model.seen[-1])
        assert "SYNTHETIC-SERIAL" not in sent and "2026-01-01" not in sent and "8.0" not in sent


def test_extra_tool_arguments_are_ignored(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "SYNTHETIC-STATION", "case_id": "x"}),
                      ("get_handover", {"case_id": "whatever", "format": "short"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        conv = say(client, headers, "open")["data"]["conversation_id"]
        assert "MAGNA TRACE handover" in say(client, headers, "handover", conv)["data"]["reply"]


def test_answer_without_open_question_and_evidence_errors(monkeypatch):
    model = FakeModel(("record_answer", {"answer_text": "yes"}), ("get_evidence", {"evidence_id": "1"}),
                      ("open_case", {"station_number": "SYNTHETIC-STATION"}), ("get_evidence", {"evidence_id": "999"}),
                      ("get_evidence", {"evidence_id": "E-" + "0" * 32 + "-1"}), ("open_case", {"station_number": "NOPE"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "yes")
        conv = first["data"]["conversation_id"]
        assert "no open question" in first["data"]["reply"]
        assert "no active case" in say(client, headers, "source?", conv)["data"]["reply"]
        say(client, headers, "open", conv)
        assert "**EVIDENCE_NOT_FOUND.**" in say(client, headers, "source of 999", conv)["data"]["reply"]
        assert "**EVIDENCE_NOT_IN_CASE.**" in say(client, headers, "foreign", conv)["data"]["reply"]
        no_data = say(client, headers, "station NOPE", conv)["data"]
        assert "**NO_DATA.**" in no_data["reply"] and "does not mean the station is healthy" in no_data["reply"]
        assert no_data["tool_calls"][0]["code"] == "NO_DATA"


def test_guards(monkeypatch):
    blocked = FakeModel(("open_case", {"station_number": "SYNTHETIC-STATION"}))
    with make(blocked, monkeypatch, allow_real_data=False)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        data = say(client, headers, "investigate")
        assert "has not been approved" in data["data"]["reply"] and data["case_id"] is None

    wrong_route = FakeModel("hello", route="other/unapproved-model")
    with make(wrong_route, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        data = say(client, headers, "hi")["data"]
        assert data["model"] is None and "not available right now" in data["reply"]

    with make(FakeModel(), monkeypatch)[0] as client:
        assert client.post("/api/v1/chat", json={"message": "hi"}).status_code == 401
        assert client.post("/mcp", json={}).status_code == 401
        headers = {"X-API-Key": client.app.state.settings.api_key}
        assert client.post("/api/v1/chat", json={"message": ""}, headers=headers).status_code == 422

    with make(FakeModel(), monkeypatch, models=())[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        response = client.post("/api/v1/chat", json={"message": "hi"}, headers=headers)
        assert response.status_code == 503 and response.json()["error"]["code"] == "SOURCE_UNAVAILABLE"


def test_backend_contract_routes_still_work(monkeypatch):
    with make(FakeModel(), monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        assert client.get("/healthz").status_code == 200
        stations = client.get("/api/v1/stations", headers=headers).json()
        assert stations["case_id"] is None and stations["data"]["stations"][0]["station_number"] == "SYNTHETIC-STATION"


def test_mcp_lists_the_five_tools(monkeypatch):
    with make(FakeModel(), monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key, "Accept": "application/json, text/event-stream"}
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}
        assert client.post("/mcp", json=init, headers=headers).status_code == 200
        listed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers).json()
        assert {t["name"] for t in listed["result"]["tools"]} == {
            "open_case", "get_evidence", "record_answer", "get_handover", "list_stations"}
        called = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "open_case", "arguments": {"station_number": "SYNTHETIC-STATION"}}}, headers=headers).json()
        body = json.loads(called["result"]["content"][0]["text"])
        assert body["status"] == "ok" and "SYNTHETIC Torque" in body["message"] and body["question_id"]
