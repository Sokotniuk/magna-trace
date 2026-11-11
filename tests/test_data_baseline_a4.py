"""A4 fixed-query behavior with synthetic rows and hand-derived expectations.

SQLite checks relational behavior after adapting only FETCH FIRST. Oracle
dialect/native timestamp acceptance and the real demo rows require student/D5
verification. Nothing here establishes a real case or a backend evidence ID.
"""

from dataclasses import asdict
from pathlib import Path
import re
import sqlite3

import pytest

from backend.app.measurements import analyze_measurement
from backend.app.oracle_repo import MeasurementRecord


BASELINE = Path(__file__).resolve().parents[1] / "docs" / "data-baseline.sql"
QUERIES = dict(re.findall(r"/\* (A4-\d\d)\n(SELECT\b.*?)\n\*/", BASELINE.read_text(encoding="utf-8"), re.S))
T0 = "2026-01-01T10:00:00.000000"
T1 = "2026-01-01T10:00:00.000001"
T2 = "2026-01-01T10:00:00.000002"


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("ATTACH DATABASE ':memory:' AS HACKATON")
    connection.create_function("ROWIDTOCHAR", 1, str)
    connection.execute("""CREATE TABLE HACKATON.SNO_MEASUREMENT_DATA (
        STATION_NUMBER TEXT, SERIAL_NUMBER TEXT, MEASURE_NAME TEXT,
        MEASURE_VALUE TEXT, LOWER_LIMIT TEXT, UPPER_LIMIT TEXT, UNIT TEXT,
        MEASURE_FAIL_CODE INTEGER, BOOK_STAMP TEXT, PART_NUMBER TEXT,
        WORKORDER_NUMBER TEXT, MEASURE_STEP_NUMBER INTEGER, MEASURE_TYPE TEXT,
        NOMINAL TEXT, TOLERANCE TEXT, LOWER_INTERVENTION_LIMIT TEXT,
        UPPER_INTERVENTION_LIMIT TEXT, LOWER_SCRAP_LIMIT TEXT, UPPER_SCRAP_LIMIT TEXT
    )""")
    # Hand-labelled physical order within SYNTH-A: 1,2,3,4,5,6. Rows 1/2
    # collide on the extended candidate fields but have different raw values.
    connection.executemany("""INSERT INTO HACKATON.SNO_MEASUREMENT_DATA VALUES
        (?,?,?,?,?,?,?,?,?,'P','W',1,'synthetic','100','0.5','-100','100','-200','200')""", [
        ("SYNTH-A", "S1", "Length", " 31.250 ", "0", "30.000", "mm", 1001, T2),
        ("SYNTH-A", "S1", "Length", "32.000", "0", "30.000", "mm", None, T2),
        ("SYNTH-A", "S2", "Offset", "-2.50", "-2.00", "0", "mm", None, T1),
        ("SYNTH-A", "S2", "Category", "abc", "0", "1", "u", 1001, T0),
        ("SYNTH-A", "S3", "Missing limits", "2", None, None, None, None, T0),
        ("SYNTH-A", "S3", "Reversed", "2", "3", "1", "u", None, None),
        ("SYNTH-B", "S4", "Screw Count", "8", "8.0", "8.00", "count", 1001, T1),
        ("SYNTH-B", "S4", "Screw Count", "9", "8", "8", "count", 1001, T1),
    ])
    yield connection
    connection.close()


def query(database, label, **binds):
    statement = QUERIES[label].replace("FETCH FIRST :row_limit ROWS ONLY", "LIMIT :row_limit")
    return [dict(row) for row in database.execute(statement, binds)]


def scope(database, **changes):
    return query(database, "A4-01", **{
        "station_number": "SYNTH-A", "serial_number": None,
        "from_time": None, "to_time": None, "row_limit": 100, **changes,
    })


def record(source):
    values = {name: source[name] for name in MeasurementRecord.__dataclass_fields__ if name != "snapshot_ordinal"}
    return MeasurementRecord(**values, snapshot_ordinal=source["capture_ordinal"])


def test_fixed_select_templates_bind_all_scope_values_and_are_bounded():
    assert set(QUERIES) == {"A4-01", "A4-02", "A4-03"}
    required = {
        "A4-01": {"station_number", "serial_number", "from_time", "to_time", "row_limit"},
        "A4-02": {"fail_code", "measurement", "row_limit"},
        "A4-03": {"station_number", "serial_number", "source_rowid", "row_limit"},
    }
    for label, statement in QUERIES.items():
        assert statement.startswith("SELECT ")
        assert set(re.findall(r":([a-z_]+)", statement)) == required[label]
        assert "FETCH FIRST :row_limit ROWS ONLY" in statement
        assert "ORDER BY m.BOOK_STAMP DESC NULLS LAST, m.ROWID ASC" in statement
        assert "SELECT *" not in statement
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|GRANT|BEGIN)\b", statement, re.I)
        assert "TO_NUMBER" not in statement  # No session-dependent numeric conversion.


