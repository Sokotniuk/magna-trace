"""Cases, evidence and open_case/get_evidence with a fake Oracle repository.

Rows are synthetic except the four ST3003 values already published in docs/product.md.
"""

import os
import unittest
from unittest import mock

# config.py reads these at import; dummy values, no database is contacted in these tests.
os.environ.setdefault("TRACE_API_KEY", "test-key")
os.environ.setdefault("ORACLE_USER", "test")
os.environ.setdefault("ORACLE_PASSWORD", "test")

from backend.app import oracle_repo, services  # noqa: E402
from backend.app.cases import CaseStore, CaseNotFound  # noqa: E402
from backend.app.evidence import EvidenceLedger, EvidenceNotFound, EvidenceNotInCase  # noqa: E402


def row(serial, step, name, value, lower, upper, unit, code=None, stamp="2026-11-09 10:55:13.108334"):
    return {
        "row_locator": f"ROW{serial}{step}", "station_number": "ST9999", "station_desc": "Test Station",
        "part_number": "P-1", "part_desc": "Part", "workorder_number": "WO-1", "workorder_desc": "WO",
        "serial_number": serial, "measure_step_number": step, "measure_name": name, "unit": unit,
        "measure_value": value, "lower_limit": lower, "upper_limit": upper, "nominal": None,
        "tolerance": None, "measure_fail_code": code, "book_stamp": stamp, "measure_type": "PROCESS",
        "lower_intervention_limit": None, "upper_intervention_limit": None,
        "lower_scrap_limit": None, "upper_scrap_limit": None,
    }


ROWS = [
    row("S1", 1, "Torque", "12.029", "10", "14", "Nm", stamp="2026-11-09 10:41:13"),
    row("S2", 2, "Angle", "197.592", "170", "190", "deg", 1001),
    row("S2", 4, "Screw Count", "8", "8", "8", "pcs", 1001),
    row("S2", 6, "Vibration", "2.354", "1", "2", "mm/s", 1001),
    row("S2", 8, "Position Accuracy", "1.292", "-1", "1", "mm", 1001),
    row("S2", 10, "Motor Speed", "1350.457", "1100", "1300", "rpm", 1001),
    row("S3", 1, "Torque", "1,5", "10", "14", "Nm", stamp="2026-11-09 11:02:13"),
]


class Ledger(unittest.TestCase):
    def test_ids_are_sequential_and_resolvable(self):
        ledger = EvidenceLedger("ABC123")
        eid = ledger.add("OBSERVED", {"x": 1})
        self.assertEqual(eid, "E-ABC123-001")
        self.assertEqual(ledger.get(eid)["x"], 1)
        self.assertEqual(ledger.get(eid.lower())["evidence_class"], "OBSERVED")

    def test_foreign_and_invented_ids(self):
        ledger = EvidenceLedger("ABC123")
        ledger.add("OBSERVED", {})
        with self.assertRaises(EvidenceNotInCase):
            ledger.get("E-FFFFFF-001")
        with self.assertRaises(EvidenceNotFound):
            ledger.get("E-ABC123-999")
        with self.assertRaises(EvidenceNotFound):
            ledger.get("anything")

    def test_typographic_dashes_and_quotes_are_normalised(self):
        ledger = EvidenceLedger("D65427")
        for _ in range(22):
            ledger.add("OBSERVED", {"n": 1})
        for variant in ("E‑D65427‑022", "E–D65427–022", "`E-D65427-022`", " e-d65427-022 "):
            self.assertEqual(ledger.get(variant)["evidence_id"], "E-D65427-022", repr(variant))
        with self.assertRaises(EvidenceNotInCase):
            ledger.get("E‑FFFFFF‑022")

    def test_stored_evidence_cannot_be_mutated_by_caller(self):
        ledger = EvidenceLedger("ABC123")
        content = {"fields": {"v": "1"}}
        eid = ledger.add("OBSERVED", content)
        content["fields"]["v"] = "2"
        ledger.get(eid)["fields"]["v"] = "3"
        self.assertEqual(ledger.get(eid)["fields"]["v"], "1")


class Store(unittest.TestCase):
    def test_unknown_case(self):
        with self.assertRaises(CaseNotFound):
            CaseStore().get("C-0000000000000000")

    def test_cases_are_isolated(self):
        store = CaseStore()
        a, b = store.create({}, "t"), store.create({}, "t")
        self.assertNotEqual(a.case_id, b.case_id)
        self.assertIsNot(a.ledger, b.ledger)


