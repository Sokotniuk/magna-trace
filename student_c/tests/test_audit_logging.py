"""Legacy fallback logging regression, synthetic failure, no Oracle connection."""
def test_connection_failure_does_not_log_settings_or_driver_message(monkeypatch, caplog):
    for name in ("TRACE_API_KEY", "ORACLE_USER", "ORACLE_PASSWORD"):
        monkeypatch.setenv(name, "synthetic-only")
    from backend.app import oracle_repo
    import oracledb
    import pytest
    from dataclasses import replace
    monkeypatch.setattr(oracle_repo, "settings", replace(oracle_repo.settings,
        oracle_user="AUDIT_PRIVATE_USER", oracle_dsn="AUDIT_PRIVATE_DSN"))
    def fail(**kwargs):
        raise oracledb.DatabaseError("AUDIT_PRIVATE_DRIVER_TEXT")
    monkeypatch.setattr(oracledb, "connect", fail)
    with pytest.raises(oracle_repo.SourceUnavailable):
        oracle_repo.count_measurements()
    assert "AUDIT_PRIVATE" not in caplog.text
