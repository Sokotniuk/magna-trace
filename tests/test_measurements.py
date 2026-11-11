"""A3 synthetic expectations from hand arithmetic and approved D04/D05 rules."""

from dataclasses import FrozenInstanceError, asdict, replace
from decimal import Decimal, Inexact, Rounded, localcontext
import json

import pytest

from backend.app.measurements import analyze_measurement
from backend.app.oracle_repo import MeasurementRecord


def row(value="2.50", lower="1", upper="3", **changes):
    return replace(MeasurementRecord(
        station_number="SYNTH-A", serial_number="SYNTH-1", measurement="Synthetic length",
        raw_value=value, raw_lower=lower, raw_upper=upper, unit="mm", raw_fail_code=None,
        book_stamp="2026-01-01T10:00:00.123456", part_number="P", workorder_number="W",
        measure_step_number=Decimal("1"), measure_type="test",
        source_rowid="synthetic-locator", snapshot_ordinal=1,
    ), **changes)


@pytest.mark.parametrize(
    "value,lower,upper,status,deviation,rule",
    [
        ("2.50", "1", "3", "WITHIN_RECORDED_BOUNDS", None, None),
        ("3.015", "1", "3.000", "ABOVE", "0.015", "value - upper"),
        ("-2.50", "-2.00", "0", "BELOW", "0.50", "lower - value"),
        ("1", "1.0", "3", "WITHIN_RECORDED_BOUNDS", None, None),
        ("3.0", "1", "3", "WITHIN_RECORDED_BOUNDS", None, None),
        ("-0.000", "0", "0.0", "WITHIN_RECORDED_BOUNDS", None, None),
        (" +1.00 ", "1", "2", "WITHIN_RECORDED_BOUNDS", None, None),
    ],
)
def test_hand_calculations(value, lower, upper, status, deviation, rule):
    result = analyze_measurement(row(value, lower, upper))
    assert result.range_status == status
    assert result.deviation_rule == rule
    assert result.quality_flags == ("SEMANTICS_UNKNOWN",)
    assert result.field_issues == ()
    assert result.parsed_value == Decimal(value.strip())
    assert result.parsed_lower == Decimal(lower)
    assert result.parsed_upper == Decimal(upper)
    if deviation is None:
        assert result.deviation is None
        assert result.numeric_evaluation == "IN_RANGE"
    else:
        assert str(result.deviation) == deviation
        assert result.numeric_evaluation == "OUT_OF_RANGE"


@pytest.mark.parametrize("value", [None, "", " \t\n "])
def test_empty_numeric_input_is_missing_not_zero(value):
    result = analyze_measurement(row(value, "0", "0"))
    assert result.range_status == result.numeric_evaluation == "NOT_EVALUABLE"
    assert result.parsed_value is result.deviation is result.deviation_rule is None
    assert result.field_issues == (("raw_value", "MISSING"),)
    assert result.quality_flags == ("MISSING", "SEMANTICS_UNKNOWN")
    assert result.record.raw_value == value


def test_all_numeric_fields_and_unit_absent_preserves_every_issue():
    result = analyze_measurement(row(None, "", "  ", unit=None))
    assert result.numeric_evaluation == "NOT_EVALUABLE"
    assert result.parsed_value is result.parsed_lower is result.parsed_upper is None
    assert result.deviation is result.raw_fail_code is None
    assert result.field_issues == (
        ("raw_value", "MISSING"), ("raw_lower", "MISSING"), ("raw_upper", "MISSING"),
    )
    assert result.quality_flags == (
        "MISSING", "LIMIT_UNKNOWN", "UNIT_UNKNOWN", "SEMANTICS_UNKNOWN",
    )


@pytest.mark.parametrize("value", [
    "abc", "1,5", "1.234,5", "1 000", "NaN", "-Infinity", "Infinity",
    "1e3", "12mm", "1_000", "١٢", ".5", "1.",
])
def test_present_invalid_numeric_text_is_unparseable(value):
    result = analyze_measurement(row(value))
    assert result.numeric_evaluation == "NOT_EVALUABLE"
    assert result.parsed_value is result.deviation is None
    assert result.field_issues == (("raw_value", "UNPARSEABLE"),)
    assert result.quality_flags == ("UNPARSEABLE", "SEMANTICS_UNKNOWN")
    assert result.record.raw_value == value


