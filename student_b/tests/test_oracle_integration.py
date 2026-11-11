"""Actual packaged A2/A3 + B HTTP boundary; only the Oracle driver is synthetic."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import oracledb
import pytest
from fastapi.testclient import TestClient

from backend.app import oracle_repo as a
from backend.app import schemas as s
from student_b.main import Settings, create_app
from student_b.source import OracleCredentials, OracleSource, raw_number_text
from .test_cases_api import assert_error, wire


STATION = "SYNTH-A"
STAMP = "2026-01-01T10:00:00.123456"


def raw_rows():
    # Independent expected subtraction: 3.0150 - 3.0000 = 0.0150.
    inputs = (
        ("Synthetic length", " 3.0150 ", "1", "3.0000", "mm", Decimal("1001")),
        ("Synthetic count", "8", "8", "8", "count", None),
        ("Synthetic missing", " ", None, None, None, None),
    )
    return [(STATION, "SYNTH-S", name, value, lower, upper, unit, code, STAMP,
             "SYNTH-P", "SYNTH-W", Decimal("1"), None, f"synthetic-rowid-{i}")
            for i, (name, value, lower, upper, unit, code) in enumerate(inputs)]


@pytest.fixture
def integrated(monkeypatch, key):
    state = SimpleNamespace(rows=raw_rows(), calls=[], failure=None)
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    def execute(sql, binds=None):
        state.calls.append((sql, dict(binds or {})))
        if state.failure:
            raise state.failure
        if binds is None:
            cursor.fetchone.return_value = (len(state.rows),)
        elif "station_number" in binds:
            rows = [r for r in state.rows if r[0] == binds["station_number"]
                    and (binds["serial_number"] is None or r[1] == binds["serial_number"])
                    and (binds["from_time"] is None or datetime.fromisoformat(r[8]) >= binds["from_time"])
                    and (binds["to_time"] is None or datetime.fromisoformat(r[8]) < binds["to_time"])]
            total = len(rows)
            cursor.fetchmany.return_value = [(*r, Decimal(total), STAMP, STAMP, Decimal(0))
                                            for r in rows[:binds["row_limit"]]]
        else:
            # Literal case-sensitive substring, matching the accepted A2 contract.
            stations = sorted({r[0] for r in state.rows if binds["q"] is None or binds["q"] in r[0]})
            cursor.fetchmany.return_value = [(station, Decimal(sum(r[0] == station for r in state.rows)), Decimal(len(stations)))
                                            for station in stations[:binds["row_limit"]]]

    cursor.execute.side_effect = execute
    monkeypatch.setattr(oracledb, "connect", connect)
    credentials = OracleCredentials("synthetic_reader", "synthetic-only", "localhost/TESTPDB")
    app = create_app(Settings(api_key=key, oracle=credentials, development_routes=True, row_limit=2))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield app, client, {"X-API-Key": key}, state, cursor


def test_actual_a2_a3_full_journey_preserves_capture(integrated):
    app, client, headers, state, cursor = integrated
    opened = client.post("/api/v1/cases", json={"station_number": STATION}, headers=headers)
    assert opened.status_code == 200, opened.text
    payload = opened.json()
    wire("OpenCaseResponse", payload)
    data = payload["data"]
    first, second = data["findings"]
    assert first["raw_value"] == " 3.0150 "
    assert (first["parsed_value"], first["deviation"], first["raw_fail_code"]) == ("3.0150", "0.0150", "1001")
    assert second["range_status"] == "WITHIN_RECORDED_BOUNDS" and second["deviation"] is None
    assert second["raw_fail_code"] is None
    assert data["scope"]["row_count"] == 3 and data["scope"]["captured_row_count"] == 2
    assert data["scope"]["truncated"] and "TIME_SCOPE_HALF_OPEN" in data["warnings"]
    assert data["assessment"]["label"] == "UNDETERMINED"
    prefix = f"/api/v1/cases/{payload['case_id']}"
    observed = client.get(prefix + "/evidence/" + first["evidence_id"], headers=headers).json()
    wire("GetEvidenceResponse", observed)
    assert observed["data"]["raw_fields"]["BOOK_STAMP"] == STAMP
    assert observed["data"]["retrieved_at"] == data["observations_retrieved_at"]
    with app.state.cases.locked(payload["case_id"]) as case:
        page, evaluations = case.source_capture
        assert page.total_matching_rows == 3 and page.truncated
        assert evaluations[0].record is page.records[0]
        assert page.records[0].source_rowid == "synthetic-rowid-0"
        with pytest.raises(FrozenInstanceError):
            page.records[0].raw_value = "changed"
    state.failure = oracledb.DatabaseError(SimpleNamespace(full_code="ORA-01017", message="private connection details"))
    before_calls = len(state.calls)
    recorded = client.post(prefix + "/answers", json={"question_id": data["next_action"]["question_id"], "answer_text": "Synthetic context report."}, headers=headers).json()
    wire("RecordAnswerResponse", recorded)
    handover = client.get(prefix + "/handover", headers=headers).json()
    wire("GetHandoverResponse", handover)
    assert handover["data"]["observations"] == data["findings"]
    assert recorded["data"]["findings"] == data["findings"]
    assert client.get(prefix + "/evidence/" + first["evidence_id"], headers=headers).json()["data"] == observed["data"]
    assert len(state.calls) == before_calls
    assert "source_rowid" not in opened.text and "workorder_number" not in opened.text
    assert "private connection details" not in str(handover)


def test_time_filters_are_half_open_with_six_digit_source_precision(integrated):
    _, client, headers, state, cursor = integrated
    body = {"station_number": STATION, "from": STAMP, "to": "2026-01-01T10:00:00.123457"}
    result = client.post("/api/v1/cases", json=body, headers=headers)
    assert result.status_code == 200, result.text
    binds = state.calls[-1][1]
    assert binds["from_time"] == datetime(2026, 1, 1, 10, 0, 0, 123456)
    assert binds["to_time"] == datetime(2026, 1, 1, 10, 0, 0, 123457)
    cursor.setinputsizes.assert_called_with(from_time=oracledb.DB_TYPE_TIMESTAMP, to_time=oracledb.DB_TYPE_TIMESTAMP)
    body = {"station_number": STATION, "to": STAMP}
    assert_error(client.post("/api/v1/cases", json=body, headers=headers), "NO_DATA", 404)


@pytest.mark.parametrize("bounds", [
    {"from": "2026-01-01"}, {"from": STAMP, "to": STAMP},
    {"from": "2026-01-01T10:00:00.1234567"},
])
def test_a_scope_validation_maps_to_422_before_driver(integrated, bounds):
    _, client, headers, state, _ = integrated
    result = client.post("/api/v1/cases", json={"station_number": STATION, **bounds}, headers=headers)
    assert_error(result, "INVALID_SCOPE", 422)
    assert state.calls == []


def test_station_search_and_null_case(integrated):
    _, client, headers, state, _ = integrated
    for query, expected in (("YNTH", 1), ("ynth", 0), ("%", 0), ("_", 0)):
        result = client.get("/api/v1/stations", params={"q": query, "limit": 1}, headers=headers).json()
        wire("ListStationsResponse", result)
        assert result["case_id"] is None and len(result["data"]["stations"]) == expected
    for query in ("", " "):
        assert_error(client.get("/api/v1/stations", params={"q": query}, headers=headers), "INVALID_SCOPE", 422)


@pytest.mark.parametrize("code,expected,status", [
    ("DPY-4024", "TIMEOUT", 504), ("ORA-01013", "SOURCE_UNAVAILABLE", 503),
    ("ORA-01017", "SOURCE_UNAVAILABLE", 503),
])
def test_driver_error_crosses_all_a_read_routes(integrated, code, expected, status):
    _, client, headers, state, _ = integrated
    state.failure = oracledb.DatabaseError(SimpleNamespace(full_code=code, message="private source details"))
    for response in (client.post("/api/v1/cases", json={"station_number": STATION}, headers=headers),
                     client.get("/api/v1/stations", headers=headers),
                     client.get("/api/v1/health/echo", headers=headers), client.get("/readyz")):
        assert_error(response, expected, status)
        assert "private source details" not in response.text


def test_no_data_preserves_exact_input_scope(integrated):
    _, client, headers, _, _ = integrated
    scope = {"station_number": "SYNTH-ABSENT", "serial_number": None, "from": "2026-01-01T00:00:00", "to": None}
    result = assert_error(client.post("/api/v1/cases", json=scope, headers=headers), "NO_DATA", 404)
    assert result["error"]["scope"] == scope


def test_high_precision_uses_actual_a3_under_hostile_decimal_context(integrated):
    _, client, headers, state, _ = integrated
    raw = list(state.rows[0])
    raw[3:6] = ["12345678901234567890.0150", "0", "12345678901234567890.0000"]
    state.rows = [tuple(raw)]
    with localcontext() as ctx:
        ctx.prec = 2
        response = client.post("/api/v1/cases", json={"station_number": STATION}, headers=headers)
    finding = response.json()["data"]["findings"][0]
    assert finding["parsed_value"] == "12345678901234567890.0150" and finding["deviation"] == "0.0150"


def test_raw_number_projection_rejects_float_and_bool():
    for value in (1.5, True, Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(TypeError):
            raw_number_text(value)


def test_source_retrieval_time_and_coverage_are_retained(monkeypatch):
    timestamp = "2026-01-01T10:00:01.654321+00:00"
    record = a.MeasurementRecord(*raw_rows()[0], snapshot_ordinal=1)
    page = a.MeasurementPage(a.MeasurementScope(STATION, None, None, None, 200), (record,), 1, STAMP, STAMP, 0, timestamp)
    monkeypatch.setattr(a, "read_measurements", lambda **kwargs: page)
    source = OracleSource(OracleCredentials("synthetic_reader", "synthetic-only", "localhost/TESTPDB"))
    batch = source.fetch_measurements(s.OpenCaseRequest(station_number=STATION), limit=200)
    assert batch.retrieved_at == datetime(2026, 1, 1, 10, 0, 1, 654321, tzinfo=timezone.utc)
    assert batch.source_capture[0] is page


def test_acceptance_client_against_real_loopback_http_and_packaged_a(integrated, key):
    import socket
    from threading import Thread
    from time import monotonic, sleep
    import uvicorn
    from student_b.live_check import Client, run_checks

    app, _, _, _, _ = integrated
    app.state.settings = replace(app.state.settings, row_limit=200)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False, log_level="critical"))
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = monotonic() + 5
        while not server.started and thread.is_alive() and monotonic() < deadline:
            sleep(0.01)
        assert server.started
        run_checks(Client(f"http://127.0.0.1:{port}", key), {"station_number": STATION}, check_echo=True, expected_count=3)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
    assert not thread.is_alive()


@pytest.mark.parametrize("url", ["https://example.com", "http://example.com", "http://user:password@localhost", "http://localhost/api/v1"])
def test_acceptance_client_rejects_remote_or_credential_urls(url, key):
    from student_b.live_check import Client, CheckError
    with pytest.raises(CheckError):
        Client(url, key)
