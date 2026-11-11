"""Single-worker FastAPI factory, server-side credentials and redacted boundaries."""

import logging
import os
import re
import secrets
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app import schemas as s
from .api import make_router, ok, read_count
from .cases import CaseStore, utc_now
from .source import DataSource, Failure, OracleCredentials, OracleSource


logger = logging.getLogger("magna_trace.student_b")


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    oracle: OracleCredentials | None = field(default=None, repr=False)
    development_routes: bool = False
    call_timeout_ms: int = 5000
    connect_timeout_seconds: int = 5
    row_limit: int = 200
    case_capacity: int = 100
    case_ttl_seconds: int = 7200
    max_body_bytes: int = 16384
    requests_per_minute: int = 60

    def __post_init__(self) -> None:
        if not isinstance(self.api_key, str) or not self.api_key.isascii() or not 32 <= len(self.api_key) <= 256 or self.api_key.strip() != self.api_key:
            raise ValueError("TRACE_API_KEY must have 32–256 ASCII characters without surrounding whitespace")
        for name in ("call_timeout_ms", "connect_timeout_seconds", "row_limit", "case_capacity", "case_ttl_seconds", "max_body_bytes", "requests_per_minute"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.row_limit > 200:
            raise ValueError("P0 row_limit cannot exceed 200")

    @classmethod
    def from_environment(cls) -> "Settings":
        values = [os.environ.get(name) for name in ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN")]
        if any(values) and not all(values):
            raise ValueError("Configure ORACLE_USER, ORACLE_PASSWORD and ORACLE_DSN together")
        oracle = OracleCredentials(*values) if all(values) else None
        if oracle and oracle.user.strip().strip('"').upper() in {"SYS", "SYSTEM"}:
            raise ValueError("Use a dedicated SELECT-only Oracle user")
        dev = os.environ.get("TRACE_DEV_ROUTES", "false").lower()
        if dev not in {"true", "false"}:
            raise ValueError("TRACE_DEV_ROUTES must be true or false")
        if os.environ.get("WEB_CONCURRENCY", "1") != "1":
            raise ValueError("RAM cases require a single worker")
        return cls(
            api_key=os.environ.get("TRACE_API_KEY", ""), oracle=oracle, development_routes=dev == "true",
            call_timeout_ms=int(os.environ.get("ORACLE_CALL_TIMEOUT_MS", "5000")),
            connect_timeout_seconds=int(os.environ.get("ORACLE_CONNECT_TIMEOUT_SECONDS", "5")),
        )


def error_response(scope: Scope, failure: Failure) -> JSONResponse:
    candidate = scope.get("b_case_id") or scope.get("path_params", {}).get("case_id")
    case_id = candidate if isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{32}", candidate) else None
    body = s.ErrorResponse(
        request_id=scope["b_request_id"], retrieved_at=utc_now(), case_id=case_id,
        error=s.ErrorInfo(code=failure.code, message=failure.message, scope=failure.scope),
    )
    return JSONResponse(body.model_dump(mode="json", by_alias=True), status_code=failure.http_status,
                        headers={"Retry-After": "60"} if failure.http_status == 429 else None)


class RequestBoundary:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app, self.max_body_bytes = app, max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        scope["b_request_id"] = uuid4().hex
        start, status, response_started = monotonic(), 500, False

        async def tracked_send(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status, response_started = message["status"], True
                message = {**message, "headers": [*message.get("headers", []), (b"x-request-id", scope["b_request_id"].encode()), (b"cache-control", b"no-store")]}
            await send(message)

        try:
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    status = 499
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > self.max_body_bytes:
                    await error_response(scope, Failure("INVALID_SCOPE", "Request body exceeds the configured limit", 413))(scope, receive, tracked_send)
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, tracked_send)
        except Exception as error:
            logger.error("request_failed request_id=%s exception_type=%s", scope["b_request_id"], type(error).__name__)
            if not response_started:
                await error_response(scope, Failure("SOURCE_UNAVAILABLE", "Backend service could not complete the request", 500))(scope, receive, tracked_send)
        finally:
            route = getattr(scope.get("route"), "path", "<unmatched>")
            logger.info("request_id=%s route=%s status=%s duration_ms=%.3f", scope["b_request_id"], route, status, (monotonic() - start) * 1000)


def create_app(settings: Settings | None = None, source: DataSource | None = None, clock: Callable[[], float] = monotonic) -> FastAPI:
    config = settings if settings is not None else Settings.from_environment()
    app = FastAPI(title="MAGNA TRACE — Student B", redirect_slashes=False,
                  docs_url="/docs" if config.development_routes else None, redoc_url=None,
                  openapi_url="/openapi.json" if config.development_routes else None)
    app.state.settings = config
    app.state.source = source if source is not None else OracleSource(config.oracle, call_timeout_ms=config.call_timeout_ms, connect_timeout_seconds=config.connect_timeout_seconds)
    app.state.cases = CaseStore(config.case_capacity, config.case_ttl_seconds, clock)
    header = APIKeyHeader(name="X-API-Key", auto_error=False)
    calls: deque[float] = deque()
    guard = Lock()

    def authenticate(request: Request, key: str | None = Security(header)) -> None:
        if key is None or len(request.headers.getlist("x-api-key")) != 1 or not secrets.compare_digest(key.encode(), config.api_key.encode()):
            raise Failure("UNAUTHORIZED", "Valid connector credentials are required", 401)
        with guard:
            current = clock()
            while calls and calls[0] <= current - 60:
                calls.popleft()
            if len(calls) >= config.requests_per_minute:
                raise Failure("INVALID_SCOPE", "Connector request rate exceeds the configured limit", 429)
            calls.append(current)

    # The integrated chat must enforce the same connector admission limit.
    app.state.authenticate = authenticate

    @app.exception_handler(Failure)
    async def failure_handler(request: Request, error: Failure):
        return error_response(request.scope, error)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, error: RequestValidationError):
        return error_response(request.scope, Failure("INVALID_SCOPE", "Request does not match the agreed scope or schema", 422))

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, error: HTTPException):
        return error_response(request.scope, Failure("INVALID_SCOPE", "Requested route or method is unavailable", error.status_code))

    @app.get("/healthz", response_model=s.Success[dict[str, str]])
    def healthz(request: Request):
        return ok(request, {"process": "running"})

    @app.get("/readyz", response_model=s.Success[dict[str, str]])
    def readyz(request: Request):
        read_count(request)
        return ok(request, {"oracle": "reachable"})

    app.include_router(make_router(authenticate, config.development_routes))
    app.add_middleware(RequestBoundary, max_body_bytes=config.max_body_bytes)
    return app
