"""MAGNA TRACE backend: FastAPI app with REST routes and the MCP endpoint at /mcp.

Run from the project root (one worker; cases will live in memory):
    python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
"""

import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import oracle_repo, services
from .config import settings
from .mcp_server import mcp
from .schemas import error, new_request_id, request_id_var

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("trace")

PUBLIC_PATHS = {"/healthz"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="MAGNA TRACE", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def request_id_auth_and_log(request: Request, call_next):
    request_id = new_request_id()
    request_id_var.set(request_id)
    started = time.perf_counter()

    if request.url.path not in PUBLIC_PATHS:
        supplied = request.headers.get(settings.api_key_header, "")
        if not hmac.compare_digest(supplied.encode(), settings.api_key.encode()):
            response = JSONResponse(error("UNAUTHORIZED", "Missing or invalid API key."), status_code=401)
            _log(request, response.status_code, started, request_id)
            response.headers["X-Request-ID"] = request_id
            return response

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    _log(request, response.status_code, started, request_id)
    return response


def _log(request: Request, status: int, started: float, request_id: str) -> None:
    # Never log headers, keys or bodies (AGENTS.md I-11).
    ms = (time.perf_counter() - started) * 1000
    log.info("request_id=%s %s %s -> %s (%.0f ms)", request_id, request.method, request.url.path, status, ms)


# --- REST routes (must be declared before the MCP mount below) -------------

@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> JSONResponse:
    try:
        oracle_repo.ping()
    except (oracle_repo.SourceUnavailable, oracle_repo.SourceTimeout):
        return JSONResponse(error("SOURCE_UNAVAILABLE", "Oracle is not reachable."), status_code=503)
    return JSONResponse({"status": "ok"})


_HTTP_STATUS = {
    "INVALID_SCOPE": 400, "NO_DATA": 404, "CASE_NOT_FOUND_OR_EXPIRED": 404,
    "EVIDENCE_NOT_FOUND": 404, "EVIDENCE_NOT_IN_CASE": 404, "NOT_COMPARABLE": 422,
    "SOURCE_UNAVAILABLE": 503, "TIMEOUT": 504, "UNAUTHORIZED": 401,
}


def _rest(envelope: dict) -> JSONResponse:
    """Same envelope as the MCP tools; the HTTP status reflects the error code."""
    code = (envelope.get("error") or {}).get("code")
    return JSONResponse(envelope, status_code=_HTTP_STATUS.get(code, 200))


class OpenCaseRequest(BaseModel):
    station_number: str
    time_from: str | None = None
    time_to: str | None = None
    serial_number: str | None = None


@app.get("/api/v1/health/echo")
def rest_health_echo() -> JSONResponse:
    return _rest(services.health_echo())


@app.get("/api/v1/stations")
def rest_list_stations() -> JSONResponse:
    return _rest(services.list_stations())


@app.post("/api/v1/cases")
def rest_open_case(body: OpenCaseRequest) -> JSONResponse:
    return _rest(services.open_case(body.station_number, body.time_from, body.time_to, body.serial_number))


class RecordAnswerRequest(BaseModel):
    question_id: str
    answer_text: str
    answer_kind: str | None = None


@app.post("/api/v1/cases/{case_id}/answers")
def rest_record_answer(case_id: str, body: RecordAnswerRequest) -> JSONResponse:
    return _rest(services.record_answer(case_id, body.question_id, body.answer_text, body.answer_kind))


@app.get("/api/v1/cases/{case_id}/handover")
def rest_get_handover(case_id: str) -> JSONResponse:
    return _rest(services.get_handover(case_id))


@app.get("/api/v1/cases/{case_id}/evidence/{evidence_id}")
def rest_get_evidence(case_id: str, evidence_id: str) -> JSONResponse:
    return _rest(services.get_evidence(case_id, evidence_id))


# --- MCP endpoint: serves /mcp. Mounted last so it does not shadow REST routes.
app.mount("/", mcp.streamable_http_app())
