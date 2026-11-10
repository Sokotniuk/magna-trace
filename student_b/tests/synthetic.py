"""Test-only source. Literal synthetic outcomes; never imported by production."""

from decimal import Decimal
from backend.app import schemas as s
from student_b.source import AnalyzedRow, Batch


class Clock:
    now = 0.0
    def __call__(self):
        return self.now


class SyntheticSource:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.rows = []
        # Independent expected literals, not calculations produced by the code under test.
        for name, value, low, high, unit, code, parsed, deviation, status, flags in (
            ("SYNTHETIC Torque", "10.5", "8.0", "10.0", "Nm", None, "10.5", "0.5", "ABOVE", ("SEMANTICS_UNKNOWN",)),
            ("SYNTHETIC Count", "8", "8", "8", "count", "1001", "8", "0", "WITHIN_RECORDED_BOUNDS", ("SEMANTICS_UNKNOWN",)),
            ("SYNTHETIC Invalid", "abc", "0", "1", None, None, None, None, "NOT_EVALUABLE", ("UNPARSEABLE", "UNIT_UNKNOWN", "SEMANTICS_UNKNOWN")),
        ):
            self.rows.append(AnalyzedRow(
                measurement=name, raw_fields=s.RawFields(
                    MEASURE_VALUE=value, LOWER_LIMIT=low, UPPER_LIMIT=high, UNIT=unit,
                    MEASURE_FAIL_CODE=code, station_number="SYNTHETIC-STATION", serial_number="SYNTHETIC-SERIAL", BOOK_STAMP="2026-01-01 10:00:00",
                ), calculation=s.CalculationResult(
                    parsed_value=Decimal(parsed) if parsed is not None else None,
                    deviation=Decimal(deviation) if deviation is not None else None,
                    range_status=status, quality_flags=flags,
                ), rule="Independent synthetic fixture; 10.5 - 10.0 = 0.5; equality provisionally within bounds",
            ))

    def count_measurements(self):
        self.calls.append("count")
        if self.failure:
            raise self.failure
        return len(self.rows)

    def fetch_measurements(self, scope, *, limit):
        self.calls.append((scope, limit))
        if self.failure:
            raise self.failure
        rows = tuple(row for row in self.rows if row.raw_fields.station_number == scope.station_number and (scope.serial_number is None or row.raw_fields.serial_number == scope.serial_number))
        return Batch(rows[:limit], len(rows), len(rows) > limit)

    def list_stations(self, q, limit):
        if self.failure:
            raise self.failure
        return s.Stations(stations=(s.Station(station_number="SYNTHETIC-STATION", record_count=len(self.rows)),) if q is None or "SYNTHETIC-STATION".lower().startswith(q.lower()) else ())


