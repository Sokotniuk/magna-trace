"""Review is explicit internal input, never guessed from arbitrary answer prose."""

import pytest
from backend.app import schemas as s
from student_b.answers import record_answer
from student_b.source import Failure


def body(opened):
    return s.RecordAnswerRequest(question_id=opened["data"]["next_action"]["question_id"], answer_text="Technician disputes the selected observation.")


def test_explicit_dispute_keeps_both_versions_and_escalates(app, client, headers, opened):
    ref = opened["data"]["findings"][0]["evidence_id"]
    result = record_answer(app.state.cases, opened["case_id"], body(opened), reviewed_conflicts=(ref, ref))
    assert result.next_action.kind == "escalation"
    assert "TECHNICIAN_REPORT_CONFLICT" in result.warnings
    assert "REPORT_CONFLICT_NOT_AUTOMATICALLY_ASSESSED" not in result.warnings
    assert result.assessment.label == "UNDETERMINED"
    assert result.model_dump(mode="json")["findings"] == opened["data"]["findings"]
    report = result.technician_reports[0]
    assert report.conflict_evidence_ids == (ref,)
    assert ref in result.next_action.basis_evidence_ids
    prefix = f"/api/v1/cases/{opened['case_id']}"
    captured = client.get(prefix + "/evidence/" + ref, headers=headers).json()["data"]
    reported = client.get(prefix + "/evidence/" + report.evidence_id, headers=headers).json()["data"]
    assert captured["classification"] == "OBSERVED" and captured["raw_fields"]["MEASURE_VALUE"] == "10.5"
    assert reported["classification"] == "TECHNICIAN_REPORTED" and reported["conflict_evidence_ids"] == [ref]
    handover = client.get(prefix + "/handover", headers=headers).json()["data"]
    assert handover["next_action"]["kind"] == "escalation"
    assert handover["technician_reports"][0] == reported
    assert handover["observations"] == opened["data"]["findings"]


def test_explicit_review_without_conflict_is_distinct_from_unreviewed(app, opened):
    result = record_answer(app.state.cases, opened["case_id"], body(opened), reviewed_conflicts=())
    assert result.next_action.kind == "data_check"
    assert result.technician_reports[0].conflict_evidence_ids == ()
    assert "REPORT_REVIEWED_NO_CONFLICT_IDENTIFIED" in result.warnings
    assert "REPORT_CONFLICT_NOT_AUTOMATICALLY_ASSESSED" not in result.warnings


@pytest.mark.parametrize("kind,code", [("unknown", "EVIDENCE_NOT_FOUND"), ("calculated", "INVALID_SCOPE"), ("foreign", "EVIDENCE_NOT_IN_CASE"), ("wrong_type", "INVALID_SCOPE")])
def test_invalid_review_is_rejected_before_report_or_question_mutation(app, client, headers, opened, kind, code):
    first = opened["data"]["findings"][0]
    ref = {
        "unknown": f"E-{opened['case_id']}-999",
        "calculated": first["calculation_evidence_id"],
        "foreign": "E-ffffffffffffffffffffffffffffffff-1",
        "wrong_type": 123,
    }[kind]
    with pytest.raises(Failure) as error:
        # First reference is valid: a later invalid reference must not store a partial report.
        record_answer(app.state.cases, opened["case_id"], body(opened), reviewed_conflicts=(first["evidence_id"], ref))
    assert error.value.code == code
    with app.state.cases.locked(opened["case_id"]) as case:
        assert case.state == "AWAITING_CLARIFICATION"
        assert case.snapshot.model_dump(mode="json")["findings"] == opened["data"]["findings"]
        assert case.snapshot.technician_reports == ()
    result = record_answer(app.state.cases, opened["case_id"], body(opened))
    assert result.report_evidence_id == f"E-{opened['case_id']}-7"


def test_rest_cannot_submit_unapproved_review_fields(client, headers, opened):
    payload = body(opened).model_dump()
    payload["reviewed_conflicts"] = [opened["data"]["findings"][0]["evidence_id"]]
    prefix = f"/api/v1/cases/{opened['case_id']}/answers"
    rejected = client.post(prefix, json=payload, headers=headers)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "INVALID_SCOPE"
    accepted = client.post(prefix, json=body(opened).model_dump(), headers=headers)
    assert accepted.status_code == 200
    assert "REPORT_CONFLICT_NOT_AUTOMATICALLY_ASSESSED" in accepted.json()["data"]["warnings"]


def test_existing_report_cannot_be_reclassified_as_observed_evidence(app, client, headers, opened):
    result = record_answer(app.state.cases, opened["case_id"], body(opened))
    with app.state.cases.locked(opened["case_id"]) as case:
        with pytest.raises(Failure) as error:
            case.evidence.report("internal-question", "Another report", case.updated_at, (result.report_evidence_id,))
        assert error.value.code == "INVALID_SCOPE"
        assert case.evidence.get(result.report_evidence_id).conflict_evidence_ids == ()
