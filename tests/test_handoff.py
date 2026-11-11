"""Offline handoff checks; all rows and evidence references here are synthetic."""
from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import oracledb
import pytest
from backend.app import oracle_repo as repo
from backend.app.measurements import analyze_measurement
from handoff_adapter import dumps_exact, raw_number_text, to_json_value

SETTINGS = {"user": "synthetic_reader", "password": "synthetic-only", "dsn": "localhost/TESTPDB"}
STAMP = "2026-01-01T10:00:00.123456"

@pytest.fixture
def driver(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    connect = MagicMock()
    connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(oracledb, "connect", connect)
    return connect, cursor

def source_row(value=" 3.0150 ", lower="1", upper="3.0000", code=Decimal("1001")):
    return ("SYNTH-A", "SYNTH-S", "Synthetic length", value, lower, upper, "mm", code,
            STAMP, "SYNTH-P", "SYNTH-W", Decimal("1"), None, "synthetic-rowid",
            Decimal("1"), STAMP, STAMP, Decimal("0"))

def test_a2_to_a3_to_json_preserves_capture_and_exact_calculation(driver):
    _, cursor = driver
    cursor.fetchmany.return_value = [source_row()]
    page = repo.read_measurements(**SETTINGS, station_number="SYNTH-A")
    result = analyze_measurement(page.records[0])
    assert result.record is page.records[0]
    # 3.0150 - 3.0000 = 0.0150, derived independently by hand.
    assert result.deviation == Decimal("0.0150")
    payload = json.loads(dumps_exact({"page": page, "evaluation": result,
        "input_evidence_ids": ["synthetic-reference-from-B"]}))
    assert payload["evaluation"]["deviation"] == "0.0150"
    assert payload["evaluation"]["range_status"] == "ABOVE"
    assert payload["evaluation"]["deviation_rule"] == "value - upper"
    assert payload["evaluation"]["quality_flags"] == ["SEMANTICS_UNKNOWN"]
    assert payload["evaluation"]["record"]["raw_value"] == " 3.0150 "
    assert payload["evaluation"]["record"]["raw_fail_code"] == "1001"
    assert payload["page"]["records"][0]["book_stamp"] == STAMP
    assert payload["page"]["returned_count"] == 1
    assert payload["page"]["truncated"] is False
    assert payload["input_evidence_ids"] == ["synthetic-reference-from-B"]
    with pytest.raises(FrozenInstanceError):
        result.record.raw_value = "changed"

def test_empty_scope_is_successful_capture_not_source_failure(driver):
    _, cursor = driver
    cursor.fetchmany.return_value = []
    page = repo.read_measurements(**SETTINGS, station_number="SYNTH-EMPTY", limit=200)
    wire = json.loads(dumps_exact(page))
    assert wire["records"] == [] and wire["total_matching_rows"] == 0
    assert wire["returned_count"] == 0 and wire["truncated"] is False
    assert wire["first_book_stamp"] is wire["last_book_stamp"] is None
    assert wire["scope"] == {"station_number": "SYNTH-EMPTY", "serial_number": None,
                             "from_time": None, "to_time": None, "limit": 200}

@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_and_null_remain_distinct_raw_inputs(driver, value):
    _, cursor = driver
    cursor.fetchmany.return_value = [source_row(value, None, None, None)]
    result = analyze_measurement(repo.read_measurements(**SETTINGS, station_number="SYNTH-A").records[0])
    wire = json.loads(dumps_exact(result))
    assert wire["record"]["raw_value"] == value
    assert wire["record"]["raw_fail_code"] is None
    assert wire["deviation"] is wire["parsed_value"] is None
    assert wire["range_status"] == "NOT_EVALUABLE"

def test_high_precision_and_scale_ignore_decimal_context():
    with localcontext() as context:
        context.prec = 2
        encoded = json.loads(dumps_exact([Decimal("123456789012345678901234567890.0100"),
                                          Decimal("0.000000000000000000000000000002"), None]))
    assert encoded == ["123456789012345678901234567890.0100", "2E-30", None]

@pytest.mark.parametrize("value", [1.5, Decimal("NaN"), Decimal("Infinity"), object()])
def test_unsupported_values_fail_closed(value):
    with pytest.raises((TypeError, ValueError)):
        dumps_exact(value)

@pytest.mark.parametrize("value,expected", [(1001, "1001"), (Decimal("1001"), "1001"), (None, None)])
def test_explicit_raw_number_text(value, expected):
    assert raw_number_text(value) == expected

def test_invalid_scope_never_connects(driver):
    connect, _ = driver
    with pytest.raises(repo.InvalidScopeError) as error:
        repo.read_measurements(**SETTINGS, station_number="", limit=200)
    assert error.value.code == "INVALID_SCOPE"
    connect.assert_not_called()

@pytest.mark.parametrize("driver_code,expected,code", [
    ("DPY-4024", repo.OracleTimeoutError, "TIMEOUT"),
    ("ORA-01013", repo.SourceUnavailableError, "SOURCE_UNAVAILABLE"),
    ("ORA-01017", repo.SourceUnavailableError, "SOURCE_UNAVAILABLE"),
])
def test_typed_boundary_inputs_have_no_fallback_data(driver, driver_code, expected, code):
    _, cursor = driver
    cursor.execute.side_effect = oracledb.DatabaseError(SimpleNamespace(full_code=driver_code))
    with pytest.raises(expected) as error:
        repo.read_measurements(**SETTINGS, station_number="SYNTH-A")
    assert error.value.code == code
    assert error.value.phase == "execute" and error.value.driver_code == driver_code
    assert not hasattr(error.value, "records")

def test_station_page_metadata_survives_projection(driver):
    _, cursor = driver
    cursor.fetchmany.return_value = [("SYNTH-A", Decimal("3"), Decimal("2"))]
    wire = to_json_value(repo.list_stations(**SETTINGS, limit=1))
    assert wire["records"] == [{"station_number": "SYNTH-A", "record_count": 3}]
    assert wire["total_matching_stations"] == 2 and wire["truncated"] is True
