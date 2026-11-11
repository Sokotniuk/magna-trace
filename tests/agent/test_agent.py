"""Agent layer on student B's backend, with B's synthetic source and a scripted fake model."""

import json
import re
from secrets import token_urlsafe
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agent.auth import Auth, Directory, Employee, hash_password
from agent.chat import AgentConfig
from agent.main import create_app
from backend.app.main import Settings
from tests.api.synthetic import SyntheticSource

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
                     AgentConfig(**{**defaults, **config}), model, auth=synthetic_auth())
    client = TestClient(app, raise_server_exceptions=False)
    # The dashboard signs in first (D34); the client keeps the session cookie.
    signed_in = client.post("/api/v1/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD},
                            headers={"X-API-Key": key})
    assert signed_in.status_code == 200, signed_in.text
    return client, {"X-API-Key": key}


TEST_USER, TEST_PASSWORD = "synthetic.tech", token_urlsafe(12)


def synthetic_auth() -> Auth:
    salt = bytes(16)
    employee = Employee("SYN-0001", TEST_USER, "Synthetic Technician", "Test technician", "A",
                        salt.hex(), hash_password(TEST_PASSWORD, salt))
    return Auth(Directory("Synthetic Company", [employee]))


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
        assert "| 10.5 Nm | 8.0 – 10.0 | ABOVE | 0.5 | none | SYNTHETIC-SERIAL |" in rows[0]
        assert "| SYNTHETIC-SERIAL | 2026-01-01 10:00:00 |" in rows[0]  # identifiers after the decisive columns
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
        # the answer is attributed to the signed-in employee, not to an anonymous connector (D34)
        assert "— Synthetic Technician (SYN-0001), Test technician, shift A — demo sign-in, reported" in handover
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


def test_evidence_by_measurement_name_of_a_shown_finding(monkeypatch):
    # Demo question "where does the X deviation come from?": the model names the measurement.
    model = FakeModel(("open_case", {"station_number": "synthetic-station"}),
                      ("get_evidence", {"measurement": "synthetic  TORQUE"}),
                      ("get_evidence", {"measurement": "SYNTHETIC Torque", "kind": "observation"}),
                      ("get_evidence", {"measurement": "Invented Pressure"}),
                      ("get_evidence", {}),
                      ("get_evidence", {"calculation_id": "2"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "open")
        conv, case_id = first["data"]["conversation_id"], first["case_id"]
        calculated = say(client, headers, "where does the torque deviation come from?", conv)["data"]["reply"]
        assert f"`E-{case_id}-2` **(CALCULATED)**" in calculated and "deviation **0.5**" in calculated
        observed = say(client, headers, "raw torque row", conv)["data"]["reply"]
        assert f"`E-{case_id}-1` **(OBSERVED)**" in observed and "`8.0` – `10.0`" in observed
        missing = say(client, headers, "pressure?", conv)["data"]
        assert "is not among the findings shown for this case" in missing["reply"]
        assert missing["tool_calls"][0]["code"] == "EVIDENCE_NOT_FOUND"
        empty = say(client, headers, "source?", conv)["data"]
        assert empty["tool_calls"][0]["code"] == "BAD_ARGUMENTS"
        alias = say(client, headers, "deviation source", conv)["data"]["reply"]
        assert f"`E-{case_id}-2` **(CALCULATED)**" in alias


def test_evidence_id_copied_from_the_dashboard_continues_that_case(monkeypatch):
    # D38: a technician pastes a full evidence ID from the dashboard into a fresh chat.
    with make(FakeModel(), monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        opened = client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers).json()
        case_id, calc = opened["case_id"], opened["data"]["findings"][0]["calculation_evidence_id"]
        model = FakeModel(("record_answer", {"answer_text": "ignored model text"}))
        client.app.state.agent._client = model
        first = say(client, headers, f"Where does {calc} come from?")
        assert f"Continuing with case `{case_id}` from the dashboard." in first["data"]["reply"]
        assert f"`{calc}` **(CALCULATED)**" in first["data"]["reply"] and first["case_id"] == case_id
        assert first["data"]["open_question"] is True  # the dashboard case's question is now open in chat
        assert model.seen == [] and first["data"]["model"] is None  # answered without asking the model
        answered = say(client, headers, "No change on the fixture.", first["data"]["conversation_id"])["data"]
        assert "Recorded your answer as technician report" in answered["reply"]


def test_pasted_dashboard_id_selects_the_case_even_if_the_model_names_the_measurement(monkeypatch):
    with make(FakeModel(), monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        opened = client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers).json()
        case_id, calc = opened["case_id"], opened["data"]["findings"][0]["calculation_evidence_id"]
        # The model would open another station (seen in rehearsal); a pasted ID never reaches it.
        client.app.state.agent._client = FakeModel(("open_case", {"station_number": "ST3003"}))
        reply = say(client, headers, f"{calc} — where does this deviation come from?")["data"]["reply"]
        assert reply.startswith(f"Continuing with case `{case_id}` from the dashboard.")
        assert f"`{calc}` **(CALCULATED)**" in reply
        # an ID of a case that does not exist selects nothing
        client.app.state.agent._client = FakeModel(("get_evidence", {"measurement": "SYNTHETIC Torque"}))
        other = say(client, headers, "E-" + "a" * 32 + "-3 where from?")["data"]["reply"]
        assert "Continuing with case" not in other and "no active case" in other
