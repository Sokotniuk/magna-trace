"""Lossless internal projection example, isolated from A's accepted modules.

This is not B2's response schema and does not issue evidence IDs or query Oracle.
"""
from dataclasses import fields, is_dataclass
from decimal import Decimal
import json

from backend.app.oracle_repo import MeasurementPage, StationPage


def to_json_value(value: object) -> object:
    """Project supported captures without rounding, fallback text or float use."""
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite Decimal cannot be serialized.")
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        result = {field.name: to_json_value(getattr(value, field.name)) for field in fields(value)}
        # These computed properties would be silently omitted by asdict alone.
        if isinstance(value, (MeasurementPage, StationPage)):
            result["returned_count"] = value.returned_count
            result["truncated"] = value.truncated
        return result
    if type(value) in (list, tuple):
        return [to_json_value(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError("JSON object keys must be strings.")
        return {key: to_json_value(item) for key, item in value.items()}
    raise TypeError("Unsupported value; explicit schema projection required.")


def dumps_exact(value: object) -> str:
    """Encode a projection; source timestamps already are timezone-free strings."""
    return json.dumps(to_json_value(value), ensure_ascii=False, allow_nan=False)


def raw_number_text(value: int | Decimal | None) -> str | None:
    """Use only if B2 requires raw NUMBER fields as string/null; no semantics."""
    if value is None:
        return None
    if type(value) is int:
        return str(value)
    if isinstance(value, Decimal) and value.is_finite():
        return str(value)
    raise TypeError("Expected an exact finite NUMBER or null.")
