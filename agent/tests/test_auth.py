"""Demo employee sign-in (D34): gate, sessions, throttle and in-process token."""

from secrets import token_urlsafe

from fastapi.testclient import TestClient

from agent.auth import COOKIE, Auth, Directory, Employee, Sessions, Throttle, hash_password
from agent.chat import AgentConfig
from agent.main import create_app
from student_b.main import Settings
from student_b.tests.synthetic import SyntheticSource

PASSWORD = token_urlsafe(12)


def directory() -> Directory:
    salt = bytes(range(16))
    return Directory("Synthetic Company", [Employee("SYN-0002", "synthetic.lead", "Synthetic Lead", "Shift lead", "B",
                                                    salt.hex(), hash_password(PASSWORD, salt))])


def client(auth: Auth | None = None):
    key = token_urlsafe(32)
    app = create_app(Settings(api_key=key, requests_per_minute=1000), SyntheticSource(),
                     AgentConfig(models=(), expected_routes=frozenset(), allow_real_data=False, rate_limit_waits=()),
                     None, auth=auth or Auth(directory()))
    return TestClient(app, raise_server_exceptions=False), {"X-API-Key": key}


def login(c, headers, username="synthetic.lead", password=PASSWORD):
    return c.post("/api/v1/auth/login", json={"username": username, "password": password}, headers=headers)


def test_every_api_route_needs_a_session_but_health_does_not():
    c, headers = client()
    for method, path in [("get", "/api/v1/stations"), ("post", "/api/v1/cases"), ("get", "/api/v1/auth/me"),
                         ("post", "/api/v1/chat")]:
        response = getattr(c, method)(path, headers=headers, **({"json": {}} if method == "post" else {}))
        assert response.status_code == 401, path
        body = response.json()
        assert body["status"] == "error" and body["error"]["code"] == "UNAUTHORIZED" and body["data"] is None
    assert c.get("/healthz").status_code == 200
    info = c.get("/api/v1/auth/info", headers=headers)
    assert info.status_code == 200 and info.json()["data"] == {"company": "Synthetic Company"}
    assert c.get("/api/v1/auth/info").status_code == 401  # still behind the connector key


def test_login_me_logout_and_cookie_flags():
    c, headers = client()
    response = login(c, headers)
    assert response.status_code == 200
    assert response.json()["data"]["employee"] == {"employee_id": "SYN-0002", "username": "synthetic.lead",
                                                   "name": "Synthetic Lead", "role": "Shift lead", "shift": "B"}
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1" in cookie
    assert "password" not in response.text and "salt" not in response.text
    assert c.get("/api/v1/auth/me", headers=headers).json()["data"]["employee"]["name"] == "Synthetic Lead"
    assert c.get("/api/v1/stations", headers=headers).status_code == 200
    assert c.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert c.get("/api/v1/stations", headers=headers).status_code == 401


def test_session_does_not_replace_the_connector_key():
    c, headers = client()
    assert login(c, headers).status_code == 200
    assert c.get("/api/v1/stations").status_code == 401
    assert login(c, {}).status_code == 401


def test_wrong_password_and_unknown_user_look_the_same():
    c, headers = client()
    wrong, unknown = login(c, headers, password="nope"), login(c, headers, username="nobody")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"] == "Wrong username or password"
    assert COOKIE not in wrong.headers.get("set-cookie", "")


def test_throttle_blocks_after_five_failures_even_with_the_right_password():
    c, headers = client()
    for _ in range(5):
        assert login(c, headers, password="nope").status_code == 401
    blocked = login(c, headers)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "UNAUTHORIZED"


def test_forged_internal_token_or_session_is_rejected():
    c, headers = client()
    assert c.get("/api/v1/stations", headers={**headers, "X-Trace-Internal": "guess"}).status_code == 401
    c.cookies.set(COOKIE, token_urlsafe(32), path="/api/v1")
    assert c.get("/api/v1/stations", headers=headers).status_code == 401


def test_sessions_expire_and_throttle_window_slides():
    now = [0.0]
    sessions = Sessions(ttl_seconds=10, clock=lambda: now[0])
    token = sessions.create("SYN-0002")
    assert sessions.resolve(token) == "SYN-0002"
    now[0] = 10.0
    assert sessions.resolve(token) is None
    throttle = Throttle(per_user=2, window=60, clock=lambda: now[0])
    throttle.failed("a"), throttle.failed("a")
    assert throttle.blocked("a") and not throttle.blocked("b")
    now[0] = 71.0
    assert not throttle.blocked("a")


def test_missing_employee_file_means_nobody_can_sign_in(tmp_path):
    empty = Directory.load(tmp_path / "absent.json")
    c, headers = client(Auth(empty))
    assert login(c, headers).status_code == 401
