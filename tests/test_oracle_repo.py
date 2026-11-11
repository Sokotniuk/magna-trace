"""Synthetic driver and loopback transport tests. No Oracle login is used."""

from pathlib import Path
import re
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock

import oracledb
import pytest

from backend.app.oracle_repo import (
    OracleTimeoutError,
    SourceUnavailableError,
    count_measurements,
)


@pytest.fixture
def driver(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (7,)
    connect = MagicMock()
    connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(oracledb, "connect", connect)
    return connect, connection, cursor


def test_fixed_count_query_and_resource_cleanup(driver):
    connect, connection, cursor = driver

    assert count_measurements(
        user="synthetic_reader", password="synthetic-only", dsn="localhost/TESTPDB"
    ) == 7

    cursor.execute.assert_called_once_with(
        "SELECT COUNT(*) FROM HACKATON.SNO_MEASUREMENT_DATA"
    )
    cursor.fetchone.assert_called_once_with()
    connection.cursor.return_value.__exit__.assert_called_once()
    connect.return_value.__exit__.assert_called_once()
    assert connection.call_timeout == 5000


def test_connection_limits_override_dsn_options(driver):
    connect, connection, _ = driver

    count_measurements(
        user="synthetic_reader",
        password="synthetic-only",
        dsn="localhost/TESTPDB?transport_connect_timeout=99&retry_count=8",
        call_timeout_ms=200,
        connect_timeout_seconds=2,
    )

    params = connect.call_args.kwargs["params"]
    assert params.user == "synthetic_reader"
    assert params.tcp_connect_timeout == 2
    assert params.retry_count == 0
    assert connection.call_timeout == 200


def test_zero_is_an_actual_count(driver):
    _, _, cursor = driver
    cursor.fetchone.return_value = (0,)
    assert count_measurements(
        user="synthetic_reader", password="synthetic-only", dsn="localhost/TESTPDB"
    ) == 0


@pytest.mark.parametrize("row", [None, (), (None,), (-1,), ("7",), (True,), (7, 8)])
def test_invalid_count_cannot_become_substitute_data(driver, row):
    connect, connection, cursor = driver
    cursor.fetchone.return_value = row
    with pytest.raises(SourceUnavailableError, match="no valid count"):
        count_measurements(
            user="synthetic_reader",
            password="synthetic-only",
            dsn="localhost/TESTPDB",
        )
    connection.cursor.return_value.__exit__.assert_called_once()
    connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("stage", ["connect", "execute", "fetch"])
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("DPY-6005", SourceUnavailableError),
        ("ORA-00942", SourceUnavailableError),
        ("DPY-4024", OracleTimeoutError),
        ("DPI-1067", OracleTimeoutError),
        ("DPI-1080", SourceUnavailableError),
        ("ORA-12170", OracleTimeoutError),
        ("ORA-12535", OracleTimeoutError),
    ],
)
def test_database_errors_are_typed_and_redacted(driver, stage, code, expected):
    connect, connection, cursor = driver
    error = oracledb.DatabaseError(
        SimpleNamespace(full_code=code, message="synthetic-sensitive-details")
    )
    operations = {
        "connect": connect,
        "execute": cursor.execute,
        "fetch": cursor.fetchone,
    }
    operations[stage].side_effect = error

    with pytest.raises(expected) as caught:
        count_measurements(
            user="synthetic_reader",
            password="synthetic-only",
            dsn="localhost/TESTPDB",
        )

    assert caught.value.code in {"SOURCE_UNAVAILABLE", "TIMEOUT"}
    assert "synthetic-sensitive-details" not in str(caught.value)
    assert caught.value.__suppress_context__
    if stage != "connect":
        connection.cursor.return_value.__exit__.assert_called_once()
        connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "settings",
    [
        {"user": ""},
        {"user": "SYS"},
        {"user": " system "},
        {"user": '"SYSTEM"'},
        {"password": ""},
        {"dsn": " "},
        {"call_timeout_ms": 0},
        {"call_timeout_ms": True},
        {"connect_timeout_seconds": -1},
        {"connect_timeout_seconds": "5"},
    ],
)
def test_invalid_settings_are_rejected_before_connect(driver, settings):
    connect, _, _ = driver
    arguments = {
        "user": "synthetic_reader",
        "password": "synthetic-only",
        "dsn": "localhost/TESTPDB",
    }
    arguments.update(settings)
    with pytest.raises(ValueError):
        count_measurements(**arguments)
    connect.assert_not_called()


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        (TimeoutError("synthetic-timeout"), OracleTimeoutError),
        (ConnectionRefusedError("synthetic-refusal"), SourceUnavailableError),
    ],
)
def test_connection_failure_preserves_timeout_distinction(driver, cause, expected):
    connect, _, _ = driver
    error = oracledb.OperationalError(SimpleNamespace(full_code="DPY-6005"))
    error.__cause__ = cause
    connect.side_effect = error
    with pytest.raises(expected):
        count_measurements(
            user="synthetic_reader",
            password="synthetic-only",
            dsn="localhost/TESTPDB",
        )


