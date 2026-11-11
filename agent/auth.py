"""Demo employee sign-in for the web dashboard (fictional company, see employees.json).

Adds a second gate in front of every /api/v1 route: a valid session cookie from
POST /api/v1/auth/login, or the in-process token the agent's own tool calls carry. The
connector key check of student B is unchanged and still applies. /mcp, /healthz and /readyz
are not affected. This is a demo access list, not a corporate identity provider.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ASGIApp, Receive, Scope, Send

from student_b.cases import utc_now
from student_b.main import error_response
from student_b.source import Failure

COOKIE = "trace_session"
INTERNAL_HEADER = "x-trace-internal"
EMPLOYEE_HEADER = "x-trace-employee"
DEFAULT_FILE = Path(__file__).with_name("employees.json")
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}

# Employee of the chat request being served; the toolbox forwards it to its in-process calls
# so a technician answer is attributed to the signed-in person.
current_employee: ContextVar[str | None] = ContextVar("current_employee", default=None)


def hash_password(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, **SCRYPT).hex()


@dataclass(frozen=True)
class Employee:
    employee_id: str
    username: str
    name: str
    role: str
    shift: str
    salt: str
    password_hash: str

    def public(self) -> dict[str, str]:
        return {"employee_id": self.employee_id, "username": self.username, "name": self.name,
                "role": self.role, "shift": self.shift}

    def attribution(self) -> str:
        return f"{self.name} ({self.employee_id}), {self.role}, shift {self.shift} — demo sign-in"


class Directory:
    """Fictional employees allowed to use the dashboard. A missing file means nobody can sign in."""

    def __init__(self, company: str, employees: list[Employee]) -> None:
        self.company = company
        self._by_username = {e.username: e for e in employees}
        self._by_id = {e.employee_id: e for e in employees}
        # Verifying against a dummy hash for unknown users keeps the timing of both failures alike.
        self._dummy = Employee("", "", "", "", "", secrets.token_hex(16), "0" * 64)

    @classmethod
    def load(cls, path: Path = DEFAULT_FILE) -> "Directory":
        if not path.is_file():
            return cls("", [])
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["company"], [Employee(**item) for item in data["employees"]])

    def by_id(self, employee_id: str) -> Employee | None:
        return self._by_id.get(employee_id)

    def verify(self, username: str, password: str) -> Employee | None:
        employee = self._by_username.get(username.strip().lower())
        candidate = employee or self._dummy
        digest = hash_password(password, bytes.fromhex(candidate.salt))
        if secrets.compare_digest(digest, candidate.password_hash) and employee is not None:
            return employee
        return None


class Sessions:
    """In-memory sessions, like the cases: bounded, expiring, lost on restart."""

    def __init__(self, ttl_seconds: int = 8 * 3600, max_sessions: int = 500,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl, self.max, self.clock = ttl_seconds, max_sessions, clock
        self._items: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def create(self, employee_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._purge()
            if len(self._items) >= self.max:
                self._items.pop(min(self._items, key=lambda k: self._items[k][1]))
            self._items[token] = (employee_id, self.clock() + self.ttl)
        return token

    def resolve(self, token: str | None) -> str | None:
        if not token:
            return None
        with self._lock:
            item = self._items.get(token)
            if item is None or item[1] <= self.clock():
                self._items.pop(token, None)
                return None
            return item[0]

    def drop(self, token: str | None) -> None:
        with self._lock:
            self._items.pop(token or "", None)

    def _purge(self) -> None:
        now = self.clock()
        for key in [k for k, (_, expires) in self._items.items() if expires <= now]:
            del self._items[key]


class Throttle:
    """Failed sign-ins: at most 5 per username and 30 overall in a sliding 5-minute window."""

    def __init__(self, per_user: int = 5, overall: int = 30, window: float = 300,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.per_user, self.overall, self.window, self.clock = per_user, overall, window, clock
        self._fails: dict[str, deque[float]] = {}
        self._all: deque[float] = deque()
        self._lock = threading.Lock()

    def _trim(self, q: deque[float]) -> None:
        while q and q[0] <= self.clock() - self.window:
            q.popleft()

    def blocked(self, username: str) -> bool:
        with self._lock:
            for key, history in tuple(self._fails.items()):
                self._trim(history)
                if not history:
                    del self._fails[key]
            q = self._fails.get(username, deque())
            self._trim(self._all)
            return len(q) >= self.per_user or len(self._all) >= self.overall

    def failed(self, username: str) -> None:
        with self._lock:
            now = self.clock()
            self._fails.setdefault(username, deque()).append(now)
            self._all.append(now)


class Auth:
    def __init__(self, directory: Directory, sessions: Sessions | None = None,
                 throttle: Throttle | None = None) -> None:
        self.directory = directory
        self.sessions = sessions or Sessions()
        self.throttle = throttle or Throttle()
        # Random per process and never sent outside it: only the toolbox's in-process calls know it.
        self.internal_token = secrets.token_urlsafe(32)


def _cookie(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            for part in value.decode("latin-1").split(";"):
                key, _, val = part.strip().partition("=")
                if key == COOKIE:
                    return val
    return None


def _header(scope: Scope, wanted: str) -> list[str]:
    return [v.decode("latin-1") for k, v in scope.get("headers", []) if k == wanted.encode()]


class EmployeeGate:
    """Pure ASGI, placed inside student B's RequestBoundary so errors keep B's envelope."""

    PUBLIC = {"/api/v1/auth/login", "/api/v1/auth/info"}

    def __init__(self, app: ASGIApp, auth: Auth) -> None:
        self.app, self.auth = app, auth

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/v1/") or path in self.PUBLIC:
            await self.app(scope, receive, send)
            return
        employee = self._identify(scope)
        if employee is False:
            response = error_response(scope, Failure("UNAUTHORIZED", "Sign in to use MAGNA TRACE", 401))
            await response(scope, receive, send)
            return
        scope["trace_employee"] = employee
        reset = current_employee.set(employee.employee_id if employee else current_employee.get())
        try:
            await self.app(scope, receive, send)
        finally:
            current_employee.reset(reset)

    def _identify(self, scope: Scope) -> Employee | None | bool:
        internal = _header(scope, INTERNAL_HEADER)
        if internal:
            if len(internal) != 1 or not secrets.compare_digest(internal[0], self.auth.internal_token):
                return False
            named = _header(scope, EMPLOYEE_HEADER)
            return self.auth.directory.by_id(named[0]) if len(named) == 1 else None
        employee_id = self.auth.sessions.resolve(_cookie(scope))
        employee = self.auth.directory.by_id(employee_id) if employee_id else None
        return employee if employee is not None else False


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def make_auth_router(auth: Auth, authenticate: Callable[[Request], None]) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth")

    def envelope(request: Request, data: dict | None) -> dict:
        return {"request_id": request.scope["b_request_id"], "retrieved_at": utc_now().isoformat(),
                "status": "ok", "case_id": None, "error": None, "data": data}

    @router.post("/login", operation_id="login")
    def login(body: LoginRequest, request: Request, response: Response):
        authenticate(request)
        username = body.username.strip().lower()
        if auth.throttle.blocked(username):
            raise Failure("UNAUTHORIZED", "Too many failed sign-ins. Wait five minutes and try again.", 429)
        employee = auth.directory.verify(username, body.password)
        if employee is None:
            auth.throttle.failed(username)
            raise Failure("UNAUTHORIZED", "Wrong username or password", 401)
        token = auth.sessions.create(employee.employee_id)
        # HttpOnly: page scripts cannot read it. Not Secure because the demo runs on plain
        # http://127.0.0.1; set it behind HTTPS before any shared deployment.
        response.set_cookie(COOKIE, token, max_age=auth.sessions.ttl, httponly=True,
                            samesite="strict", path="/api/v1")
        return envelope(request, {"employee": employee.public(), "company": auth.directory.company})

    @router.get("/info", operation_id="sign_in_info")
    def info(request: Request):
        # Public part of the sign-in screen: the (fictional) company name only, no employee data.
        authenticate(request)
        return envelope(request, {"company": auth.directory.company})

    @router.get("/me", operation_id="me")
    def me(request: Request):
        authenticate(request)
        employee: Employee | None = request.scope.get("trace_employee")
        if employee is None:
            raise Failure("UNAUTHORIZED", "Sign in to use MAGNA TRACE", 401)
        return envelope(request, {"employee": employee.public(), "company": auth.directory.company})

    @router.post("/logout", operation_id="logout")
    def logout(request: Request, response: Response):
        authenticate(request)
        auth.sessions.drop(_cookie(request.scope))
        response.delete_cookie(COOKIE, path="/api/v1")
        return envelope(request, {"signed_out": True})

    return router
