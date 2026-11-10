"""B2 v1 contract based on test1 baseline 2cbfd412. Pending C/D acknowledgement.

No Oracle, mock data or transport implementation belongs in these models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, WithJsonSchema, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128)]
CaseId = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{32}$")]
EvidenceId = Annotated[str, StringConstraints(strict=True, pattern=r"^E-[0-9a-f]{32}-[1-9][0-9]*$")]
ErrorCode = Literal["INVALID_SCOPE", "NO_DATA", "SOURCE_UNAVAILABLE", "TIMEOUT", "EVIDENCE_NOT_FOUND", "EVIDENCE_NOT_IN_CASE", "NOT_COMPARABLE", "CASE_NOT_FOUND_OR_EXPIRED", "UNAUTHORIZED"]
RangeStatus = Literal["ABOVE", "BELOW", "WITHIN_RECORDED_BOUNDS", "NOT_EVALUABLE"]
QualityFlag = Literal["MISSING", "UNPARSEABLE", "LIMIT_UNKNOWN", "LIMIT_INVALID", "PARTIAL_BOUNDS", "UNIT_UNKNOWN", "SEMANTICS_UNKNOWN"]


def reject_float(value: object) -> object:
    if isinstance(value, (float, bool)):
        raise ValueError("Use Decimal or decimal text, not binary float")
    return value


# This is the computed response representation, not A's strict raw-value parser.
DECIMAL_RESPONSE_PATTERN = r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
Exact = Annotated[
    Decimal, BeforeValidator(reject_float), Field(allow_inf_nan=False),
    WithJsonSchema({"type": "string", "pattern": DECIMAL_RESPONSE_PATTERN}, mode="serialization"),
]


class OpenCaseRequest(Model):
    station_number: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=64)]
    from_time: str | None = Field(None, alias="from", max_length=40)
    to_time: str | None = Field(None, alias="to", max_length=40)
    serial_number: Text | None = None

    @model_validator(mode="after")
    def validate_time(self) -> "OpenCaseRequest":
        start = datetime.fromisoformat(self.from_time) if self.from_time else None
        end = datetime.fromisoformat(self.to_time) if self.to_time else None
        if self.from_time == "" or self.to_time == "":
            raise ValueError("Use null or a source-local ISO timestamp")
        if any(value is not None and value.tzinfo is not None for value in (start, end)):
            raise ValueError("Source timezone is unknown; use source-local timestamps without offset")
        if start is not None and end is not None and start > end:
            raise ValueError("from must not exceed to")
        return self


class CaseRequest(Model):
    case_id: CaseId


class EvidenceRequest(CaseRequest):
    evidence_id: EvidenceId


class RecordAnswerRequest(Model):
    question_id: Text
    answer_text: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2000)]


class StationsRequest(Model):
    q: Annotated[str, StringConstraints(strict=True, max_length=64)] | None = None
    limit: int = Field(20, strict=True, ge=1, le=100)


class Scope(OpenCaseRequest):
    row_count: int = Field(ge=0)
    captured_row_count: int = Field(ge=0)
    truncated: bool
    coverage_warnings: tuple[str, ...]


class Finding(Model):
    measurement: str
    raw_value: str | None
    raw_lower: str | None
    raw_upper: str | None
    parsed_value: Exact | None
    deviation: Exact | None = Field(ge=0)
    unit: str | None
    range_status: RangeStatus
    quality_flags: tuple[QualityFlag, ...]
    raw_fail_code: str | None
    evidence_id: EvidenceId
    calculation_evidence_id: EvidenceId


class Hypothesis(Model):
    classification: Literal["HYPOTHESIS"] = "HYPOTHESIS"
    description: str
    supporting_evidence_ids: tuple[EvidenceId, ...]
    counterevidence_ids: tuple[EvidenceId, ...]
    limitations: tuple[str, ...]
    distinguishing_evidence: str


class Assessment(Model):
    label: Literal["UNDETERMINED"] = "UNDETERMINED"
    hypotheses: tuple[Hypothesis, ...]
    unknowns: tuple[str, ...]


class Question(Model):
    kind: Literal["question"] = "question"
    question_id: Text
    text: str
    basis_evidence_ids: tuple[EvidenceId, ...]


class Check(Model):
    kind: Literal["data_check"] = "data_check"
    text: str
    basis_evidence_ids: tuple[EvidenceId, ...]


class Escalation(Model):
    kind: Literal["escalation"] = "escalation"
    text: str
    basis_evidence_ids: tuple[EvidenceId, ...]


Action = Annotated[Question | Check | Escalation, Field(discriminator="kind")]


class Report(Model):
    evidence_id: EvidenceId
    classification: Literal["TECHNICIAN_REPORTED"] = "TECHNICIAN_REPORTED"
    question_id: str
    answer_text: str
    reported_at: datetime
    attribution: str
    conflict_evidence_ids: tuple[EvidenceId, ...]


class Snapshot(Model):
    scope: Scope
    observations_retrieved_at: datetime
    findings: tuple[Finding, ...] = Field(max_length=5)
    additional_evidence_ids: tuple[EvidenceId, ...]
    technician_reports: tuple[Report, ...]
    assessment: Assessment
    next_action: Action
    warnings: tuple[str, ...]


class AnswerSnapshot(Snapshot):
    report_evidence_id: EvidenceId
    change_summary: str


class RawFields(Model):
    MEASURE_VALUE: str | None
    LOWER_LIMIT: str | None
    UPPER_LIMIT: str | None
    UNIT: str | None
    MEASURE_FAIL_CODE: str | None
    station_number: str
    serial_number: str | None
    BOOK_STAMP: str | None


class ObservedEvidence(Model):
    evidence_id: EvidenceId
    classification: Literal["OBSERVED"] = "OBSERVED"
    source_table: Literal["HACKATON.SNO_MEASUREMENT_DATA"]
    scope: OpenCaseRequest
    measurement: str
    raw_fields: RawFields
    row_ordinal: int = Field(ge=1)
    retrieved_at: datetime


class CalculationResult(Model):
    parsed_value: Exact | None
    deviation: Exact | None = Field(ge=0)
    range_status: RangeStatus
    quality_flags: tuple[QualityFlag, ...]


class CalculatedEvidence(Model):
    evidence_id: EvidenceId
    classification: Literal["CALCULATED"] = "CALCULATED"
    input_evidence_ids: tuple[EvidenceId, ...]
    rule: str
    result: CalculationResult
    retrieved_at: datetime


Evidence = Annotated[ObservedEvidence | CalculatedEvidence | Report, Field(discriminator="classification")]


class Handover(Model):
    scope: Scope
    observations_retrieved_at: datetime
    observations: tuple[Finding, ...]
    additional_evidence_ids: tuple[EvidenceId, ...]
    technician_reports: tuple[Report, ...]
    assessment: Assessment
    open_questions: tuple[str, ...]
    gaps: tuple[str, ...]
    next_action: Action


class Station(Model):
    station_number: str
    record_count: int = Field(ge=0)


class Stations(Model):
    stations: tuple[Station, ...]


class ErrorInfo(Model):
    code: ErrorCode
    message: str
    scope: OpenCaseRequest | None = None


T = TypeVar("T")


class Success(Model, Generic[T]):
    request_id: str
    retrieved_at: datetime
    status: Literal["ok"] = "ok"
    case_id: CaseId | None
    data: T
    error: None = None


class ErrorResponse(Model):
    request_id: str
    retrieved_at: datetime
    status: Literal["error"] = "error"
    case_id: CaseId | None
    data: None = None
    error: ErrorInfo


class OpenCaseResponse(Success[Snapshot]): pass
class GetEvidenceResponse(Success[Evidence]): pass
class RecordAnswerResponse(Success[AnswerSnapshot]): pass
class GetHandoverResponse(Success[Handover]): pass
class ListStationsResponse(Success[Stations]):
    # Station discovery is independent of an active diagnostic case.
    case_id: None = None
