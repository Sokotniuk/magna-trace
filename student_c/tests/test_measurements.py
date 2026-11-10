"""Measurement rules. Expected values are computed by hand, not by running the code under test."""

import unittest
from decimal import Decimal

from backend.app import measurements as m


class ParseNumber(unittest.TestCase):
    def test_plain_and_oracle_leading_dot_formats(self):
        self.assertEqual(m.parse_number("12.029"), (Decimal("12.029"), None))
        self.assertEqual(m.parse_number("8"), (Decimal("8"), None))
        self.assertEqual(m.parse_number(".5"), (Decimal("0.5"), None))
        self.assertEqual(m.parse_number("-.575"), (Decimal("-0.575"), None))
        self.assertEqual(m.parse_number(" 0 "), (Decimal("0"), None))

    def test_missing(self):
        for raw in (None, "", "   "):
            self.assertEqual(m.parse_number(raw), (None, "MISSING"))

    def test_rejected_formats_are_not_guessed(self):
        for raw in ("1,5", "1.234,5", "1 000", "1e3", "NaN", "Infinity", "12mm", "abc", "--1", "1.", "+1"):
            self.assertEqual(m.parse_number(raw), (None, "UNPARSEABLE"), raw)

    def test_one_and_one_point_zero_are_equal_numbers(self):
        self.assertEqual(m.parse_number("1")[0], m.parse_number("1.0")[0])

    def test_fmt_never_uses_exponent(self):
        self.assertEqual(m.fmt(Decimal("0.0000001")), "0.0000001")
        self.assertEqual(m.fmt(Decimal(".5")), "0.5")
        self.assertIsNone(m.fmt(None))


class Evaluate(unittest.TestCase):
    def test_reported_st3003_breaches(self):
        # hand arithmetic: 197.592-190, 1350.457-1300, 2.354-2, 1.292-1
        cases = [("197.592", "170", "190", "7.592"), ("1350.457", "1100", "1300", "50.457"),
                 ("2.354", "1", "2", "0.354"), ("1.292", "-1", "1", "0.292")]
        for value, lower, upper, expected in cases:
            ev = m.evaluate(value, lower, upper, "x", None)
            self.assertEqual(ev.range_status, m.ABOVE, value)
            self.assertEqual(m.fmt(ev.deviation), expected, value)

    def test_below(self):
        ev = m.evaluate("9.5", "10", "14", "Nm", None)  # 10 - 9.5
        self.assertEqual((ev.range_status, m.fmt(ev.deviation)), (m.BELOW, "0.5"))

    def test_negative_values_and_leading_dot(self):
        ev = m.evaluate("-.575", "-1", "1", "mm", None)
        self.assertEqual(ev.range_status, m.WITHIN)
        ev = m.evaluate("-1.2", "-1", "1", "mm", None)  # -1 - (-1.2)
        self.assertEqual((ev.range_status, m.fmt(ev.deviation)), (m.BELOW, "0.2"))

    def test_equality_with_bound_is_within(self):
        self.assertEqual(m.evaluate("14", "10", "14", "Nm", None).range_status, m.WITHIN)
        self.assertEqual(m.evaluate("10", "10", "14", "Nm", None).range_status, m.WITHIN)

    def test_in_range_row_with_1001_is_not_a_breach(self):
        ev = m.evaluate("8", "8", "8", "pcs", 1001)  # reported Screw Count row
        self.assertEqual(ev.range_status, m.WITHIN)
        self.assertIsNone(ev.deviation)
        self.assertIn("SEMANTICS_UNKNOWN", ev.flags)

    def test_null_code_has_no_semantics_flag_and_is_not_pass(self):
        ev = m.evaluate("12", "10", "14", "Nm", None)
        self.assertNotIn("SEMANTICS_UNKNOWN", ev.flags)
        self.assertEqual(ev.range_status, m.WITHIN)  # within recorded bounds, not "PASS"

    def test_missing_value(self):
        ev = m.evaluate(None, "10", "14", "Nm", None)
        self.assertEqual(ev.range_status, m.NOT_EVALUABLE)
        self.assertIn("MISSING", ev.flags)

    def test_unparseable_value(self):
        ev = m.evaluate("1,5", "1", "2", "mm", None)
        self.assertEqual(ev.range_status, m.NOT_EVALUABLE)
        self.assertIn("UNPARSEABLE", ev.flags)

    def test_no_bounds(self):
        ev = m.evaluate("5", None, "", "mm", None)
        self.assertEqual(ev.range_status, m.NOT_EVALUABLE)
        self.assertIn("LIMIT_UNKNOWN", ev.flags)

    def test_reversed_bounds(self):
        ev = m.evaluate("5", "10", "1", "mm", None)
        self.assertEqual(ev.range_status, m.NOT_EVALUABLE)
        self.assertIn("LIMIT_INVALID", ev.flags)

    def test_single_bound_is_partial(self):
        ev = m.evaluate("5", None, "10", "mm", None)
        self.assertEqual(ev.range_status, m.WITHIN)
        self.assertIn("PARTIAL_BOUNDS", ev.flags)
        ev = m.evaluate("12", None, "10", "mm", None)
        self.assertEqual((ev.range_status, m.fmt(ev.deviation)), (m.ABOVE, "2"))

    def test_unparseable_bound(self):
        ev = m.evaluate("5", "1,0", "10", "mm", None)
        self.assertIn("LIMIT_INVALID", ev.flags)
        self.assertIn("PARTIAL_BOUNDS", ev.flags)

    def test_unit_unknown(self):
        self.assertIn("UNIT_UNKNOWN", m.evaluate("5", "1", "10", None, None).flags)
        self.assertIn("UNIT_UNKNOWN", m.evaluate("5", "1", "10", "  ", None).flags)


if __name__ == "__main__":
    unittest.main()
