"""Acceptance client for an already running backend on the local Oracle host.

No mock source, Oracle credentials, raw row output or tunnel configuration here.
HTTP timeouts do not cancel an Oracle call already executing in the server.
"""

import argparse
import http.client
import json
import os
from urllib.parse import urlsplit

from backend.app import schemas as s


class CheckError(RuntimeError):
    """Public, redacted acceptance failure."""


class Client:
    def __init__(self, base_url: str, key: str, timeout: int = 15) -> None:
        url = urlsplit(base_url)
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
            raise CheckError("Use a loopback http://host:port URL with no path or credentials")
        if not key or not key.isascii() or not 32 <= len(key) <= 256 or key.strip() != key:
            raise CheckError("Configure the server-side TRACE_API_KEY for this client")
        self.host, self.port, self.key, self.timeout = url.hostname, url.port or 8000, key, timeout

    def request(self, method: str, path: str, model: type, *, body: dict | None = None,
                authorized: bool = True, expected_status: int = 200) -> dict:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["X-API-Key"] = self.key
        try:
            connection.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
            response = connection.getresponse()
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise CheckError("Response exceeds acceptance-client size limit")
            payload = json.loads(raw)
            model.model_validate(payload)
            if response.status != expected_status:
                raise CheckError("Unexpected HTTP status during acceptance check")
            if response.getheader("X-Request-ID") != payload["request_id"] or response.getheader("Cache-Control") != "no-store":
                raise CheckError("Response metadata does not match the API envelope")
            return payload
        except CheckError:
            raise
        except Exception:
            raise CheckError("HTTP or schema check failed; inspect redacted server logs") from None
        finally:
            connection.close()


def run_checks(client: Client, scope: dict, *, check_echo: bool = False, expected_count: int | None = None) -> None:
    client.request("GET", "/healthz", s.Success[dict[str, str]])
    client.request("GET", "/readyz", s.Success[dict[str, str]])
    denied = client.request("GET", "/api/v1/stations", s.ErrorResponse, authorized=False, expected_status=401)
    if denied["error"]["code"] != "UNAUTHORIZED":
        raise CheckError("Missing credential did not fail closed")
    client.request("GET", "/api/v1/stations?limit=20", s.ListStationsResponse)
    if check_echo:
        counts = [client.request("GET", "/api/v1/health/echo", s.Success[dict[str, int]])["data"]["measurement_rows"] for _ in range(2)]
        if expected_count is not None and counts != [expected_count, expected_count]:
            raise CheckError("Echo differs from independently supplied count")
    previous = None
    for index in range(2):
        opened = client.request("POST", "/api/v1/cases", s.OpenCaseResponse, body=scope)
        case_id, before = opened["case_id"], opened["data"]
        if len(before["findings"]) < 3:
            raise CheckError("Choose a verified scope containing at least three findings")
        prefix = f"/api/v1/cases/{case_id}"
        captured = {}
        for finding in before["findings"]:
            for ref in (finding["evidence_id"], finding["calculation_evidence_id"]):
                captured[ref] = client.request("GET", prefix + "/evidence/" + ref, s.GetEvidenceResponse)["data"]
        if previous is not None:
            foreign = client.request("GET", prefix + "/evidence/" + previous, s.ErrorResponse, expected_status=404)
            if foreign["error"]["code"] != "EVIDENCE_NOT_IN_CASE":
                raise CheckError("Foreign evidence was not rejected")
        previous = before["findings"][0]["evidence_id"]
        request = {"question_id": before["next_action"]["question_id"], "answer_text": (
            "Acceptance test: station context is not independently confirmed."
            if index == 0 else "Acceptance test: additional station context remains unknown."
        )}
        updated = client.request("POST", prefix + "/answers", s.RecordAnswerResponse, body=request)["data"]
        if updated["findings"] != before["findings"] or updated["assessment"]["label"] != "UNDETERMINED" or updated["next_action"]["kind"] == "question":
            raise CheckError("Answer changed observations or violated the P0 diagnostic policy")
        ref = updated["report_evidence_id"]
        report = client.request("GET", prefix + "/evidence/" + ref, s.GetEvidenceResponse)["data"]
        if report["classification"] != "TECHNICIAN_REPORTED" or report["answer_text"] != request["answer_text"]:
            raise CheckError("Technician report was not captured")
        handover = client.request("GET", prefix + "/handover", s.GetHandoverResponse)["data"]
        if handover["observations"] != before["findings"] or handover["technician_reports"] != updated["technician_reports"]:
            raise CheckError("Handover does not reflect the saved case")
        ref = before["findings"][0]["evidence_id"]
        if client.request("GET", prefix + "/evidence/" + ref, s.GetEvidenceResponse)["data"] != captured[ref]:
            raise CheckError("Captured evidence was modified")
        repeated = client.request("POST", prefix + "/answers", s.ErrorResponse, body=request, expected_status=409)
        if repeated["error"]["code"] != "INVALID_SCOPE":
            raise CheckError("Repeated answer was not rejected")
    print("PASS: two HTTP API journeys, evidence, answers, handover, isolation and auth. Independent SQL and C/D acceptance are separate.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--station", required=True)
    parser.add_argument("--serial")
    parser.add_argument("--from", dest="from_time")
    parser.add_argument("--to", dest="to_time")
    parser.add_argument("--check-echo", action="store_true")
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    try:
        if args.expected_count is not None and (not args.check_echo or args.expected_count < 0):
            raise CheckError("A nonnegative independent count requires --check-echo")
        scope = s.OpenCaseRequest(station_number=args.station, serial_number=args.serial,
                                  from_time=args.from_time, to_time=args.to_time)
        run_checks(Client(args.base_url, os.environ.get("TRACE_API_KEY", "")),
                   scope.model_dump(mode="json", by_alias=True), check_echo=args.check_echo,
                   expected_count=args.expected_count)
    except (CheckError, ValueError):
        print("FAIL: acceptance check incomplete; verify configuration and redacted server logs")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
