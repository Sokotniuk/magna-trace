"""Bounded deterministic output; source calculations are provided by A."""

from datetime import datetime

from backend.app import schemas as s


def snapshot(scope: s.Scope, findings: tuple[s.Finding, ...], question_id: str, retrieved_at: datetime) -> s.Snapshot:
    basis = tuple(f.evidence_id for f in findings[:5])
    hypotheses = tuple(s.Hypothesis(
        description=description, supporting_evidence_ids=basis, counterevidence_ids=(),
        limitations=("Captured measurements cannot establish a physical cause.",),
        distinguishing_evidence=distinguishing,
    ) for description, distinguishing in (
        ("Equipment or test-context explanation remains unverified.", "Independently verified station context and comparable tests."),
        ("Product-context explanation remains unverified.", "Verified product linkage and comparable measurements."),
    ))
    warnings = ["SOURCE_TIMEZONE_UNKNOWN", "SEMANTICS_UNKNOWN", "RELATIONSHIPS_UNVERIFIED", "BOUND_EQUALITY_POLICY_PROVISIONAL", *scope.coverage_warnings]
    if any(not f.unit or not f.unit.strip() for f in findings):
        warnings.append("UNIT_UNKNOWN")
    if scope.truncated:
        warnings.append("TRUNCATED_SCOPE")
    return s.Snapshot(
        scope=scope, observations_retrieved_at=retrieved_at, findings=findings[:5],
        additional_evidence_ids=tuple(ref for f in findings[5:] for ref in (f.evidence_id, f.calculation_evidence_id)),
        technician_reports=(), assessment=s.Assessment(hypotheses=hypotheses, unknowns=("Physical cause", "Fail-code semantics", "Source timezone")),
        next_action=s.Question(
            question_id=question_id, text="Do you know of station or fixture context changes around these tests that are absent from the captured measurement records?",
            basis_evidence_ids=basis,
        ), warnings=tuple(dict.fromkeys(warnings)),
    )


def record_report(before: s.Snapshot, report: s.Report, *, conflict_reviewed: bool = False) -> s.Snapshot:
    basis = (report.evidence_id, *(f.evidence_id for f in before.findings))
    if report.conflict_evidence_ids:
        action = s.Escalation(
            text="Escalate the explicitly disputed observations for independent verification; retain both the captured record and technician report.",
            basis_evidence_ids=tuple(dict.fromkeys((*basis, *report.conflict_evidence_ids))),
        )
        review_warning = "TECHNICIAN_REPORT_CONFLICT"
    else:
        action = s.Check(text="Verify the reported context and its timing against authorized station records before drawing conclusions.", basis_evidence_ids=basis)
        review_warning = "REPORT_REVIEWED_NO_CONFLICT_IDENTIFIED" if conflict_reviewed else "REPORT_CONFLICT_NOT_AUTOMATICALLY_ASSESSED"
    return before.model_copy(update={
        "technician_reports": (*before.technician_reports, report), "next_action": action,
        "warnings": tuple(dict.fromkeys((*before.warnings, "TECHNICIAN_REPORT_UNVERIFIED", review_warning))),
    })


def handover(current: s.Snapshot) -> s.Handover:
    questions = (current.next_action.text,) if current.next_action.kind == "question" else ()
    return s.Handover(
        scope=current.scope, observations_retrieved_at=current.observations_retrieved_at,
        observations=current.findings, additional_evidence_ids=current.additional_evidence_ids,
        technician_reports=current.technician_reports, assessment=current.assessment,
        open_questions=questions, gaps=(*current.assessment.unknowns, *current.warnings), next_action=current.next_action,
    )
