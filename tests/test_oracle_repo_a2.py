"""A2 behavior checks using synthetic SQLite data and injected Oracle failures.

SQLite executes the repository SELECTs with only FETCH FIRST syntax translated.
This checks relational behavior independently of mocked output tuples. It does
not verify Oracle dialect acceptance, ROWID access, or live source values.
"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
import re
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import oracledb
import pytest

from backend.app import oracle_repo as repo


SETTINGS = {
    "user": "synthetic_reader",
    "password": "synthetic-only",
    "dsn": "127.0.0.1/TESTPDB",
}
T0 = "2026-01-01T10:00:00.000000"
T1 = "2026-01-01T10:00:00.000001"
T2 = "2026-01-01T10:00:00.000002"
T3 = "2026-01-01T10:00:01.000000"


class CursorAdapter:
    def __init__(self, source):
        self.source = source
        self.cursor = source.database.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def setinputsizes(self, **sizes):
        self.source.input_sizes.append(sizes)

    def execute(self, statement, binds):
        self.source.calls.append((statement, binds.copy()))
        sql = statement.replace(
            "FETCH FIRST :row_limit ROWS ONLY", "LIMIT :row_limit"
        )
        values = {
            name: value.isoformat(timespec="microseconds")
            if isinstance(value, datetime) else value
            for name, value in binds.items()
        }
        self.cursor.execute(sql, values)

    def fetchmany(self, size):
        return self.cursor.fetchmany(size)


@pytest.fixture
def source(monkeypatch):
    database = sqlite3.connect(":memory:")
    database.execute("ATTACH DATABASE ':memory:' AS HACKATON")
    database.create_function("TO_CHAR", 2, lambda value, fmt: value)
    database.create_function("ROWIDTOCHAR", 1, str)
    database.execute("""
        CREATE TABLE HACKATON.SNO_MEASUREMENT_DATA (
            STATION_NUMBER TEXT, SERIAL_NUMBER TEXT, MEASURE_NAME TEXT,
            MEASURE_VALUE TEXT, LOWER_LIMIT TEXT, UPPER_LIMIT TEXT, UNIT TEXT,
            MEASURE_FAIL_CODE INTEGER, BOOK_STAMP TEXT, PART_NUMBER TEXT,
            WORKORDER_NUMBER TEXT, MEASURE_STEP_NUMBER INTEGER, MEASURE_TYPE TEXT
        )
    """)
    # Hand-labelled order for station A is physical rows 5,4,2,3,1,6.
    database.executemany(
        """INSERT INTO HACKATON.SNO_MEASUREMENT_DATA
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("A", "S1", "M", " 1.00 ", "0", "2.00", "u", 1001, T0, "P", "W", 1, "test"),
            ("A", "S1", "M", "1,5", "0", "2", "v", None, T1, "P", "W", 1, None),
            ("A", "S1", "M", "1,5", "0", "2", "v", None, T1, "P", "W", 1, None),
            ("A", "S2", "M", None, None, "2", "u", None, T2, "P", "W", 1, "test"),
            ("A", "S2", "M", "1e3", "0", None, "u", 1001, T3, "P", "W", 1, "test"),
            ("A", "S3", "M", "0", "0", "2", None, None, None, "P", "W", 1, "test"),
            ("B", "S1", "M2", "2", "0", "3", "u", None, T1, "P", "W", 1, "test"),
            ("B", "S4", "M2", "-1", "0", "3", "u", None, T0, "P", "W", 1, "test"),
        ],
    )
    value = SimpleNamespace(
        database=database, calls=[], input_sizes=[], connection=MagicMock()
    )
    value.connection.cursor.side_effect = lambda: CursorAdapter(value)
    connect = MagicMock()
    connect.return_value.__enter__.return_value = value.connection
    monkeypatch.setattr(oracledb, "connect", connect)
    value.connect = connect
    yield value
    database.close()