@pytest.mark.parametrize(
    "value,lower,upper,status,deviation,flags,issues",
    [
        ("2", None, " ", "NOT_EVALUABLE", None, ("LIMIT_UNKNOWN",),
         (("raw_lower", "MISSING"), ("raw_upper", "MISSING"))),
        ("0", "1", None, "BELOW", "1", ("PARTIAL_BOUNDS",), (("raw_upper", "MISSING"),)),
        ("1", "1.0", None, "WITHIN_RECORDED_BOUNDS", None, ("PARTIAL_BOUNDS",),
         (("raw_upper", "MISSING"),)),
        ("4", None, "3.0", "ABOVE", "1.0", ("PARTIAL_BOUNDS",), (("raw_lower", "MISSING"),)),
        ("3", "", "3", "WITHIN_RECORDED_BOUNDS", None, ("PARTIAL_BOUNDS",),
         (("raw_lower", "MISSING"),)),
        ("2", "3", "1", "NOT_EVALUABLE", None, ("LIMIT_INVALID",), ()),
        ("2", "bad", "3", "NOT_EVALUABLE", None, ("UNPARSEABLE", "LIMIT_INVALID"),
         (("raw_lower", "UNPARSEABLE"),)),
        ("2", "1", "1,5", "NOT_EVALUABLE", None, ("UNPARSEABLE", "LIMIT_INVALID"),
         (("raw_upper", "UNPARSEABLE"),)),
        (None, "3", "1", "NOT_EVALUABLE", None, ("MISSING", "LIMIT_INVALID"),
         (("raw_value", "MISSING"),)),
        ("bad", "", "NaN", "NOT_EVALUABLE", None, ("UNPARSEABLE", "LIMIT_INVALID"),
         (("raw_value", "UNPARSEABLE"), ("raw_lower", "MISSING"), ("raw_upper", "UNPARSEABLE"))),
        ("bad", "1", "", "NOT_EVALUABLE", None, ("UNPARSEABLE", "PARTIAL_BOUNDS"),
         (("raw_value", "UNPARSEABLE"), ("raw_upper", "MISSING"))),
    ],
)
def test_independent_value_and_bound_issues(value, lower, upper, status, deviation, flags, issues):
    result = analyze_measurement(row(value, lower, upper))
    assert result.range_status == status
    assert result.quality_flags == (*flags, "SEMANTICS_UNKNOWN")
    assert result.field_issues == issues
    assert (None if result.deviation is None else str(result.deviation)) == deviation


def test_raw_record_identity_units_and_fail_codes_never_change_numeric_evaluation(monkeypatch):
    # A pure evaluation must work even when database access is forbidden.
    def forbidden(*args, **kwargs):
        pytest.fail("A3 attempted Oracle access")
    monkeypatch.setattr("oracledb.connect", forbidden)
    source = row("8", "8", "8", measurement="Screw Count", raw_fail_code=1001)
    original = asdict(source)
    baseline = analyze_measurement(source)
    assert baseline.record is source
    assert asdict(source) == original
    assert baseline == analyze_measurement(source)
    assert baseline.numeric_evaluation == "IN_RANGE"
    assert baseline.raw_fail_code == 1001
    assert baseline.quality_flags == ("SEMANTICS_UNKNOWN",)
    for value, expected in (("8", "IN_RANGE"), ("9", "OUT_OF_RANGE"), ("bad", "NOT_EVALUABLE")):
        expected_result = analyze_measurement(replace(source, raw_value=value))
        for code in (1001, None, Decimal("-9999999999")):
            for unit in ("mm", "V", " unknown unit ", None, "", "  "):
                changed = replace(source, raw_value=value, raw_fail_code=code, unit=unit)
                result = analyze_measurement(changed)
                assert result.record is changed
                assert result.record.unit == unit
                assert result.raw_fail_code is code
                assert result.numeric_evaluation == expected
                assert (result.range_status, result.parsed_value, result.deviation) == (
                    expected_result.range_status, expected_result.parsed_value, expected_result.deviation,
                )
                assert ("UNIT_UNKNOWN" in result.quality_flags) == (unit is None or not unit.strip())
                assert "SEMANTICS_UNKNOWN" in result.quality_flags
    with pytest.raises(FrozenInstanceError):
        baseline.range_status = "ABOVE"
    with pytest.raises(FrozenInstanceError):
        baseline.record.raw_value = "9"