@pytest.mark.parametrize("stage", ["cursor_close", "connection_close"])
def test_cleanup_failure_prevents_returning_a_count(driver, stage):
    connect, connection, _ = driver
    exits = {
        "cursor_close": connection.cursor.return_value.__exit__,
        "connection_close": connect.return_value.__exit__,
    }
    exits[stage].side_effect = oracledb.DatabaseError()
    with pytest.raises(SourceUnavailableError):
        count_measurements(
            user="synthetic_reader",
            password="synthetic-only",
            dsn="localhost/TESTPDB",
        )
    connect.return_value.__exit__.assert_called_once()


def test_baseline_contains_only_reads_and_independent_table_counts():
    baseline = Path(__file__).resolve().parents[1] / "docs" / "data-baseline.sql"
    # A4's prepared templates are SQL comments, checked by their own tests.
    sql = re.sub(r"/\*.*?\*/", "", baseline.read_text(encoding="utf-8"), flags=re.S)
    sql = re.sub(r"--[^\n]*", "", sql)
    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]

    assert statements
    for statement in statements:
        assert re.match(r"(SELECT|WITH)\b", statement, re.IGNORECASE)
        assert not re.search(
            r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|"
            r"GRANT|REVOKE|EXECUTE|BEGIN|COMMIT|ROLLBACK)\b",
            statement,
            re.IGNORECASE,
        )

    for table in (
        "MACHINE_LINES",
        "SNO_BOOKINGS_WP",
        "SNO_MEASUREMENT_DATA",
        "WORKORDERS",
    ):
        assert re.search(
            r"SELECT\s+COUNT\(\*\)\s+AS\s+\w+\s+FROM\s+HACKATON\."
            + table
            + r"\s*;",
            sql,
            re.IGNORECASE,
        )


def test_real_driver_tcp_timeout_and_zero_retries(monkeypatch):
    # TCP establishment is a separate phase from the Oracle login handshake.
    # Exercise the real driver with a deterministic socket failure, avoiding
    # network routes whose refusal/blackhole behavior depends on the host.
    tcp_connect = MagicMock(side_effect=TimeoutError("synthetic TCP timeout"))
    monkeypatch.setattr(socket, "create_connection", tcp_connect)
    with pytest.raises(OracleTimeoutError):
        count_measurements(
            user="synthetic_reader",
            password="synthetic-only",
            dsn=(
                "127.0.0.1:1521/TESTPDB"
                "?transport_connect_timeout=20&retry_count=2&retry_delay=1"
            ),
            connect_timeout_seconds=1,
        )
    tcp_connect.assert_called_once_with(("127.0.0.1", 1521), 1)


def test_baseline_duplicate_audit_uses_verified_column_inventory():
    # Independent source: the student's 23-row ALL_TAB_COLUMNS result.
    verified_columns = {
        "STATION_ID", "STATION_NUMBER", "STATION_DESC",
        "PART_NUMBER", "PART_DESC", "WORKORDER_NUMBER", "WORKORDER_DESC",
        "SERIAL_NUMBER", "MEASURE_STEP_NUMBER", "MEASURE_NAME", "UNIT",
        "MEASURE_VALUE", "LOWER_LIMIT", "UPPER_LIMIT", "NOMINAL", "TOLERANCE",
        "MEASURE_FAIL_CODE", "BOOK_STAMP", "MEASURE_TYPE",
        "LOWER_INTERVENTION_LIMIT", "UPPER_INTERVENTION_LIMIT",
        "LOWER_SCRAP_LIMIT", "UPPER_SCRAP_LIMIT",
    }
    baseline = Path(__file__).resolve().parents[1] / "docs" / "data-baseline.sql"
    sql = re.sub(r"/\*.*?\*/", "", baseline.read_text(encoding="utf-8"), flags=re.S)
    partition_lists = re.findall(r"PARTITION BY\s+([^)]*)", sql, re.IGNORECASE)
    assert len(partition_lists) == 3
    for partition in partition_lists:
        assert {column.strip() for column in partition.split(",")} <= verified_columns
    assert {
        column.strip() for column in partition_lists[-1].split(",")
    } == verified_columns
    assert "JOIN HACKATON." not in sql
