"""Pure A3 evaluation; source observations remain immutable and separate.

The internal result shape and nullable non-breach deviation are provisional for
B5 confirmation. Public API serialization remains Student B's responsibility.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Context, Decimal, MAX_EMAX, MIN_EMIN
import re
from typing import Literal

from .oracle_repo import MeasurementRecord


RangeStatus = Literal["ABOVE", "BELOW", "WITHIN_RECORDED_BOUNDS", "NOT_EVALUABLE"]
NumericEvaluation = Literal["IN_RANGE", "OUT_OF_RANGE", "NOT_EVALUABLE"]
ParseIssue = Literal["MISSING", "UNPARSEABLE"]
QualityFlag = Literal[
    "MISSING", "UNPARSEABLE", "LIMIT_UNKNOWN", "LIMIT_INVALID",
    "PARTIAL_BOUNDS", "UNIT_UNKNOWN", "SEMANTICS_UNKNOWN",
]
NumericField = Literal["raw_value", "raw_lower", "raw_upper"]
DeviationRule = Literal["value - upper", "lower - value"]

# Provisional D09 grammar: never infer locale, exponent or categorical meaning.
_DECIMAL_TEXT = re.compile(r"[+-]?[0-9]+(?:[.][0-9]+)?")
_FLAG_ORDER: tuple[QualityFlag, ...] = (
    "MISSING", "UNPARSEABLE", "LIMIT_UNKNOWN", "LIMIT_INVALID",
    "PARTIAL_BOUNDS", "UNIT_UNKNOWN", "SEMANTICS_UNKNOWN",
)
_EXTRA_FIELDS = frozenset({
    "NOMINAL", "TOLERANCE", "LOWER_INTERVENTION_LIMIT",
    "UPPER_INTERVENTION_LIMIT", "LOWER_SCRAP_LIMIT", "UPPER_SCRAP_LIMIT",
})


@dataclass(frozen=True)
class MeasurementEvaluation:
    """Raw A2 record plus exact calculations, without case/evidence IDs.

    field_issues attributes each missing/invalid numeric input to its raw field.
    extra_raw_fields holds only supplied source context; omitted columns remain
    unavailable. No context field is used as a specification bound.
    """

    record: MeasurementRecord
    parsed_value: Decimal | None
    parsed_lower: Decimal | None
    parsed_upper: Decimal | None
    range_status: RangeStatus
    deviation: Decimal | None
    deviation_rule: DeviationRule | None
    quality_flags: tuple[QualityFlag, ...]
    field_issues: tuple[tuple[NumericField, ParseIssue], ...]
    extra_raw_fields: tuple[tuple[str, str | None], ...]

    @property
    def numeric_evaluation(self) -> NumericEvaluation:
        """Coarse internal view; range_status keeps the canonical direction."""
        if self.range_status == "WITHIN_RECORDED_BOUNDS":
            return "IN_RANGE"
        if self.range_status in ("ABOVE", "BELOW"):
            return "OUT_OF_RANGE"
        return "NOT_EVALUABLE"

    @property
    def raw_fail_code(self) -> int | Decimal | None:
        return self.record.raw_fail_code


def _parse(raw: str | None) -> tuple[Decimal | None, ParseIssue | None]:
    if raw is None:
        return None, "MISSING"
    if not isinstance(raw, str):
        raise TypeError("Numeric source fields must be text or null.")
    text = raw.strip()
    if not text:
        return None, "MISSING"
    if not _DECIMAL_TEXT.fullmatch(text):
        return None, "UNPARSEABLE"
    return Decimal(text), None


def _exact_difference(left: Decimal, right: Decimal) -> Decimal:
    # Enough digits for aligned coefficients and a carry, independent of the
    # caller's precision, exponent limits, rounding mode, traps and flags.
    exponent = min(left.as_tuple().exponent, right.as_tuple().exponent)
    precision = max(left.adjusted(), right.adjusted()) - exponent + 2
    return Context(prec=precision, Emin=MIN_EMIN, Emax=MAX_EMAX).subtract(left, right)


def _capture_extra(
    fields: Mapping[str, str | None] | None,
) -> tuple[tuple[str, str | None], ...]:
    if fields is None:
        return ()
    if not isinstance(fields, Mapping):
        raise TypeError("Extra source fields must be a mapping.")
    captured = []
    for key, value in fields.items():
        if key not in _EXTRA_FIELDS:
            raise ValueError("Unsupported extra source field.")
        if value is not None and not isinstance(value, str):
            raise TypeError("Extra source values must be text or null.")
        captured.append((key, value))
    return tuple(sorted(captured))


def analyze_measurement(
    record: MeasurementRecord,
    *,
    extra_raw_fields: Mapping[str, str | None] | None = None,
) -> MeasurementEvaluation:
    """Evaluate one A2 record without I/O, normalization or code interpretation.

    One valid bound can be evaluated only when the other is missing (D04).
    A malformed supplied bound invalidates the interval. Non-breach and
    unevaluable deviations are None, provisionally awaiting B5 confirmation.
    """
    if not isinstance(record, MeasurementRecord):
        raise TypeError("Expected one MeasurementRecord.")
    if record.unit is not None and not isinstance(record.unit, str):
        raise TypeError("Source unit must be text or null.")
    captured = _capture_extra(extra_raw_fields)
    value, value_issue = _parse(record.raw_value)
    lower, lower_issue = _parse(record.raw_lower)
    upper, upper_issue = _parse(record.raw_upper)
    issues: tuple[tuple[NumericField, ParseIssue], ...] = tuple(
        (name, issue) for name, issue in (
            ("raw_value", value_issue), ("raw_lower", lower_issue),
            ("raw_upper", upper_issue),
        ) if issue is not None
    )

    # Null and undocumented codes have equally unknown semantics (D05).
    flags: set[QualityFlag] = {"SEMANTICS_UNKNOWN"}
    if value_issue == "MISSING":
        flags.add("MISSING")
    if any(issue == "UNPARSEABLE" for _, issue in issues):
        flags.add("UNPARSEABLE")
    if record.unit is None or not record.unit.strip():
        flags.add("UNIT_UNKNOWN")

    invalid_bounds = (
        lower_issue == "UNPARSEABLE" or upper_issue == "UNPARSEABLE"
        or (lower is not None and upper is not None and lower > upper)
    )
    if invalid_bounds:
        flags.add("LIMIT_INVALID")
    elif lower is None and upper is None:
        flags.add("LIMIT_UNKNOWN")
    elif lower is None or upper is None:
        flags.add("PARTIAL_BOUNDS")

    status: RangeStatus = "NOT_EVALUABLE"
    deviation = None
    rule: DeviationRule | None = None
    if value is not None and not invalid_bounds and (lower is not None or upper is not None):
        if lower is not None and value < lower:
            status, deviation, rule = "BELOW", _exact_difference(lower, value), "lower - value"
        elif upper is not None and value > upper:
            status, deviation, rule = "ABOVE", _exact_difference(value, upper), "value - upper"
        else:
            # Provisional D09: equality is within the recorded bound, not a
            # certification of the manufacturing test or fail-code semantics.
            status = "WITHIN_RECORDED_BOUNDS"

    return MeasurementEvaluation(
        record=record, parsed_value=value, parsed_lower=lower, parsed_upper=upper,
        range_status=status, deviation=deviation, deviation_rule=rule,
        quality_flags=tuple(flag for flag in _FLAG_ORDER if flag in flags),
        field_issues=issues, extra_raw_fields=captured,
    )
