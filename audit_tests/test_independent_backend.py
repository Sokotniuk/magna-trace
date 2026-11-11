"""Independent audit: synthetic source/driver/model only; no external services."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agent.tests.test_agent import FakeModel, make, say
from agent.tools import Session
from backend.app import oracle_repo as repo
from student_b.main import Settings, create_app
from student_b.source import OracleCredentials, OracleSource
from student_b.tests.synthetic import SyntheticSource


def test_untrusted_model_prose_is_not_a_fact_channel(monkeypatch):
    fabricated = "AUDIT_UNSUPPORTED_DIAGNOSIS: EQUIPMENT_LIKELY; value 999.999, E-invented-1"
    with make(FakeModel(fabricated), monkeypatch)[0] as client:
        result = say(client, {"X-API-Key": client.app.state.settings.api_key}, "Investigate")
        assert fabricated not in result["data"]["reply"]
        assert "EQUIPMENT_LIKELY" not in result["data"]["reply"]


def test_failed_case_switch_cannot_answer_old_case(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "SYNTHETIC-STATION"}),
                      ("open_case", {"station_number": "MISSING"}),
                      ("record_answer", {"answer_text": "yes"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "open")
        conv = first["data"]["conversation_id"]
        failed = say(client, headers, "investigate MISSING", conv)
        assert failed["case_id"] is None
        say(client, headers, "yes", conv)
        with client.app.state.cases.locked(first["case_id"]) as original:
            assert original.snapshot.technician_reports == ()


def test_report_uses_actual_technician_text(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "SYNTHETIC-STATION"}),
                      ("record_answer", {"answer_text": "invented affirmative answer"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "open")
        actual = "No, I did not observe a change."
        say(client, headers, actual, first["data"]["conversation_id"])
        with client.app.state.cases.locked(first["case_id"]) as case:
            assert case.snapshot.technician_reports[0].answer_text == actual


def test_missing_provider_route_fails_closed(monkeypatch):
    with make(FakeModel("hello", route=""), monkeypatch)[0] as client:
        result = say(client, {"X-API-Key": client.app.state.settings.api_key}, "hi")
        assert result["data"]["model"] is None


def test_invented_evidence_suffix_not_repaired(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "SYNTHETIC-STATION"}),
                      ("get_evidence", {"evidence_id": "untrusted-invented-reference-2"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "open")
        result = say(client, headers, "source", first["data"]["conversation_id"])
        assert result["data"]["tool_calls"][0]["status"] == "error"


class MalformedModel(FakeModel):
    async def create(self, **kwargs):
        return SimpleNamespace(headers={"x-routed-via": self.route}, parse=lambda: SimpleNamespace(choices=[]))


def test_malformed_provider_does_not_pollute_history(monkeypatch):
    with make(MalformedModel(), monkeypatch)[0] as client:
        result = say(client, {"X-API-Key": client.app.state.settings.api_key}, "hi")
        assert result["data"]["model"] is None
        assert next(iter(client.app.state.agent._conversations.values())).messages == []


def test_conversation_history_storage_is_bounded(monkeypatch):
    model = FakeModel(*(["hello"] * 12))
    with make(model, monkeypatch, max_history=4)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "hi")
        conv = first["data"]["conversation_id"]
        for _ in range(10):
            say(client, headers, "hi", conv)
        assert len(client.app.state.agent._conversations[conv].messages) <= 4


@pytest.mark.parametrize("path,method,body", [
    ("/api/v1/cases", "POST", {"station_number": "SYNTHETIC-STATION"}),
    ("/api/v1/stations", "GET", None),
    ("/api/v1/cases/unknown/handover", "GET", None),
    ("/api/v1/cases/unknown/evidence/unknown", "GET", None),
    ("/api/v1/cases/unknown/answers", "POST", {"question_id": "q", "answer_text": "a"}),
    ("/api/v1/chat", "POST", {"message": "hi"}), ("/mcp", "POST", {}),
])
def test_authentication_all_active_surfaces(monkeypatch, path, method, body):
    with make(FakeModel(), monkeypatch)[0] as client:
        for headers in ({}, {"X-API-Key": "invalid"}):
            response = client.request(method, path, json=body, headers=headers)
            assert response.status_code == 401
            assert response.json()["data"] is None


def test_actual_a2_a3_b_lifecycle_exact_precision_and_concurrency(monkeypatch):
    stamp = "2026-01-01T10:00:00.123456"
    row = ("SYNTH", "SERIAL", "precision", "123456789012345678901234567890.0100", "0", "0.0001",
           "mm", Decimal("1001"), stamp, "P", "W", Decimal(1), None, "synthetic-rowid", 1, stamp, stamp, 0)
    monkeypatch.setattr(repo, "_select_rows", lambda *a, **k: [row])
    key = "audit-synthetic-key-" * 3
    source = OracleSource(OracleCredentials("synthetic", "synthetic-only", "localhost/TESTPDB"))
    with TestClient(create_app(Settings(api_key=key), source)) as client:
        headers = {"X-API-Key": key}
        first = client.post("/api/v1/cases", json={"station_number": "SYNTH"}, headers=headers).json()
        second = client.post("/api/v1/cases", json={"station_number": "SYNTH"}, headers=headers).json()
        case_id, finding = first["case_id"], first["data"]["findings"][0]
        assert finding["deviation"] == "123456789012345678901234567890.0099"
        assert finding["raw_fail_code"] == "1001"
        path = f"/api/v1/cases/{case_id}/evidence/{finding['evidence_id']}"
        before = client.get(path, headers=headers).json()["data"]
        assert before["raw_fields"]["BOOK_STAMP"] == stamp
        answer = {"question_id": first["data"]["next_action"]["question_id"], "answer_text": "unchanged"}
        def submit():
            return client.post(f"/api/v1/cases/{case_id}/answers", json=answer, headers=headers).status_code
        with ThreadPoolExecutor(2) as pool:
            assert sorted(pool.map(lambda _: submit(), range(2))) == [200, 409]
        assert client.get(path, headers=headers).json()["data"] == before
        assert client.get(f"/api/v1/cases/{second['case_id']}/handover", headers=headers).json()["data"]["technician_reports"] == []
        foreign = client.get(f"/api/v1/cases/{second['case_id']}/evidence/{finding['evidence_id']}", headers=headers)
        assert foreign.json()["error"]["code"] == "EVIDENCE_NOT_IN_CASE"
        assert client.get(f"/api/v1/cases/{case_id}/handover", headers=headers).json()["data"]["assessment"]["label"] == "UNDETERMINED"


@pytest.mark.parametrize("error,code,status", [
    (repo.OracleTimeoutError("synthetic-private-detail"), "TIMEOUT", 504),
    (repo.SourceUnavailableError("synthetic-private-detail"), "SOURCE_UNAVAILABLE", 503),
    (repo.InvalidScopeError("synthetic-private-detail"), "INVALID_SCOPE", 422),
])
def test_fault_injection_actual_adapter_to_http(monkeypatch, error, code, status):
    def fail(*a, **k):
        raise error
    monkeypatch.setattr(repo, "read_measurements", fail)
    key = "audit-synthetic-key-" * 3
    with TestClient(create_app(Settings(api_key=key), OracleSource(OracleCredentials("synthetic", "synthetic-only", "localhost/TESTPDB")))) as client:
        response = client.post("/api/v1/cases", json={"station_number": "SYNTH"}, headers={"X-API-Key": key})
        assert response.status_code == status
        assert response.json()["error"]["code"] == code and response.json()["data"] is None
        assert "synthetic-private-detail" not in response.text


def test_expired_case_does_not_retain_agent_context(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "SYNTHETIC-STATION"}), ("get_handover", {}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "open")
        with client.app.state.cases.locked(first["case_id"]) as case:
            case.expires_at = 0
        result = say(client, headers, "summary", first["data"]["conversation_id"])
        assert result["case_id"] is None and result["data"]["open_question"] is False


def test_partial_answer_failure_does_not_publish_report(monkeypatch):
    from student_b import diagnostics
    key = "audit-synthetic-key-" * 3
    with TestClient(create_app(Settings(api_key=key), SyntheticSource()), raise_server_exceptions=False) as client:
        headers = {"X-API-Key": key}
        first = client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers).json()
        with client.app.state.cases.locked(first["case_id"]) as case:
            original = dict(case.evidence._items)
        def fail(*a, **k):
            raise RuntimeError("synthetic private failure")
        monkeypatch.setattr(diagnostics, "record_report", fail)
        response = client.post(f"/api/v1/cases/{first['case_id']}/answers", headers=headers,
            json={"question_id": first["data"]["next_action"]["question_id"], "answer_text": "hello"})
        assert response.status_code == 500 and "private" not in response.text
        with client.app.state.cases.locked(first["case_id"]) as case:
            assert case.evidence._items == original
            assert case.state == "AWAITING_CLARIFICATION"


def test_chat_rate_limit_before_model_call(monkeypatch):
    with make(FakeModel("hello", "hello"), monkeypatch)[0] as client:
        from dataclasses import replace
        # Construct a fresh app with a one-request configured budget.
        from agent.main import create_app as integrated
        original = client.app
        app = integrated(replace(original.state.settings, requests_per_minute=1), SyntheticSource(),
                         original.state.agent.config, FakeModel("hello", "hello"), auth=original.state.auth)
        with TestClient(app) as limited:
            limited.cookies.update(client.cookies)
            headers = {"X-API-Key": app.state.settings.api_key}
            assert limited.post("/api/v1/chat", json={"message": "hi"}, headers=headers).status_code == 200
            assert limited.post("/api/v1/chat", json={"message": "hi"}, headers=headers).status_code == 429


def test_mcp_actual_case_answer_handover_and_foreign_evidence(monkeypatch):
    with make(FakeModel(), monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key, "Accept": "application/json, text/event-stream"}
        def call(name, **arguments):
            response = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1,
                "method": "tools/call", "params": {"name": name, "arguments": arguments}})
            assert response.status_code == 200
            return json.loads(response.json()["result"]["content"][0]["text"])
        one = call("open_case", station_number="SYNTHETIC-STATION")
        two = call("open_case", station_number="SYNTHETIC-STATION")
        eid = one["findings"][0]["evidence_id"]
        assert call("get_evidence", case_id=two["case_id"], evidence_id=eid)["code"] == "EVIDENCE_NOT_IN_CASE"
        assert call("get_evidence", case_id=one["case_id"], evidence_id=eid)["classification"] == "OBSERVED"
        assert call("record_answer", case_id=one["case_id"], question_id=one["question_id"], answer_text="no") ["status"] == "ok"
        assert "no" in call("get_handover", case_id=one["case_id"])["message"]
        assert call("record_answer", case_id=one["case_id"], question_id=one["question_id"], answer_text="retry")["code"] == "INVALID_SCOPE"


@pytest.mark.parametrize("scope", [
    {"station_number": ""}, {"station_number": "SYNTH", "from": "2026-01-01T00:00:00Z"},
    {"station_number": "SYNTH", "from": "2026-01-01T00:00:00", "to": "2026-01-01T00:00:00"},
])
def test_invalid_scopes_do_not_contact_oracle(monkeypatch, scope):
    def forbidden(*a, **k):
        pytest.fail("invalid scope reached Oracle")
    monkeypatch.setattr(repo, "_select_rows", forbidden)
    key = "audit-synthetic-key-" * 3
    with TestClient(create_app(Settings(api_key=key), OracleSource(OracleCredentials("synthetic", "synthetic-only", "localhost/TESTPDB")))) as client:
        result = client.post("/api/v1/cases", json=scope, headers={"X-API-Key": key})
        assert result.status_code == 422 and result.json()["data"] is None


def test_actual_empty_page_maps_no_data(monkeypatch):
    monkeypatch.setattr(repo, "_select_rows", lambda *a, **k: [])
    key = "audit-synthetic-key-" * 3
    with TestClient(create_app(Settings(api_key=key), OracleSource(OracleCredentials("synthetic", "synthetic-only", "localhost/TESTPDB")))) as client:
        result = client.post("/api/v1/cases", json={"station_number": "SYNTH-EMPTY"}, headers={"X-API-Key": key})
        assert result.status_code == 404
        assert result.json()["error"]["code"] == "NO_DATA"
        assert result.json()["error"]["scope"]["station_number"] == "SYNTH-EMPTY"
        assert result.json()["data"] is None


def test_model_deadline_cancels_synthetic_provider(monkeypatch):
    cancelled = []
    class Hanging(FakeModel):
        async def create(self, **kwargs):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
    with make(Hanging(), monkeypatch, model_timeout_seconds=0.01)[0] as client:
        result = say(client, {"X-API-Key": client.app.state.settings.api_key}, "hi")
        assert result["data"]["model"] is None and cancelled == [True]


def test_multiple_model_actions_rejected_before_side_effect(monkeypatch):
    class Multiple(FakeModel):
        async def create(self, **kwargs):
            response = await super().create(**kwargs)
            parsed = response.parse()
            parsed.choices[0].message.tool_calls *= 2
            return SimpleNamespace(headers=response.headers, parse=lambda: parsed)
    with make(Multiple(("open_case", {"station_number": "SYNTHETIC-STATION"})), monkeypatch)[0] as client:
        result = say(client, {"X-API-Key": client.app.state.settings.api_key}, "hi")
        assert result["data"]["model"] is None and not client.app.state.cases._items


def test_auth_throttle_does_not_retain_unknown_names():
    from agent.auth import Throttle
    throttle = Throttle()
    for i in range(1000):
        throttle.blocked(str(i))
    assert not throttle._fails


def test_generated_demo_password_has_sufficient_entropy_shape():
    from agent.make_employees import demo_password
    values = {demo_password() for _ in range(10)}
    assert len(values) == 10 and all(len(x) >= 24 for x in values)
