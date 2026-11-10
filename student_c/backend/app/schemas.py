"""Response envelope shared by REST routes and MCP tools (architecture §3)."""

import contextvars
import uuid
from datetime import datetime, timezone

# Canonical error codes. Add none without a contract change.
ERROR_CODES = {
    "INVALID_SCOPE",
    "NO_DATA",
    "SOURCE_UNAVAILABLE",
    "TIMEOUT",
    "EVIDENCE_NOT_FOUND",
    "EVIDENCE_NOT_IN_CASE",
    "NOT_COMPARABLE",
    "CASE_NOT_FOUND_OR_EXPIRED",
    "UNAUTHORIZED",
}

# Set per HTTP request by the middleware in main.py, so the ID in a tool result
# is the same one written to the backend log.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


# Language models sometimes re-type IDs with typographic dashes (U+2011 non-breaking hyphen,
# en/em dash, minus sign) or wrap them in quotes/backticks. IDs only ever contain ASCII
# letters, digits and '-', so mapping these back is lossless and never matches a different ID.
_DASHES = str.maketrans({c: "-" for c in "‐‑‒–—―−﹘﹣－"})


def normalize_id(raw: str | None) -> str:
    """Canonical form of a case, evidence or question ID as supplied by a client."""
    return (raw or "").translate(_DASHES).strip().strip("`'\"").replace(" ", "").upper()


def new_request_id() -> str:
    return uuid.uuid4().hex


def current_request_id() -> str:
    return request_id_var.get() or new_request_id()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ok(data: dict, case_id: str | None = None) -> dict:
    return {
        "request_id": current_request_id(),
        "retrieved_at": utc_now(),
        "status": "ok",
        "case_id": case_id,
        "data": data,
        "error": None,
    }


def error(code: str, message: str, case_id: str | None = None) -> dict:
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code {code}")
    return {
        "request_id": current_request_id(),
        "retrieved_at": utc_now(),
        "status": "error",
        "case_id": case_id,
        "data": None,
        "error": {"code": code, "message": message},
    }