def test_raw_capture_order_metadata_and_repeatability(source):
    page = repo.read_measurements(**SETTINGS, station_number="A", limit=2)
    again = repo.read_measurements(**SETTINGS, station_number="A", limit=2)
    assert [row.source_rowid for row in page.records] == ["5", "4"]
    assert page.records == again.records
    assert (page.returned_count, page.total_matching_rows, page.truncated) == (2, 6, True)
    assert (page.first_book_stamp, page.last_book_stamp, page.missing_book_stamps) == (T0, T3, 1)
    assert page.source_table == "HACKATON.SNO_MEASUREMENT_DATA"
    assert page.scope.station_number == "A"
    assert "ROWID_NOT_DURABLE" in page.warnings
    assert datetime.fromisoformat(page.retrieved_at).utcoffset().total_seconds() == 0
    assert source.input_sizes[-1] == {
        "from_time": oracledb.DB_TYPE_TIMESTAMP,
        "to_time": oracledb.DB_TYPE_TIMESTAMP,
    }

    all_rows = repo.read_measurements(**SETTINGS, station_number="A")
    assert [row.source_rowid for row in all_rows.records] == ["5", "4", "2", "3", "1", "6"]
    assert [row.snapshot_ordinal for row in all_rows.records] == [1, 2, 3, 4, 5, 6]
    assert all_rows.records[2].raw_value == all_rows.records[3].raw_value == "1,5"
    raw = all_rows.records[4]
    assert (raw.raw_value, raw.raw_lower, raw.raw_upper, raw.raw_fail_code) == (
        " 1.00 ", "0", "2.00", 1001
    )
    assert all_rows.records[-1].unit is None
    assert not all_rows.truncated
    with pytest.raises(FrozenInstanceError):
        raw.raw_value = "changed"


@pytest.mark.parametrize(
    ("filters", "rowids"),
    [
        ({"from_time": T1, "to_time": T3}, ["4", "2", "3"]),
        ({"from_time": T1, "to_time": T3, "serial_number": "S1"}, ["2", "3"]),
        ({"serial_number": "S2"}, ["5", "4"]),
        ({"from_time": T3}, ["5"]),
        ({"to_time": T1}, ["1"]),
    ],
)
def test_filters_and_microsecond_interval_boundaries(source, filters, rowids):
    page = repo.read_measurements(**SETTINGS, station_number="A", **filters)
    assert [row.source_rowid for row in page.records] == rowids
    assert page.total_matching_rows == len(rowids)
    assert page.returned_count == len(rowids)
    assert not page.truncated
    if "from_time" in filters:
        assert source.calls[-1][1]["from_time"] == datetime.fromisoformat(filters["from_time"])


def test_empty_results_preserve_scope_and_never_imply_source_failure(source):
    page = repo.read_measurements(
        **SETTINGS, station_number="unknown", serial_number="S1",
        from_time=T0, to_time=T1, limit=1,
    )
    assert page.records == ()
    assert page.total_matching_rows == page.returned_count == 0
    assert not page.truncated
    assert page.first_book_stamp is page.last_book_stamp is None
    assert page.missing_book_stamps == 0
    assert (page.scope.station_number, page.scope.serial_number) == ("unknown", "S1")
    assert (page.scope.from_time, page.scope.to_time) == (T0, T1)


@pytest.mark.parametrize("amount", [1, repo.MAX_LIMIT, repo.MAX_LIMIT + 1])
def test_exact_cap_and_overflow(source, amount):
    source.database.execute("DELETE FROM HACKATON.SNO_MEASUREMENT_DATA")
    source.database.executemany(
        """INSERT INTO HACKATON.SNO_MEASUREMENT_DATA
           VALUES ('A','S1','M','1','0','2','u',NULL,?,'P','W',1,NULL)""",
        [(T0,)] * amount,
    )
    page = repo.read_measurements(**SETTINGS, station_number="A", limit=repo.MAX_LIMIT)
    assert page.returned_count == min(amount, repo.MAX_LIMIT)
    assert page.total_matching_rows == amount
    assert page.truncated == (amount > repo.MAX_LIMIT)
    assert len({row.source_rowid for row in page.records}) == page.returned_count