def test_raw_context_preserved_without_substitution_or_aliasing():
    extras = {
        "NOMINAL": " 1.00 ", "TOLERANCE": "±0,1", "LOWER_INTERVENTION_LIMIT": "-9",
        "UPPER_INTERVENTION_LIMIT": "9", "LOWER_SCRAP_LIMIT": None, "UPPER_SCRAP_LIMIT": "10",
    }
    original = dict(extras)
    result = analyze_measurement(row("2", None, None), extra_raw_fields=extras)
    assert result.numeric_evaluation == "NOT_EVALUABLE"
    assert result.quality_flags == ("LIMIT_UNKNOWN", "SEMANTICS_UNKNOWN")
    assert dict(result.extra_raw_fields) == original
    extras["NOMINAL"] = "changed"
    assert dict(result.extra_raw_fields) == original
    assert analyze_measurement(row()).extra_raw_fields == ()


def test_precision_scale_and_caller_decimal_context_are_preserved():
    with localcontext() as context:
        context.prec = 2
        context.Emax = 2
        context.Emin = -2
        context.clamp = 1
        context.traps[Inexact] = context.traps[Rounded] = True
        before = str(context)
        above = analyze_measurement(row("123456789012345678901234567890.0100", "0", "0.0001"))
        below = analyze_measurement(row("-999999999999999999999999999999.9999", "0.0001", None))
        tiny = analyze_measurement(row("0.000000000000000000000000000003", None,
                                       "0.000000000000000000000000000001"))
        assert str(above.deviation) == "123456789012345678901234567890.0099"
        assert str(below.deviation) == "1000000000000000000000000000000.0000"
        assert tiny.deviation.as_tuple() == Decimal("0.000000000000000000000000000002").as_tuple()
        assert str(context) == before


def test_inclusive_and_outside_metamorphic_properties():
    # Hand-selected intervals exercise signs, numerical equality and zero.
    for lower, upper, below, above in [
        ("1", "1.0", "0.999", "1.001"), ("-2.00", "-1", "-2.001", "-0.999"),
        ("0", "2", "-0.001", "2.001"),
    ]:
        for boundary in (lower, upper):
            result = analyze_measurement(row(boundary, lower, upper))
            assert result.numeric_evaluation == "IN_RANGE"
            assert result.deviation is None
        for outside, status in ((below, "BELOW"), (above, "ABOVE")):
            result = analyze_measurement(row(outside, lower, upper))
            assert result.numeric_evaluation == "OUT_OF_RANGE"
            assert result.range_status == status
            assert result.deviation > 0


def test_empty_record_and_native_numeric_inputs_rejected_without_coercion():
    for empty in (None, {}, ""):
        with pytest.raises(TypeError, match="MeasurementRecord"):
            analyze_measurement(empty)
    for field in ("raw_value", "raw_lower", "raw_upper"):
        for native in (0, 0.1, Decimal("1"), True):
            with pytest.raises(TypeError, match="text or null"):
                analyze_measurement(replace(row(), **{field: native}))
    with pytest.raises(TypeError, match="unit"):
        analyze_measurement(row(unit=1))
    with pytest.raises(ValueError, match="Unsupported"):
        analyze_measurement(row(), extra_raw_fields={"UNKNOWN": "1"})
    with pytest.raises(TypeError, match="text or null"):
        analyze_measurement(row(), extra_raw_fields={"NOMINAL": 1})
    with pytest.raises(TypeError, match="mapping"):
        analyze_measurement(row(), extra_raw_fields=[])


def test_synthetic_raw_calculated_pair_can_be_projected_losslessly_for_b():
    source = row(" 3.0150 ", "1", "3.0000", raw_fail_code=Decimal("1001"))
    result = analyze_measurement(source)
    # Demonstrates standard-library projection only; B5 must verify its own
    # snapshot/schema serialization. No API contract is introduced here.
    payload = json.loads(json.dumps(asdict(result), default=str))
    assert payload["record"] == {
        "station_number": "SYNTH-A", "serial_number": "SYNTH-1",
        "measurement": "Synthetic length", "raw_value": " 3.0150 ",
        "raw_lower": "1", "raw_upper": "3.0000", "unit": "mm",
        "raw_fail_code": "1001", "book_stamp": "2026-01-01T10:00:00.123456",
        "part_number": "P", "workorder_number": "W", "measure_step_number": "1",
        "measure_type": "test", "source_rowid": "synthetic-locator", "snapshot_ordinal": 1,
    }
    assert payload["parsed_value"] == "3.0150"
    assert payload["parsed_lower"] == "1"
    assert payload["parsed_upper"] == "3.0000"
    assert payload["deviation"] == "0.0150"
    assert payload["deviation_rule"] == "value - upper"
    assert payload["range_status"] == "ABOVE"
    assert payload["quality_flags"] == ["SEMANTICS_UNKNOWN"]
