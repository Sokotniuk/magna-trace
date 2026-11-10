"""record_answer: the answer is stored as evidence, observations stay unchanged, label stays UNDETERMINED."""

import unittest
from unittest import mock

from tests.test_cases_services import ROWS  # also sets dummy env before backend imports
from backend.app import oracle_repo, services


def open_case():
    with mock.patch.object(oracle_repo, "measurements_for_station", return_value=(ROWS, False)):
        return services.open_case("ST9999")


class RecordAnswer(unittest.TestCase):
    def setUp(self):
        self.case = open_case()
        self.case_id = self.case["case_id"]
        self.qid = self.case["data"]["next_action"]["question_id"]

    def answer(self, text="Fixture was re-clamped after the morning shift.", kind="YES", qid=None, case_id=None):
        return services.record_answer(case_id or self.case_id, qid or self.qid, text, kind)

    def test_yes_records_report_and_changes_next_step_not_label(self):
        result = self.answer()
        self.assertEqual(result["status"], "ok")
        snap = result["data"]
        update = snap["case_update"]
        self.assertEqual((update["question_id"], update["answer_kind"]), (self.qid, "YES"))
        self.assertEqual(snap["assessment"]["label"], "UNDETERMINED")
        self.assertEqual(snap["next_action"]["kind"], "ESCALATION")
        self.assertIn(update["answer_evidence_id"], snap["next_action"]["basis_evidence_ids"])
        self.assertNotIn("question_id", snap["next_action"])  # no new question was invented
        message = update["message"]
        self.assertIn(update["answer_evidence_id"], message)
        for part in update["what_changed"] + update["still_open"] + [snap["next_action"]["text"]]:
            self.assertIn(part, message)
        self.assertIn("not independently verified", message)
        self.assertEqual(snap["message"], message)  # the tool's ready text is the case update
        report_text = services.get_evidence(self.case_id, update["answer_evidence_id"])["data"]["message"]
        self.assertIn("(TECHNICIAN_REPORTED)", report_text)

        report = services.get_evidence(self.case_id, update["answer_evidence_id"])["data"]
        self.assertEqual(report["evidence_class"], "TECHNICIAN_REPORTED")
        self.assertEqual(report["answer_text"], "Fixture was re-clamped after the morning shift.")
        self.assertEqual(report["question_id"], self.qid)

    def test_no_and_unknown_choose_other_templates(self):
        self.assertEqual(self.answer(text="No, nothing was changed.", kind="NO")["data"]["next_action"]["kind"],
                         "ESCALATION")
        other = open_case()
        result = services.record_answer(other["case_id"], other["data"]["next_action"]["question_id"],
                                        "Not sure.", None)  # missing kind -> UNKNOWN
        self.assertEqual(result["data"]["case_update"]["answer_kind"], "UNKNOWN")
        self.assertEqual(result["data"]["next_action"]["kind"], "DATA_CHECK")

    def test_observations_and_findings_are_unchanged(self):
        before = self.case["data"]["findings"]
        before_evidence = [services.get_evidence(self.case_id, f["evidence_id"])["data"] for f in before]
        after = self.answer()["data"]
        self.assertNotIn("findings", after)  # not repeated in the response
        self.assertEqual(after["findings_unchanged"]["evidence_ids"], [f["evidence_id"] for f in before])
        handover = services.get_handover(self.case_id)["data"]  # the case still holds them in full
        self.assertEqual([o["deviation"] for o in handover["observations"]], [f["deviation"] for f in before])
        self.assertEqual([services.get_evidence(self.case_id, f["evidence_id"])["data"] for f in before],
                         before_evidence)

    def test_question_can_be_answered_once(self):
        self.assertEqual(self.answer()["status"], "ok")
        again = self.answer(kind="NO")
        self.assertEqual(again["error"]["code"], "INVALID_SCOPE")
        self.assertIn("no open question", again["error"]["message"])

    def test_ids_with_typographic_dashes_are_accepted(self):
        result = self.answer(qid=self.qid.replace("-", "‑"), case_id=self.case_id.replace("-", "‑"))
        self.assertEqual(result["status"], "ok")

    def test_wrong_question_id(self):
        result = self.answer(qid="Q-FFFFFF-1")
        self.assertEqual(result["error"]["code"], "INVALID_SCOPE")
        self.assertEqual(self.answer()["status"], "ok")  # the real question is still open

    def test_invalid_input(self):
        self.assertEqual(self.answer(text="   ")["error"]["code"], "INVALID_SCOPE")
        self.assertEqual(self.answer(text="x" * 2001)["error"]["code"], "INVALID_SCOPE")
        self.assertEqual(self.answer(kind="MAYBE")["error"]["code"], "INVALID_SCOPE")

    def test_unknown_case(self):
        self.assertEqual(self.answer(case_id="C-0000000000000000")["error"]["code"], "CASE_NOT_FOUND_OR_EXPIRED")

    def test_answers_do_not_leak_between_cases(self):
        other = open_case()
        self.answer()
        self.assertIsNone(other["data"].get("case_update"))
        result = services.record_answer(other["case_id"], self.qid, "yes", "YES")  # this case's question id
        self.assertEqual(result["error"]["code"], "INVALID_SCOPE")

    def test_case_without_question_rejects_answers(self):
        with mock.patch.object(oracle_repo, "measurements_for_station", return_value=([ROWS[0]], False)):
            quiet = services.open_case("ST9999")
        self.assertEqual(quiet["data"]["next_action"]["kind"], "DATA_CHECK")
        result = services.record_answer(quiet["case_id"], "Q-ANY-1", "yes", "YES")
        self.assertEqual(result["error"]["code"], "INVALID_SCOPE")


if __name__ == "__main__":
    unittest.main()