def test_station_group_counts_literal_search_and_request_isolation(source):
    all_stations = repo.list_stations(**SETTINGS, limit=1)
    assert [(r.station_number, r.record_count) for r in all_stations.records] == [("A", 6)]
    assert all_stations.total_matching_stations == 2 and all_stations.truncated
    only_b = repo.list_stations(**SETTINGS, q="B", limit=2)
    assert [(r.station_number, r.record_count) for r in only_b.records] == [("B", 2)]
    assert only_b.total_matching_stations == 1 and not only_b.truncated
    empty = repo.list_stations(**SETTINGS, q="%")
    assert empty.records == () and empty.total_matching_stations == 0
    first = repo.read_measurements(**SETTINGS, station_number="A", serial_number="S1")
    second = repo.read_measurements(**SETTINGS, station_number="B", serial_number="S4")
    assert first.total_matching_rows == 3 and second.total_matching_rows == 1
    assert first.scope.station_number == "A" and first.scope.serial_number == "S1"


def test_malicious_station_serial_and_search_are_literal_binds(source):
    attack = "X' OR 1=1 --"
    source.database.execute(
        """INSERT INTO HACKATON.SNO_MEASUREMENT_DATA
           VALUES (?, ?, 'M','raw','0','1','u',1001,?,'P','W',1,NULL)""",
        (attack, attack, T0),
    )
    result = repo.read_measurements(**SETTINGS, station_number=attack, serial_number=attack)
    assert result.returned_count == result.total_matching_rows == 1
    assert result.records[0].station_number == result.records[0].serial_number == attack
    assert attack not in source.calls[-1][0]
    assert source.calls[-1][1]["station_number"] == attack
    stations = repo.list_stations(**SETTINGS, q=attack)
    assert [row.station_number for row in stations.records] == [attack]
    assert attack not in source.calls[-1][0]


@pytest.mark.parametrize(
    "changes",
    [
        {"station_number": None}, {"station_number": ""}, {"station_number": "  "},
        {"serial_number": ""}, {"limit": 0}, {"limit": -1},
        {"limit": repo.MAX_LIMIT + 1}, {"limit": True},
        {"from_time": "invalid"}, {"from_time": "2026-02-30T00:00:00"},
        {"from_time": T0 + "Z"}, {"from_time": T0 + "1"},
        {"from_time": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        {"from_time": T1, "to_time": T1}, {"from_time": T3, "to_time": T0},
    ],
)
def test_invalid_measurement_scopes_fail_before_connect(source, changes):
    request = {"station_number": "A", **changes}
    with pytest.raises(repo.InvalidScopeError) as caught:
        repo.read_measurements(**SETTINGS, **request)
    assert caught.value.code == "INVALID_SCOPE"
    source.connect.assert_not_called()


def test_missing_scope_and_invalid_station_search_fail_before_connect(source):
    with pytest.raises(repo.InvalidScopeError):
        repo.read_measurements(**SETTINGS)
    for query in ["", "  ", 1]:
        with pytest.raises(repo.InvalidScopeError):
            repo.list_stations(**SETTINGS, q=query)
    with pytest.raises(repo.InvalidScopeError):
        repo.list_stations(**SETTINGS, limit=0)
    source.connect.assert_not_called()


@pytest.fixture
def wire(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchmany.return_value = []
    connect = MagicMock()
    connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(oracledb, "connect", connect)
    return connect, connection, cursor


@pytest.mark.parametrize(
    ("stage", "code", "expected"),
    [
        ("connect", "DPY-6005", repo.SourceUnavailableError),
        ("execute", "ORA-00942", repo.SourceUnavailableError),
        ("fetch", "DPY-4024", repo.OracleTimeoutError),
        ("close", "DPY-4011", repo.SourceUnavailableError),
    ],
)
def test_failure_injection_discards_results_and_redacts_errors(wire, stage, code, expected, caplog):
    connect, connection, cursor = wire
    operations = {
        "connect": connect, "execute": cursor.execute,
        "fetch": cursor.fetchmany, "close": connect.return_value.__exit__,
    }
    operations[stage].side_effect = oracledb.DatabaseError(
        SimpleNamespace(full_code=code, message="synthetic-sensitive-details")
    )
    with pytest.raises(expected) as caught:
        repo.read_measurements(**SETTINGS, station_number="A")
    assert "synthetic-sensitive-details" not in str(caught.value)
    assert "synthetic-only" not in caplog.text
    if stage != "connect":
        connection.cursor.return_value.__exit__.assert_called_once()
        connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "rows",
    [
        None,
        [("incomplete",)],
        [("A", 1, 0)],
        [("A", 0, 1)],
        [("A", 1, 2)],
        [("A", 1.5, 1)],
        [("A", 1, 2), ("B", 1, 3)],
    ],
)
def test_invalid_station_response_cannot_become_success(wire, rows):
    _, _, cursor = wire
    cursor.fetchmany.return_value = rows
    with pytest.raises(repo.SourceUnavailableError):
        repo.list_stations(**SETTINGS)


def test_cursor_number_conversion_is_exact_and_local(wire):
    _, _, cursor = wire
    cursor.arraysize = 100
    handler = repo._number_output
    handler(cursor, SimpleNamespace(type_code=oracledb.DB_TYPE_NUMBER))
    assert cursor.var.call_args.args == (oracledb.DB_TYPE_VARCHAR,)
    converter = cursor.var.call_args.kwargs["outconverter"]
    assert converter("1001") == Decimal("1001")
    assert converter("9999999999") == Decimal("9999999999")
    assert handler(cursor, SimpleNamespace(type_code=oracledb.DB_TYPE_VARCHAR)) is None


def test_fixed_sql_is_select_only_and_all_values_are_bound(source):
    repo.read_measurements(**SETTINGS, station_number="A", serial_number="S1", from_time=T0, to_time=T3)
    repo.list_stations(**SETTINGS, q="B")
    for statement, binds in source.calls:
        assert statement.lstrip().startswith("SELECT ")
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|GRANT)\b", statement, re.I)
        assert "SELECT *" not in statement
        assert "FETCH FIRST :row_limit ROWS ONLY" in statement
        assert set(re.findall(r"(?<![A-Z]):([a-z_]+)", statement)) == set(binds)