def test_three_hand_derived_abnormal_rows_match_a3_and_preserve_raw_fields(database):
    rows = scope(database)
    expected = [("1", "ABOVE", "1.250"), ("2", "ABOVE", "2.000"), ("3", "BELOW", "0.50")]
    for source, (locator, status, deviation) in zip(rows[:3], expected):
        observed = record(source)
        original = asdict(observed)
        result = analyze_measurement(observed)
        assert source["source_rowid"] == locator
        assert result.range_status == status
        assert str(result.deviation) == deviation
        assert result.record is observed and asdict(observed) == original
        assert result.raw_fail_code == source["raw_fail_code"]
    assert rows[0]["raw_value"] == " 31.250 "
    assert rows[0]["nominal"] == "100"  # Context must not replace the recorded upper bound 30.


def test_coded_screw_count_is_selected_by_raw_sql_then_checked_numerically(database):
    rows = query(database, "A4-02", fail_code=1001, measurement="Screw Count", row_limit=100)
    assert [item["source_rowid"] for item in rows] == ["7", "8"]
    first, second = (analyze_measurement(record(item)) for item in rows)
    assert first.range_status == "WITHIN_RECORDED_BOUNDS" and first.deviation is None
    assert first.raw_fail_code == second.raw_fail_code == 1001
    assert first.quality_flags == second.quality_flags == ("SEMANTICS_UNKNOWN",)
    assert second.range_status == "ABOVE" and str(second.deviation) == "1"


def test_scoped_order_repeatability_half_open_bounds_and_pre_cap_counts(database):
    rows = scope(database, from_time=T1, to_time=T2, row_limit=1)
    assert [item["source_rowid"] for item in rows] == ["3"]
    assert rows[0]["total_matching_rows"] == 1
    capped = scope(database, row_limit=2)
    assert [item["source_rowid"] for item in capped] == ["1", "2"]
    assert [item["capture_ordinal"] for item in capped] == [1, 2]
    assert [item["total_matching_rows"] for item in capped] == [6, 6]
    assert capped == scope(database, row_limit=2)
    assert [item["source_rowid"] for item in scope(database, serial_number="S1")] == ["1", "2"]


def test_empty_station_or_missing_coded_case_returns_no_substitute_rows(database):
    assert scope(database, station_number="unknown") == []
    assert scope(database, station_number="X' OR 1=1 --") == []
    assert query(database, "A4-02", fail_code=1001, measurement="absent", row_limit=100) == []
    assert query(database, "A4-03", station_number="SYNTH-A", serial_number="S1",
                 source_rowid="absent", row_limit=2) == []


def test_duplicate_candidate_keys_remain_two_distinct_captured_rows(database):
    rows = scope(database)
    assert rows[0]["candidate_multiplicity"] == rows[1]["candidate_multiplicity"] == 2
    assert rows[0]["source_rowid"] != rows[1]["source_rowid"]
    for expected in rows[:2]:
        captured = query(database, "A4-03", station_number="SYNTH-A", serial_number="S1",
                         source_rowid=expected["source_rowid"], row_limit=2)
        assert len(captured) == 1
        assert captured[0]["raw_value"] == expected["raw_value"]
        assert captured[0]["raw_upper"] == "30.000"
    assert query(database, "A4-03", station_number="SYNTH-B", serial_number="S1",
                 source_rowid=rows[0]["source_rowid"], row_limit=2) == []


def test_invalid_nonnumeric_and_unknown_bounds_never_become_selected_breaches(database):
    results = [analyze_measurement(record(item)) for item in scope(database)[3:]]
    assert [result.range_status for result in results] == ["NOT_EVALUABLE"] * 3
    assert [result.quality_flags for result in results] == [
        ("UNPARSEABLE", "SEMANTICS_UNKNOWN"),
        ("LIMIT_UNKNOWN", "UNIT_UNKNOWN", "SEMANTICS_UNKNOWN"),
        ("LIMIT_INVALID", "SEMANTICS_UNKNOWN"),
    ]
    assert all(result.deviation is None for result in results)
