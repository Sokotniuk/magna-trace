"""Guard the frozen B2 schema and the public tool descriptions."""

import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from backend.app import schemas as s
from contracts.b2.export import REQUESTS, RESPONSES


def test_models_still_generate_exact_frozen_schema():
    path = Path(__file__).resolve().parents[2] / "contracts/b2/schemas.json"
    frozen = json.loads(path.read_text(encoding="utf-8"))
    _, requests = models_json_schema([(model, "validation") for model in REQUESTS])
    _, responses = models_json_schema([(model, "serialization") for model in RESPONSES])
    assert frozen == {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": {**requests["$defs"], **responses["$defs"]}}


def test_openapi_tools_use_key_and_canonical_error_envelope(app):
    spec = app.openapi()
    expected = {
        ("/api/v1/cases", "post"): "open_case",
        ("/api/v1/cases/{case_id}/evidence/{evidence_id}", "get"): "get_evidence",
        ("/api/v1/cases/{case_id}/answers", "post"): "record_answer",
        ("/api/v1/cases/{case_id}/handover", "get"): "get_handover",
        ("/api/v1/stations", "get"): "list_stations",
    }
    for (path, method), operation_id in expected.items():
        operation = spec["paths"][path][method]
        assert operation["operationId"] == operation_id
        assert operation["security"] == [{"APIKeyHeader": []}]
        for status in (401, 404, 409, 413, 422, 429, 500, 503, 504):
            assert operation["responses"][str(status)]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
    assert spec["components"]["securitySchemes"]["APIKeyHeader"] == {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    assert spec["components"]["schemas"]["ErrorResponse"]["properties"]["data"] == {"type": "null", "title": "Data"}


def test_openapi_success_and_request_models_match_b2(app):
    # Compare the published contract, independently of FastAPI's router layout.
    spec = app.openapi()

    def expanded(value, document):
        if isinstance(value, list):
            return [expanded(item, document) for item in value]
        if not isinstance(value, dict):
            if isinstance(value, str) and value.startswith(("#/$defs/", "#/components/schemas/")):
                return value.rsplit("/", 1)[-1]
            return value
        if "$ref" in value:
            resolved = document
            for part in value["$ref"].removeprefix("#/").split("/"):
                resolved = resolved[part]
            return expanded(resolved, document)
        # FastAPI omits null defaults and uses another reference namespace;
        # neither changes validation. Keep all actual field constraints.
        return {key: expanded(item, document) for key, item in value.items()
                if key not in {"title", "$defs"} and not (key == "default" and item is None)}

    expected = {
        "open_case": (s.OpenCaseResponse, s.OpenCaseRequest),
        "get_evidence": (s.GetEvidenceResponse, None),
        "record_answer": (s.RecordAnswerResponse, s.RecordAnswerRequest),
        "get_handover": (s.GetHandoverResponse, None),
        "list_stations": (s.ListStationsResponse, None),
    }
    seen = set()
    for path in spec["paths"].values():
        for operation in path.values():
            operation_id = operation.get("operationId")
            if operation_id not in expected:
                continue
            response, request = expected[operation_id]
            schema = response.model_json_schema(mode="serialization")
            actual = operation["responses"]["200"]["content"]["application/json"]["schema"]
            assert expanded(actual, spec) == expanded(schema, schema)
            if request is not None:
                schema = request.model_json_schema(mode="validation")
                actual = operation["requestBody"]["content"]["application/json"]["schema"]
                assert expanded(actual, spec) == expanded(schema, schema)
            seen.add(operation_id)
    assert seen == set(expected)
