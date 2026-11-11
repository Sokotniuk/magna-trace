"""B1 through A's unchanged real count function with a synthetic Oracle driver."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import oracledb
import pytest
from fastapi.testclient import TestClient

from backend.app import oracle_repo as a
from backend.app.main import Settings, create_app
from backend.app.source import OracleCredentials, OracleSource


@pytest.fixture
def credentials():
    return OracleCredentials("synthetic_reader", "synthetic-only", "localhost/TESTPDB")


@pytest.fixture
def driver(monkeypatch):
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (7,)
    monkeypatch.setattr(oracledb, "connect", connect)
    return connect, connection, cursor


def test_actual_a_function_is_used_uncached_with_server_credentials(key, credentials, driver, caplog, monkeypatch):
    connect, connection, cursor = driver
    cursor.fetchone.side_effect = [(7,), (8,)]
    original_count = a.count_measurements
    calls = []
    def capture_arguments(**kwargs):
        calls.append(kwargs.copy())
        return original_count(**kwargs)
    monkeypatch.setattr(a, "count_measurements", capture_arguments)
    app = create_app(Settings(api_key=key, oracle=credentials, development_routes=True, call_timeout_ms=1234, connect_timeout_seconds=2))
    with caplog.at_level(logging.INFO, logger="magna_trace.student_b"), TestClient(app) as client:
        first = client.get("/api/v1/health/echo", headers={"X-API-Key": key})
        second = client.get("/api/v1/health/echo", headers={"X-API-Key": key})
    assert first.status_code == second.status_code == 200
    assert first.json()["data"] == {"measurement_rows": 7}
    assert second.json()["data"] == {"measurement_rows": 8}
    assert connect.call_count == 2
    cursor.execute.assert_called_with("SELECT COUNT(*) FROM HACKATON.SNO_MEASUREMENT_DATA")
    params = connect.call_args.kwargs["params"]
    assert params.user == credentials.user
    # The real driver deliberately has no public password getter.
    assert len(calls) == 2
    assert all(call["password"] == credentials.password and call["dsn"] == credentials.dsn for call in calls)
    assert params.tcp_connect_timeout == 2 and params.retry_count == 0
    assert connection.call_timeout == 1234
    for response in (first, second):
        assert response.headers["x-request-id"] == response.json()["request_id"]
        assert response.json()["request_id"] in caplog.text
    assert first.json()["request_id"] != second.json()["request_id"]
    assert credentials.password not in caplog.text and key not in caplog.text and credentials.dsn not in caplog.text


@pytest.mark.parametrize("error_type,code,status", [(a.OracleTimeoutError, "TIMEOUT", 504), (a.SourceUnavailableError, "SOURCE_UNAVAILABLE", 503)])
def test_actual_a_typed_errors_are_mapped(monkeypatch, key, credentials, error_type, code, status):
    def failure(**kwargs):
        raise error_type("private-details " + credentials.password)
    monkeypatch.setattr(a, "count_measurements", failure)
    with TestClient(create_app(Settings(api_key=key, oracle=credentials, development_routes=True))) as client:
        response = client.get("/api/v1/health/echo", headers={"X-API-Key": key})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code and response.json()["data"] is None
    assert credentials.password not in response.text and "private-details" not in response.text


@pytest.mark.parametrize("driver_code,code,status", [("DPY-4024", "TIMEOUT", 504), ("ORA-00942", "SOURCE_UNAVAILABLE", 503)])
def test_real_a_driver_error_mapping_crosses_api_boundary(driver, key, credentials, driver_code, code, status):
    connect, _, _ = driver
    connect.side_effect = oracledb.DatabaseError(SimpleNamespace(full_code=driver_code, message="sensitive"))
    with TestClient(create_app(Settings(api_key=key, oracle=credentials, development_routes=True))) as client:
        response = client.get("/api/v1/health/echo", headers={"X-API-Key": key})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "sensitive" not in response.text


def test_zero_count_is_not_an_error(driver, key, credentials):
    driver[2].fetchone.return_value = (0,)
    with TestClient(create_app(Settings(api_key=key, oracle=credentials, development_routes=True))) as client:
        response = client.get("/api/v1/health/echo", headers={"X-API-Key": key})
    assert response.status_code == 200 and response.json()["data"]["measurement_rows"] == 0


@pytest.mark.parametrize("count", [-1, True, "7", None])
def test_invalid_count_has_no_fallback(key, credentials, count):
    source = OracleSource(credentials, count_function=lambda **kwargs: count)
    with TestClient(create_app(Settings(api_key=key, development_routes=True), source)) as client:
        response = client.get("/api/v1/health/echo", headers={"X-API-Key": key})
    assert response.status_code == 503 and response.json()["data"] is None


def test_credentials_from_environment_only(monkeypatch, key):
    monkeypatch.setenv("TRACE_API_KEY", key)
    monkeypatch.setenv("ORACLE_USER", "synthetic_reader")
    monkeypatch.setenv("ORACLE_PASSWORD", "synthetic-only")
    monkeypatch.setenv("ORACLE_DSN", "localhost/TESTPDB")
    monkeypatch.setenv("ORACLE_CALL_TIMEOUT_MS", "700")
    config = Settings.from_environment()
    assert config.oracle.password == "synthetic-only" and config.call_timeout_ms == 700
    assert key not in repr(config) and "synthetic-only" not in repr(config.oracle)


def test_missing_and_partial_environment_fail_closed(monkeypatch):
    for name in ("TRACE_API_KEY", "ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError):
        create_app()
    monkeypatch.setenv("ORACLE_USER", "synthetic_reader")
    with pytest.raises(ValueError):
        Settings.from_environment()


def test_missing_oracle_settings_are_honest(key):
    with TestClient(create_app(Settings(api_key=key, development_routes=True))) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        response = client.get("/api/v1/health/echo", headers={"X-API-Key": key})
        assert response.status_code == 503 and response.json()["data"] is None


@pytest.mark.parametrize("value", ["SYS", " system ", '"SYSTEM"'])
def test_administrative_oracle_users_rejected(monkeypatch, key, value):
    for name, item in {"TRACE_API_KEY": key, "ORACLE_USER": value, "ORACLE_PASSWORD": "synthetic-only", "ORACLE_DSN": "localhost/TESTPDB"}.items():
        monkeypatch.setenv(name, item)
    with pytest.raises(ValueError):
        Settings.from_environment()
