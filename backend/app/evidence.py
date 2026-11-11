"""Immutable case-local evidence. Never reads the database."""

import re
from datetime import datetime

from backend.app import schemas as s
from .source import AnalyzedRow, Failure


class EvidenceStore:
    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self._items: dict[str, s.Evidence] = {}

    def _next_id(self) -> str:
        return f"E-{self.case_id}-{len(self._items) + 1}"

    def staged_copy(self) -> "EvidenceStore":
        """Stage changes while retaining immutable evidence objects."""
        staged = EvidenceStore(self.case_id)
        staged._items = self._items.copy()
        return staged

    def capture(self, scope: s.OpenCaseRequest, row: AnalyzedRow, ordinal: int, retrieved_at: datetime) -> s.Finding:
        observation = s.ObservedEvidence(
            evidence_id=self._next_id(), source_table="HACKATON.SNO_MEASUREMENT_DATA",
            scope=scope, measurement=row.measurement, raw_fields=row.raw_fields,
            row_ordinal=ordinal, retrieved_at=retrieved_at,
        )
        self._items[observation.evidence_id] = observation
        calculation = s.CalculatedEvidence(
            evidence_id=self._next_id(), input_evidence_ids=(observation.evidence_id,),
            rule=row.rule, result=row.calculation, retrieved_at=retrieved_at,
        )
        self._items[calculation.evidence_id] = calculation
        return s.Finding(
            measurement=row.measurement, raw_value=row.raw_fields.MEASURE_VALUE,
            raw_lower=row.raw_fields.LOWER_LIMIT, raw_upper=row.raw_fields.UPPER_LIMIT,
            parsed_value=row.calculation.parsed_value, deviation=row.calculation.deviation,
            unit=row.raw_fields.UNIT, range_status=row.calculation.range_status,
            quality_flags=row.calculation.quality_flags, raw_fail_code=row.raw_fields.MEASURE_FAIL_CODE,
            evidence_id=observation.evidence_id, calculation_evidence_id=calculation.evidence_id,
        )

    def report(
        self, question_id: str, answer_text: str, reported_at: datetime,
        conflict_evidence_ids: tuple[str, ...] = (),
        attribution: str = "technician via shared connector",
    ) -> s.Report:
        # Validate every reference before allocating/storing a new report.
        for ref in conflict_evidence_ids:
            if not isinstance(ref, str):
                raise Failure("INVALID_SCOPE", "A reviewed conflict must name observed evidence", 400)
            if not isinstance(self.get(ref), s.ObservedEvidence):
                raise Failure("INVALID_SCOPE", "A reviewed conflict must name observed evidence", 400)
        report = s.Report(
            evidence_id=self._next_id(), question_id=question_id, answer_text=answer_text,
            reported_at=reported_at, attribution=attribution,
            conflict_evidence_ids=tuple(dict.fromkeys(conflict_evidence_ids)),
        )
        self._items[report.evidence_id] = report
        return report

    def get(self, evidence_id: str) -> s.Evidence:
        match = re.fullmatch(r"E-([0-9a-f]{32})-[1-9][0-9]*", evidence_id)
        if match and match.group(1) != self.case_id:
            raise Failure("EVIDENCE_NOT_IN_CASE", "Evidence names a different case", 404)
        item = self._items.get(evidence_id)
        if item is None:
            raise Failure("EVIDENCE_NOT_FOUND", "Evidence is not present in this case", 404)
        return item
