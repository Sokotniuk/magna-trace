"""Read-only D5 smoke checks of a running local FastAPI and live Vite proxy."""

import argparse
from datetime import datetime, timedelta
from http.client import HTTPConnection, HTTPException
import json
from typing import Any, Callable


ECHO = "/api/v1/health/echo"
ENVELOPE_KEYS = {"request_id", "retrieved_at", "status", "case_id", "data", "error"}
UNAVAILABLE = {(503, "SOURCE_UNAVAILABLE"), (504, "TIMEOUT")}
MAX_BODY_BYTES = 64 * 1024


class Failed(Exception):
    """A response violated an expectation. Messages must contain no payload data."""


class Pending(Exception):
    """A live dependency prevented verification."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def get_envelope(port: int, route: str) -> tuple[int, dict[str, Any]]:
    # HTTPConnection neither follows redirects nor reads proxy/credential env vars.
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", route, headers={"Accept": "application/json"})
        response = connection.getresponse()
        status = response.status
        if response.getheader("X-Trace-Mock") is not None:
            raise Pending(f"HTTP {status}; marked mock response excluded from live checks")
        raw = response.read(MAX_BODY_BYTES + 1)
    except PermissionError:
        raise Pending("loopback access blocked") from None
    except OSError:
        raise Pending("local service unreachable, disconnected, or timed out") from None
    except HTTPException:
        raise Failed("invalid or incomplete HTTP response") from None
    finally:
        connection.close()

    require(len(raw) <= MAX_BODY_BYTES, f"HTTP {status}; response exceeded smoke check size limit")
    try:
        body = json.loads(raw)
    except (ValueError, RecursionError):
        raise Failed(f"HTTP {status}; expected a JSON envelope") from None
    try:
        validate_envelope(body)
    except Failed as error:
        raise Failed(f"HTTP {status}; {error}") from None
    return status, body


def validate_envelope(body: Any) -> None:
    require(isinstance(body, dict) and body.keys() == ENVELOPE_KEYS, "invalid envelope fields")
    require(isinstance(body["request_id"], str) and bool(body["request_id"].strip()), "invalid request_id")
    require(body["case_id"] is None, "non-case endpoint must return case_id=null")
    retrieved_at = body["retrieved_at"]
    require(isinstance(retrieved_at, str), "invalid retrieved_at")
    try:
        timestamp = datetime.fromisoformat(retrieved_at.removesuffix("Z") + "+00:00"
                                           if retrieved_at.endswith("Z") else retrieved_at)
    except ValueError:
        raise Failed("invalid retrieved_at") from None
    require(timestamp.utcoffset() == timedelta(0), "retrieved_at must be UTC")

    if body["status"] == "ok":
        require(isinstance(body["data"], dict) and body["error"] is None, "invalid success data/error fields")
        return

    require(body["status"] == "error", "invalid envelope status")
    require(body["data"] is None, "error carried non-null data")
    error = body["error"]
    require(isinstance(error, dict) and error.keys() <= {"code", "message", "scope"}, "invalid error fields")
    require(all(isinstance(error.get(key), str) and error[key].strip() for key in ("code", "message")),
            "invalid error code or message")
    # A B2 error may describe the queried scope, but never include findings or rows.
    scope = error.get("scope")
    if scope is not None:
        require(isinstance(scope, dict) and scope.keys() <= {"station_number", "from", "to", "serial_number"}
                and isinstance(scope.get("station_number"), str) and bool(scope["station_number"])
                and all(value is None or isinstance(value, str) for value in scope.values()),
                "invalid error scope fields")


def available_data(port: int, route: str) -> dict[str, Any]:
    status, body = get_envelope(port, route)
    if body["status"] == "error" and (status, body["error"]["code"]) in UNAVAILABLE:
        # This validates the error contract, not availability of the operation.
        raise Pending(f"HTTP {status} {body['error']['code']}; valid error envelope, data=null")
    require(status == 200 and body["status"] == "ok", f"HTTP {status}; expected HTTP 200 with an ok envelope")
    return body["data"]


def check_health(port: int) -> str:
    available_data(port, "/healthz")
    return "HTTP 200; valid success envelope"


def check_readiness(port: int) -> str:
    data = available_data(port, "/readyz")
    require(data.get("oracle") == "reachable", "HTTP 200; readiness did not confirm Oracle reachable")
    return "HTTP 200; backend reports Oracle reachable"


def check_no_key(port: int) -> str:
    status, body = get_envelope(port, ECHO)
    require(status == 401 and body["status"] == "error" and body["error"]["code"] == "UNAUTHORIZED",
            f"HTTP {status}; expected 401 UNAUTHORIZED without X-API-Key")
    return "HTTP 401 UNAUTHORIZED; valid error envelope, data=null"


def check_echo(port: int) -> str:
    data = available_data(port, ECHO)
    count = data.get("measurement_rows")
    require(type(count) is int and count >= 0, "HTTP 200; measurement_rows must be a nonnegative integer")
    return f"HTTP 200; Oracle aggregate measurement_rows={count} reported by backend"


def check_stations(port: int) -> str:
    data = available_data(port, "/api/v1/stations")
    require(data.keys() == {"stations"} and isinstance(data["stations"], list), "HTTP 200; invalid stations payload")
    require(all(isinstance(station, dict) and station.keys() == {"station_number", "record_count"}
                and isinstance(station["station_number"], str)
                and type(station["record_count"]) is int and station["record_count"] >= 0
                for station in data["stations"]), "HTTP 200; invalid station entry")
    return "HTTP 200; valid station list, identities withheld"


def run_check(name: str, check: Callable[[int], str], port: int) -> str:
    try:
        detail = check(port)
        status = "PASSED"
    except Pending as error:
        status, detail = "PENDING", str(error)
    except Failed as error:
        status, detail = "FAILED", str(error)
    print(f"{status} {name}: {detail}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-port", type=int, default=8000, help="loopback FastAPI port (default: 8000)")
    parser.add_argument("--proxy-port", type=int, default=5173, help="loopback live Vite port (default: 5173)")
    args = parser.parse_args()
    if not all(1 <= port <= 65535 for port in (args.backend_port, args.proxy_port)):
        parser.error("ports must be between 1 and 65535")

    print("D5 live smoke — local GET requests only; no credentials or raw payloads logged")
    checks = [
        ("FastAPI GET /healthz", check_health, args.backend_port),
        ("FastAPI GET /readyz", check_readiness, args.backend_port),
        ("FastAPI GET /api/v1/health/echo (no key)", check_no_key, args.backend_port),
        ("Vite GET /api/v1/health/echo", check_echo, args.proxy_port),
        ("Vite GET /api/v1/stations", check_stations, args.proxy_port),
    ]
    results = [run_check(*check) for check in checks]
    print("Summary: " + ", ".join(f"{status}={results.count(status)}" for status in ("PASSED", "FAILED", "PENDING")))
    return 1 if "FAILED" in results else 2 if "PENDING" in results else 0


if __name__ == "__main__":
    raise SystemExit(main())
