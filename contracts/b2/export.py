"""Run from any directory: python contracts/b2/export.py."""
import json
import sys
from pathlib import Path
from pydantic.json_schema import models_json_schema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.app import schemas as s

REQUESTS = [s.OpenCaseRequest, s.CaseRequest, s.EvidenceRequest, s.RecordAnswerRequest, s.StationsRequest]
RESPONSES = [s.OpenCaseResponse, s.GetEvidenceResponse, s.RecordAnswerResponse, s.GetHandoverResponse, s.ListStationsResponse, s.ErrorResponse]

def export():
    _, request_schema = models_json_schema([(model, "validation") for model in REQUESTS])
    _, response_schema = models_json_schema([(model, "serialization") for model in RESPONSES])
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": {**request_schema["$defs"], **response_schema["$defs"]}}
    # Serialization mode is essential: Decimal response fields accept strings, never floats.
    (Path(__file__).parent / "schemas.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    export()
