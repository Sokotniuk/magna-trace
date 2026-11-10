"""Deterministic measurement evaluation (architecture §4, AGENTS.md §7.2).

All arithmetic uses Decimal built from the raw string. Raw strings are kept by the caller.
Range status, quality flags and the raw fail code are independent outputs.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

# Formats observed in HACKATON.SNO_MEASUREMENT_DATA (profiled 2026-11-10): '12.029', '8',
# '-.575', '.5' (Oracle omits the leading zero). No commas, spaces or exponents occur, so
# anything else is rejected rather than guessed.
_NUMBER = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)$")

ABOVE = "ABOVE"
BELOW = "BELOW"
WITHIN = "WITHIN_RECORDED_BOUNDS"
NOT_EVALUABLE = "NOT_EVALUABLE"


def parse_number(raw: str | None) -> tuple[Decimal | None, str | None]:
    """Return (value, None) or (None, 'MISSING' | 'UNPARSEABLE')."""
    if raw is None or not raw.strip():
        return None, "MISSING"
    text = raw.strip()
    if not _NUMBER.match(text):
        return None, "UNPARSEABLE"
    return Decimal(text), None


def fmt(value: Decimal | None) -> str | None:
    """Decimal -> plain string without exponent ('.5' -> '0.5'). JSON carries decimals as strings."""
    return None if value is None else format(value, "f")


@dataclass(frozen=True)
class Evaluation:
    value: Decimal | None
    lower: Decimal | None
    upper: Decimal | None
    range_status: str
    deviation: Decimal | None
    flags: tuple[str, ...]


def evaluate(raw_value: str | None, raw_lower: str | None, raw_upper: str | None,
             unit: str | None, fail_code: int | None) -> Evaluation:
    flags: list[str] = []

    value, value_flag = parse_number(raw_value)
    if value_flag:
        flags.append(value_flag)

    lower, lower_flag = parse_number(raw_lower)
    upper, upper_flag = parse_number(raw_upper)
    if "UNPARSEABLE" in (lower_flag, upper_flag):
        flags.append("LIMIT_INVALID")

    status, deviation = NOT_EVALUABLE, None
    if lower is None and upper is None:
        flags.append("LIMIT_UNKNOWN")
    elif lower is not None and upper is not None and lower > upper:
        flags.append("LIMIT_INVALID")
    else:
        if lower is None or upper is None:
            flags.append("PARTIAL_BOUNDS")  # the missing side is not checked
        if value is not None:
            # Provisional policy: bounds are inclusive (equality is within bounds).
            if upper is not None and value > upper:
                status, deviation = ABOVE, value - upper
            elif lower is not None and value < lower:
                status, deviation = BELOW, lower - value
            else:
                status = WITHIN

    if unit is None or not unit.strip():
        flags.append("UNIT_UNKNOWN")
    if fail_code is not None:
        flags.append("SEMANTICS_UNKNOWN")  # e.g. 1001: meaning undocumented, never PASS/FAIL

    return Evaluation(value, lower, upper, status, deviation, tuple(dict.fromkeys(flags)))
