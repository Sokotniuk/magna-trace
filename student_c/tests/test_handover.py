"""get_handover: built from case state only; every evidence ID in it resolves."""

import re
import unittest
from unittest import mock

from tests.test_cases_services import ROWS  # sets dummy env before backend imports
from backend.app import oracle_repo, services

EVIDENCE_ID = re.compile(r"E-[0-9A-F]{6}-\d{3,}")


def open_case():
    with mock.patch.object(oracle_repo, "measurements_for_station", return_value=(ROWS, False)):
        return services.open_case("ST9999")


class Handover(unittest.TestCase):
    def test_before_answer_lists_open_question(self):
        case = open_case()
        h = services.get_handover(case["case_id"])["data"]
        self.assertEqual(h["technician_reports"], [])
        self.assertEqual(h["open_questions"][0]["question_id"], case["data"]["next_action"]["question_id"])
        self.assertEqual(h["assessment"]["label"], "UNDETERMINED")
        self.assertIn("Open question:", h["text"])

    def test_after_answer_contains_report_and_new_next_step(self):
        case = open_case()
        qid = case["data"]["next_action"]["question_id"]
        answer = services.record_answer(case["case_id"], qid, "Fixture was re-clamped.", "YES")["data"]
        h = services.get_handover(case["case_id"])["data"]
        self.assertEqual(h["open_questions"], [])
        self.assertEqual(h["technician_reports"][0]["answer_text"], "Fixture was re-clamped.")
        self.assertEqual(h["technician_reports"][0]["evidence_id"], answer["case_update"]["answer_evidence_id"])
        self.assertEqual(h["next_action"], answer["next_action"])
        self.assertIn("not independently verified", h["text"])
        self.assertIn("The report is not independently verified.", h["unresolved"])

    def test_observations_match_snapshot_and_all_ids_resolve(self):
        case = open_case()
        h = services.get_handover(case["case_id"])["data"]
        self.assertEqual([o["evidence_id"] for o in h["observations"]],
                         [f["evidence_id"] for f in case["data"]["findings"]])
        self.assertEqual([o["deviation"] for o in h["observations"]],
                         [f["deviation"] for f in case["data"]["findings"]])
        ids = set(EVIDENCE_ID.findall(h["text"]))
        self.assertTrue(ids)
        for eid in ids:
            self.assertEqual(services.get_evidence(case["case_id"], eid)["status"], "ok", eid)

    def test_no_new_oracle_query(self):
        case = open_case()
        with mock.patch.object(oracle_repo, "measurements_for_station") as query:
            services.get_handover(case["case_id"])
        query.assert_not_called()

    def test_text_mentions_unresolved_semantics_and_no_procedure(self):
        h = services.get_handover(open_case()["case_id"])["data"]
        self.assertIn("Meaning of MEASURE_FAIL_CODE values is undocumented.", h["unresolved"])
        self.assertIn("No approved maintenance procedure was consulted by this system.", h["unresolved"])

    def test_text_only_variant_for_the_agent(self):
        case = open_case()
        full = services.get_handover(case["case_id"])["data"]
        compact = services.get_handover(case["case_id"], text_only=True)["data"]
        self.assertEqual(set(compact), {"case_id", "text", "evidence_ids"})
        self.assertEqual(compact["text"], full["text"])
        self.assertEqual(compact["evidence_ids"], [o["evidence_id"] for o in full["observations"]])
        for eid in compact["evidence_ids"]:
            self.assertEqual(services.get_evidence(case["case_id"], eid)["status"], "ok")

    def test_unknown_case(self):
        self.assertEqual(services.get_handover("C-0000000000000000")["error"]["code"], "CASE_NOT_FOUND_OR_EXPIRED")


if __name__ == "__main__":
    unittest.main()
