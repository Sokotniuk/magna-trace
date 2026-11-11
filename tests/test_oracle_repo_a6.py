"""A6 contract/failure injection and bounded loopback checks; no Oracle login."""

from datetime import date
from decimal import Decimal
import json
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import oracledb
import pytest

from backend.app import oracle_repo as repo


SETTINGS = {"user": "synthetic_reader", "password": "synthetic-only", "dsn": "127.0.0.1/TESTPDB"}


@pytest.fixture
def driver(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (7,)
    cursor.fetchmany.return_value = []
    connect = MagicMock()
    connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(oracledb, "connect", connect)
    return connect, connection, cursor


def call(name, **changes):
    arguments = {**SETTINGS, **changes}
    if name == "read_measurements":
        arguments.setdefault("station_number", "SYNTH")
    return getattr(repo, name)(**arguments)


@pytest.mark.parametrize("name,code,expected", [
    ("count_measurements", "DPI-1067", repo.OracleTimeoutError),
    ("read_measurements", "DPY-4024", repo.OracleTimeoutError),
    ("list_stations", "ORA-01017", repo.SourceUnavailableError),
])
def test_primary_failure_survives_both_cleanup_failures(driver, name, code, expected, caplog):
    connect, connection, cursor = driver
    cursor.execute.side_effect = oracledb.DatabaseError(
        SimpleNamespace(full_code=code, message="synthetic-sensitive-details")
    )
    connection.cursor.return_value.__exit__.side_effect = oracledb.DatabaseError(
        SimpleNamespace(full_code="DPY-4011")
    )
    connect.return_value.__exit__.side_effect = oracledb.DatabaseError(
        SimpleNamespace(full_code="ORA-03113")
    )
    with pytest.raises(expected) as caught:
        call(name)
    assert caught.value.driver_code == code and caught.value.phase == "execute"
    assert caught.value.__suppress_context__
    wire = json.dumps({"code": caught.value.code, "message": str(caught.value)})
    assert "synthetic-sensitive-details" not in wire + caplog.text
    assert "synthetic-only" not in wire + caplog.text
    assert not hasattr(caught.value, "records")
    connection.cursor.return_value.__exit__.assert_called_once()
    connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("wrapped_code,chain", [("DPI-1080", "__cause__"), ("DPY-4011", "__context__")])
def test_timeout_recovery_disconnect_keeps_timeout_when_structured_evidence_exists(driver, wrapped_code, chain):
    connect, _, _ = driver
    error = oracledb.DatabaseError(SimpleNamespace(full_code=wrapped_code))
    nested = oracledb.OperationalError(SimpleNamespace(full_code="DPY-6005"))
    nested.__cause__ = TimeoutError("synthetic timeout")
    setattr(error, chain, nested)
    connect.side_effect = error
    with pytest.raises(repo.OracleTimeoutError) as caught:
        call("read_measurements")
    assert caught.value.phase == "connect" and caught.value.driver_code == wrapped_code


def test_generic_disconnect_is_not_assumed_to_be_a_timeout_and_diagnostics_are_allowlisted(driver):
    connect, _, _ = driver
    error = oracledb.DatabaseError(SimpleNamespace(full_code="synthetic-sensitive-details"))
    error.__cause__ = error  # Defensive cycle handling; never copy message/DSN.
    connect.side_effect = error
    with pytest.raises(repo.SourceUnavailableError) as caught:
        call("list_stations")
    assert caught.value.driver_code is None and caught.value.phase == "connect"
    assert "sensitive" not in str(caught.value)


def test_authentication_error_does_not_inherit_an_unrelated_caller_timeout(driver):
    connect, _, _ = driver
    error = oracledb.DatabaseError(SimpleNamespace(full_code="ORA-01017"))
    error.__context__ = TimeoutError("synthetic unrelated caller failure")
    connect.side_effect = error
    with pytest.raises(repo.SourceUnavailableError) as caught:
        call("count_measurements")
    assert caught.value.driver_code == "ORA-01017"


@pytest.mark.parametrize("name", ["read_measurements", "list_stations"])
def test_successful_empty_fetch_with_failed_cleanup_cannot_become_no_data(driver, name):
    _, connection, _ = driver
    connection.cursor.return_value.__exit__.side_effect = oracledb.DatabaseError(
        SimpleNamespace(full_code="DPY-4011")
    )
    with pytest.raises(repo.SourceUnavailableError) as caught:
        call(name)
    assert caught.value.phase == "cleanup"


@pytest.mark.parametrize("response", [7, [7], {"count": 7}])
def test_malformed_scalar_driver_response_is_a_typed_failure(driver, response):
    _, _, cursor = driver
    cursor.fetchone.return_value = response
    with pytest.raises(repo.SourceUnavailableError):
        call("count_measurements")


@pytest.mark.parametrize("setting", [{"user": None}, {"password": 1}, {"dsn": []}])
def test_invalid_internal_configuration_fails_before_connect(driver, setting):
    connect, _, _ = driver
    with pytest.raises(ValueError):
        call("count_measurements", **setting)
    connect.assert_not_called()


@pytest.mark.parametrize("scope", [
    {"station_number": True}, {"serial_number": []}, {"serial_number": " \t"},
    {"from_time": date(2026, 1, 1)}, {"to_time": "2026-01-01T00:00:00+01:00"},
    {"limit": Decimal("1")},
])
def test_incorrect_scope_types_never_reach_oracle(driver, scope):
    connect, _, _ = driver
    with pytest.raises(repo.InvalidScopeError) as caught:
        call("read_measurements", **scope)
    assert caught.value.code == "INVALID_SCOPE"
    connect.assert_not_called()


def test_fetch_failure_after_execute_discards_the_entire_result_and_cleans_up(driver):
    connect, connection, cursor = driver
    cursor.fetchmany.side_effect = oracledb.OperationalError(SimpleNamespace(full_code="DPY-4011"))
    with pytest.raises(repo.SourceUnavailableError) as caught:
        call("read_measurements")
    assert caught.value.phase == "fetch"
    cursor.execute.assert_called_once()
    connection.cursor.return_value.__exit__.assert_called_once()
    connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("name", ["count_measurements", "read_measurements", "list_stations"])
def test_real_loopback_connection_refusal_is_source_unavailable(name):
    # Keep the port bound but not listening, so no shared Oracle is touched.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        dsn = "127.0.0.1:{}/TESTPDB".format(reserved.getsockname()[1])
        with pytest.raises(repo.SourceUnavailableError) as caught:
            # Windows reports refusal after about two seconds on this host;
            # a one-second limit correctly yields TIMEOUT instead.
            call(name, dsn=dsn, connect_timeout_seconds=5)
        assert caught.value.phase == "connect"


def test_stalled_handshake_exceeds_tcp_timeout_until_controlled_peer_closes():
    accepted = threading.Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(4)
        def peer():
            with listener.accept()[0] as stream:
                accepted.set()
                # Bounded synthetic peer: do not leave a permanently blocked
                # login or pretend that a successful TCP connect bounds login.
                threading.Event().wait(1.5)
        worker = threading.Thread(target=peer, daemon=True)
        worker.start()
        start = time.monotonic()
        try:
            with pytest.raises(repo.SourceUnavailableError):
                call("count_measurements", dsn="127.0.0.1:{}/TESTPDB".format(listener.getsockname()[1]),
                     connect_timeout_seconds=1, call_timeout_ms=10)
        finally:
            worker.join(timeout=4)
        assert accepted.is_set() and not worker.is_alive()
        assert time.monotonic() - start >= 1.4
