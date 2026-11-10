"""Settings from environment variables only. Secrets never live in code or Git."""

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_key_header: str
    oracle_user: str
    oracle_password: str
    oracle_dsn: str
    oracle_call_timeout_ms: int


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"[config] Missing environment variable {name}. See docs/run_backend.md.")
    return value


def load_settings() -> Settings:
    return Settings(
        api_key=_required("TRACE_API_KEY"),
        api_key_header=os.environ.get("TRACE_API_KEY_HEADER", "X-API-Key"),
        oracle_user=_required("ORACLE_USER"),
        oracle_password=_required("ORACLE_PASSWORD"),
        oracle_dsn=os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1"),
        oracle_call_timeout_ms=int(os.environ.get("ORACLE_CALL_TIMEOUT_MS", "10000")),
    )


settings = load_settings()