class OpenCase(unittest.TestCase):
    def open(self, rows=ROWS, truncated=False, **kw):
        with mock.patch.object(oracle_repo, "measurements_for_station", return_value=(rows, truncated)) as q:
            result = services.open_case(kw.pop("station", "st9999"), **kw)
        return result, q

    def test_snapshot(self):
        result, query = self.open()
        self.assertEqual(result["status"], "ok")
        query.assert_called_once_with("ST9999", None, None, None)  # normalised, passed as bind values
        snap = result["data"]

        self.assertEqual(snap["summary"]["range_status_counts"],
                         {"ABOVE": 4, "BELOW": 0, "WITHIN_RECORDED_BOUNDS": 2, "NOT_EVALUABLE": 1})
        self.assertEqual(snap["summary"]["rows_with_fail_code"], 5)

        # max five findings: four breaches first, then the in-range coded row
        f = snap["findings"]
        self.assertEqual(len(f), 5)
        self.assertEqual([x["deviation"] for x in f[:4]], ["7.592", "0.354", "0.292", "50.457"])
        self.assertEqual((f[4]["measurement"], f[4]["range_status"], f[4]["raw_fail_code"]),
                         ("Screw Count", "WITHIN_RECORDED_BOUNDS", 1001))
        self.assertEqual(snap["more_findings"], 1)  # the unparseable row
        self.assertNotIn("listed_because", f[0])  # ABOVE explains itself
        self.assertIn("within the recorded limits", f[4]["listed_because"])
        self.assertNotIn("evidence_ids", snap["patterns"][0])  # kept in the pattern evidence instead
        self.assertIn("code meaning unknown", f[4]["listed_because"])

        self.assertEqual(snap["assessment"]["label"], "UNDETERMINED")
        self.assertEqual(snap["patterns"][0]["serial_number"], "S2")
        self.assertEqual(len(snap["patterns"][0]["abnormal_measurements"]), 4)
        self.assertEqual(snap["next_action"]["kind"], "QUESTION")
        self.assertTrue(snap["next_action"]["question_id"].startswith("Q-"))
        self.assertTrue(any("Fail code meaning undocumented" in w for w in snap["warnings"]))
        pattern = services.get_evidence(result["case_id"], snap["patterns"][0]["pattern_evidence_id"])["data"]
        self.assertEqual(pattern["inputs"], [x["evidence_id"] for x in f[:4]])  # members still resolvable

    def test_every_finding_resolves(self):
        result, _ = self.open()
        case_id = result["case_id"]
        for finding in result["data"]["findings"]:
            obs = services.get_evidence(case_id, finding["evidence_id"])
            self.assertEqual(obs["status"], "ok")
            self.assertEqual(obs["data"]["evidence_class"], "OBSERVED")
            self.assertEqual(obs["data"]["fields"]["measure_value"], finding["raw_value"])
            if finding["calculation_evidence_id"]:
                calc = services.get_evidence(case_id, finding["calculation_evidence_id"])
                self.assertEqual(calc["data"]["deviation"], finding["deviation"])
                self.assertEqual(calc["data"]["inputs"], [finding["evidence_id"]])

    def test_ready_texts_carry_the_same_values(self):
        result, _ = self.open()
        snap, case_id = result["data"], result["case_id"]
        msg = snap["message"]
        self.assertIn(case_id, msg)
        for f in snap["findings"]:
            self.assertIn(f"`{f['evidence_id']}`", msg)
            self.assertIn(f["raw_value"], msg)
            if f["deviation"]:
                self.assertIn(f"| {f['deviation']} |", msg)  # deviation exactly as returned, no sign
        self.assertIn("Screw Count is listed because:", msg)
        self.assertIn(snap["next_action"]["question_id"], msg)
        table = [line for line in msg.splitlines() if line.startswith("| ") and "Measurement" not in line]
        self.assertEqual(len(table), len(snap["findings"]))
        self.assertFalse(any("+" in line for line in table))  # no signs added to values or deviations

        motor = next(f for f in snap["findings"] if f["measurement"] == "Motor Speed")
        calc = services.get_evidence(case_id, motor["calculation_evidence_id"])["data"]
        self.assertIn("(CALCULATED)", calc["message"])
        self.assertIn("deviation **50.457** rpm", calc["message"])
        self.assertIn(f"`{motor['evidence_id']}`", calc["message"])
        obs = services.get_evidence(case_id, motor["evidence_id"])["data"]
        self.assertIn("(OBSERVED)", obs["message"])
        self.assertIn("`1350.457`", obs["message"])
        self.assertIn("1001 (meaning unknown)", obs["message"])
        pattern = services.get_evidence(case_id, snap["patterns"][0]["pattern_evidence_id"])["data"]
        self.assertIn("serial S2", pattern["message"])

    def test_evidence_from_another_case_is_rejected(self):
        first, _ = self.open()
        second, _ = self.open()
        foreign = first["data"]["findings"][0]["evidence_id"]
        result = services.get_evidence(second["case_id"], foreign)
        self.assertEqual(result["error"]["code"], "EVIDENCE_NOT_IN_CASE")

    def test_unknown_case(self):
        result = services.get_evidence("C-DOESNOTEXIST", "E-AAAAAA-001")
        self.assertEqual(result["error"]["code"], "CASE_NOT_FOUND_OR_EXPIRED")
        self.assertIsNone(result["data"])

    def test_no_data_is_not_healthy(self):
        result, _ = self.open(rows=[])
        self.assertEqual(result["error"]["code"], "NO_DATA")
        self.assertIn("does not mean the station is healthy", result["error"]["message"])

    def test_invalid_scope(self):
        for kw in ({"station": "ST3003; DROP TABLE x"}, {"station": ""},
                   {"time_from": "yesterday"}, {"time_from": "2026-11-09 12:00", "time_to": "2026-11-09 10:00"},
                   {"serial_number": "1' OR '1'='1"}):
            result, query = self.open(**kw)
            self.assertEqual(result["error"]["code"], "INVALID_SCOPE", kw)
            query.assert_not_called()

    def test_source_errors_carry_no_data(self):
        for exc, code in ((oracle_repo.SourceUnavailable(), "SOURCE_UNAVAILABLE"), (oracle_repo.SourceTimeout(), "TIMEOUT")):
            with mock.patch.object(oracle_repo, "measurements_for_station", side_effect=exc):
                result = services.open_case("ST9999")
            self.assertEqual(result["error"]["code"], code)
            self.assertIsNone(result["data"])

    def test_truncation_is_warned(self):
        result, _ = self.open(truncated=True)
        self.assertTrue(result["data"]["scope"]["truncated"])
        self.assertTrue(any("truncated" in w for w in result["data"]["warnings"]))

    def test_no_breaches_gives_data_check(self):
        result, _ = self.open(rows=[ROWS[0]])
        self.assertEqual(result["data"]["next_action"]["kind"], "DATA_CHECK")
        self.assertEqual(result["data"]["patterns"], [])


if __name__ == "__main__":
    unittest.main()