def test_connection_password_whitespace_is_preserved(source):
    settings = {**SETTINGS, "password": " "}
    result = repo.read_measurements(**settings, station_number="B", serial_number="S4")
    assert result.total_matching_rows == 1


@pytest.mark.parametrize(
    "changes",
    [
        {7: 1001.0},
        {8: None},
        {8: "2026-02-30T10:00:00.000000"},
        {15: T1, 16: T1},
        {17: 1},
        {0: "another station"},
        {11: "1"},
    ],
)
def test_invalid_measurement_fields_and_coverage_fail_closed(wire, changes):
    _, _, cursor = wire
    row = ["A", "S1", "M", " 1,5 ", "0", "2", "u", 1001, T0,
           "P", "W", 1, None, "physical-row", 1, T0, T0, 0]
    for position, value in changes.items():
        row[position] = value
    cursor.fetchmany.return_value = [tuple(row)]
    with pytest.raises(repo.SourceUnavailableError):
        repo.read_measurements(**SETTINGS, station_number="A")


def test_signed_decimal_fail_code_is_preserved_without_float_conversion(wire):
    _, _, cursor = wire
    cursor.fetchmany.return_value = [
        ("A", "S1", "M", "NaN", None, None, None, Decimal("-1001"), None,
         "P", "W", Decimal("1"), None, "physical-row", Decimal("1"), None, None, Decimal("1"))
    ]
    result = repo.read_measurements(**SETTINGS, station_number="A")
    assert result.records[0].raw_fail_code == Decimal("-1001")
    assert type(result.records[0].raw_fail_code) is Decimal
    assert result.records[0].raw_value == "NaN"
    assert result.first_book_stamp is result.last_book_stamp is None


def test_duplicate_station_groups_are_rejected(wire):
    _, _, cursor = wire
    cursor.fetchmany.return_value = [("A", 1, 2), ("A", 1, 2)]
    with pytest.raises(repo.SourceUnavailableError):
        repo.list_stations(**SETTINGS)


def test_oversized_or_repeated_physical_records_are_rejected(wire):
    _, _, cursor = wire
    row = ("A", "S1", "M", "1", "0", "2", "u", None, T0,
           "P", "W", 1, None, "physical-row", 2, T0, T0, 0)
    cursor.fetchmany.return_value = [row, row]
    # Covers an ignored SQL cap, then a corrupt duplicate physical locator.
    for limit in (1, 2):
        with pytest.raises(repo.SourceUnavailableError):
            repo.read_measurements(**SETTINGS, station_number="A", limit=limit)
