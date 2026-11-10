"""Run: python -m student_b.tests.smoke. Synthetic, no Oracle or external API."""

import json
from pathlib import Path
from secrets import token_urlsafe

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from student_b.main import Settings, create_app
from student_b.source import Failure
from .synthetic import SyntheticSource


def run() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "contracts/b2/schemas.json"
    schema = json.loads(schema_path.read_text())
    source = SyntheticSource()
    key = token_urlsafe(32)
    headers = {"X-API-Key": key}

    def checked(response, model: str, status: int = 200):
        assert response.status_code == status, f"Expected HTTP {status}, got {response.status_code}"
        payload = response.json()
        Draft202012Validator(
            {"$ref": f"#/$defs/{model}", "$defs": schema["$defs"]}, format_checker=FormatChecker(),
        ).validate(payload)
        assert response.headers["x-request-id"] == payload["request_id"]
        return payload

    def error(response, code: str, status: int):
        payload = checked(response, "ErrorResponse", status)
        assert payload["data"] is None and payload["error"]["code"] == code
        return payload

    opened_cases = []
    with TestClient(create_app(Settings(api_key=key), source)) as client:
        checked(client.get("/api/v1/stations", headers=headers), "ListStationsResponse")
        for text in ("A fixture context change was reported.", "The technician reports a different station setup before these tests."):
            opened = checked(client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers), "OpenCaseResponse")
            opened_cases.append(opened)
            scope = f"/api/v1/cases/{opened['case_id']}"
            findings = opened["data"]["findings"]
            assert len(findings) == 3
            assert findings[0]["deviation"] == "0.5"  # independently specified 10.5 - 10.0
            assert findings[1]["range_status"] == "WITHIN_RECORDED_BOUNDS" and findings[1]["raw_fail_code"] == "1001"
            for finding in findings:
                for name in ("evidence_id", "calculation_evidence_id"):
                    checked(client.get(scope + "/evidence/" + finding[name], headers=headers), "GetEvidenceResponse")
            body = {"question_id": opened["data"]["next_action"]["question_id"], "answer_text": text}
            recorded = checked(client.post(scope + "/answers", json=body, headers=headers), "RecordAnswerResponse")
            assert recorded["data"]["findings"] == findings
            assert recorded["data"]["assessment"]["label"] == "UNDETERMINED"
            assert recorded["data"]["next_action"]["kind"] == "data_check"
            report = checked(client.get(scope + "/evidence/" + recorded["data"]["report_evidence_id"], headers=headers), "GetEvidenceResponse")
            assert report["data"]["answer_text"] == text
            handover = checked(client.get(scope + "/handover", headers=headers), "GetHandoverResponse")
            assert handover["data"]["technician_reports"] == [report["data"]]
            assert handover["data"]["observations"] == findings
            error(client.post(scope + "/answers", json=body, headers=headers), "INVALID_SCOPE", 409)
        assert opened_cases[0]["case_id"] != opened_cases[1]["case_id"]
        one = f"/api/v1/cases/{opened_cases[0]['case_id']}"
        error(client.get("/api/v1/stations"), "UNAUTHORIZED", 401)
        error(client.get("/api/v1/stations", headers={"X-API-Key": "wrong"}), "UNAUTHORIZED", 401)
        empty = error(client.post("/api/v1/cases", json={"station_number": "ABSENT"}, headers=headers), "NO_DATA", 404)
        assert empty["error"]["scope"]["station_number"] == "ABSENT"
        error(client.get("/api/v1/cases/unknown/handover", headers=headers), "CASE_NOT_FOUND_OR_EXPIRED", 404)
        error(client.get(one + "/evidence/invented", headers=headers), "EVIDENCE_NOT_FOUND", 404)
        foreign = opened_cases[1]["data"]["findings"][0]["evidence_id"]
        error(client.get(one + "/evidence/" + foreign, headers=headers), "EVIDENCE_NOT_IN_CASE", 404)
        for code, status in (("SOURCE_UNAVAILABLE", 503), ("TIMEOUT", 504)):
            source.failure = Failure(code, "Synthetic source failure", status)
            error(client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers), code, status)
        # Previously captured evidence remains available; failed fresh reads return no fallback.
        captured = checked(client.get(one + "/evidence/" + opened_cases[0]["data"]["findings"][0]["evidence_id"], headers=headers), "GetEvidenceResponse")
        assert captured["data"]["raw_fields"]["MEASURE_VALUE"] == "10.5"
    print("PASS local synthetic smoke: two complete journeys, B2 schemas, evidence, answers, handover, auth and source-error paths. No live Oracle or external API was used.")


if __name__ == "__main__":
    run()
