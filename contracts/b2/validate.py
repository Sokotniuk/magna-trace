"""Validate all synthetic fixtures and cross-response invariants; no Oracle needed."""
import json
import sys
from decimal import Decimal
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from backend.app import schemas as s

def validate():
    schema = json.loads((HERE / "schemas.json").read_text())
    examples = json.loads((HERE / "examples.json").read_text())
    Draft202012Validator.check_schema(schema)
    checked = 0
    for item in examples["cases"]:
        for side in ("request", "response"):
            spec = item.get(side)
            if not spec:
                continue
            validator = Draft202012Validator({"$ref": f"#/$defs/{spec['model']}", "$defs": schema["$defs"]}, format_checker=FormatChecker())
            validator.validate(spec["body"])
            model = getattr(s, spec["model"])
            model.model_validate(spec["body"])
            checked += 1
    successes = {x["name"]: x["response"]["body"] for x in examples["cases"] if x["http_status"] == 200}
    before = successes["open_case"]["data"]
    after = successes["record_answer"]["data"]
    assert before["findings"] == after["findings"]
    assert before["assessment"] == after["assessment"]
    assert before["next_action"]["kind"] == "question" and after["next_action"]["kind"] == "data_check"
    assert before["findings"][0]["deviation"] == "0.5"  # hand arithmetic: 10.5 - 10.0
    assert before["findings"][1]["range_status"] == "WITHIN_RECORDED_BOUNDS"
    assert before["findings"][1]["raw_fail_code"] == "1001"
    assert "SEMANTICS_UNKNOWN" in before["findings"][2]["quality_flags"]
    assert successes["get_handover"]["data"]["technician_reports"] == after["technician_reports"]
    evidence = {body["data"]["evidence_id"]: body["data"] for name, body in successes.items() if name.startswith("get_evidence")}
    for finding in before["findings"]:
        assert finding["evidence_id"] in evidence and finding["calculation_evidence_id"] in evidence
    assert after["report_evidence_id"] in evidence
    errors = [x for x in examples["cases"] if x["http_status"] != 200]
    assert len({x["response"]["body"]["error"]["code"] for x in errors}) == 9
    assert all(x["response"]["body"]["data"] is None for x in errors)
    # Response JSON schemas must reject binary JSON numbers for exact decimal fields.
    validator = Draft202012Validator({"$ref": "#/$defs/OpenCaseResponse", "$defs": schema["$defs"]})
    mutated = json.loads(json.dumps(successes["open_case"]))
    mutated["data"]["findings"][0]["parsed_value"] = 10.5
    assert not validator.is_valid(mutated)
    # Regression: SDK serialization may emit 1E-21; generated wire schemas must accept it.
    for text in ("1E-21", "1e+3", "0.000000000000000000001"):
        payload = json.loads(json.dumps(successes["open_case"]))
        payload["data"]["findings"][0]["parsed_value"] = text
        payload["data"]["findings"][0]["deviation"] = text
        validator.validate(payload)
        serialized = s.OpenCaseResponse.model_validate(payload).model_dump(mode="json", by_alias=True)
        validator.validate(serialized)
        assert Decimal(serialized["data"]["findings"][0]["deviation"]) == Decimal(text)
    for text in ("NaN", "Infinity", "1e", "abc", ""):
        payload = json.loads(json.dumps(successes["open_case"]))
        payload["data"]["findings"][0]["parsed_value"] = text
        assert not validator.is_valid(payload)
    stations = successes["list_stations"]
    assert stations["case_id"] is None
    station_validator = Draft202012Validator({"$ref": "#/$defs/ListStationsResponse", "$defs": schema["$defs"]})
    wrong_station_case = {**stations, "case_id": successes["open_case"]["case_id"]}
    assert not station_validator.is_valid(wrong_station_case)
    try:
        s.ListStationsResponse.model_validate(wrong_station_case)
    except ValidationError:
        pass
    else:
        raise AssertionError("Station listing must not be assigned to a case")
    for code in ("EVIDENCE_NOT_FOUND", "EVIDENCE_NOT_IN_CASE"):
        fixture = next(x for x in errors if x["response"]["body"]["error"]["code"] == code)
        params = fixture["request"]["body"]
        assert fixture["method"] == "GET"
        assert fixture["path"] == f"/api/v1/cases/{params['case_id']}/evidence/{params['evidence_id']}"
    for invalid in ({"station_number": "x", "from": "bad"}, {"station_number": "x", "from": "2026-01-01T00:00:00Z"}):
        try:
            s.OpenCaseRequest.model_validate(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError("Invalid time scope accepted")
    print(f"PASS: {checked} request/response fixtures; 9 error codes; immutable findings; evidence references; decimal strings including exponents; null station case; evidence error routes; source-time validation")

if __name__ == "__main__":
    validate()
