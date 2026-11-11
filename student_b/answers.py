"""Record answers atomically. A conflict review is explicit trusted integration input."""

from backend.app import schemas as s
from . import diagnostics
from .cases import CaseStore, utc_now
from .source import Failure


def record_answer(
    store: CaseStore, case_id: str, body: s.RecordAnswerRequest, *,
    reviewed_conflicts: tuple[str, ...] | None = None,
    attribution: str | None = None,
) -> s.AnswerSnapshot:
    """None means unreviewed; () means reviewed without an identified conflict.

    Nonempty references identify explicitly disputed OBSERVED evidence. This is
    not an inference from prose or an assertion that the source record is wrong.
    REST intentionally supplies None until C's review flow has been agreed.
    """
    with store.locked(case_id) as case:
        if case.snapshot is None or case.state != "AWAITING_CLARIFICATION" or body.question_id != case.question_id:
            raise Failure("INVALID_SCOPE", "Question is stale, answered, or belongs to another case", 409)
        if reviewed_conflicts is not None and not isinstance(reviewed_conflicts, tuple):
            raise Failure("INVALID_SCOPE", "Review must provide a tuple of observed evidence references", 400)
        # attribution: signed-in demo employee when the integration layer supplies one (D34).
        extra = {"attribution": attribution} if attribution else {}
        report = case.evidence.report(body.question_id, body.answer_text, utc_now(), reviewed_conflicts or (), **extra)
        updated = diagnostics.record_report(case.snapshot, report, conflict_reviewed=reviewed_conflicts is not None)
        result = s.AnswerSnapshot(
            **updated.model_dump(), report_evidence_id=report.evidence_id,
            change_summary="Technician report added; observations preserved; next action updated.",
        )
        case.snapshot = updated
        case.question_id = None
        case.transition("ANSWER_RECORDED")
        case.transition("NEXT_CHECK_OR_ESCALATE")
        return result
