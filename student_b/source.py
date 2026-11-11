"""A/B boundary: no SQL, measurement arithmetic, or demonstration fallback."""

import importlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Callable, Protocol

from backend.app import schemas as s


class Failure(Exception):
    def __init__(self, code: str, message: str, http_status: int = 503, scope: s.OpenCaseRequest | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.http_status, self.scope = code, message, http_status, scope


@dataclass(frozen=True)
class OracleCredentials:
    user: str = field(repr=False)
    password: str = field(repr=False)
    dsn: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (self.user, self.dsn)) or not isinstance(self.password, str) or not self.password:
            raise ValueError("Oracle server-side settings must be nonempty")
        if self.user.strip().strip('"').upper() in {"SYS", "SYSTEM"}:
            raise ValueError("Use a dedicated SELECT-only Oracle user")


@dataclass(frozen=True)
class AnalyzedRow:
    measurement: str
    raw_fields: s.RawFields
    calculation: s.CalculationResult
    rule: str


@dataclass(frozen=True)
class Batch:
    rows: tuple[AnalyzedRow, ...]
    total_rows: int
    truncated: bool
    coverage_warnings: tuple[str, ...] = ()
    retrieved_at: datetime | None = None
    source_scope: s.OpenCaseRequest | None = None
    source_capture: object | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if type(self.total_rows) is not int or self.total_rows < len(self.rows) or self.truncated != (self.total_rows > len(self.rows)):
            raise ValueError("Batch counts must describe the exact queried scope")


class DataSource(Protocol):
    def count_measurements(self) -> int: ...
    def fetch_measurements(self, scope: s.OpenCaseRequest, *, limit: int) -> Batch: ...
    def list_stations(self, q: str | None, limit: int) -> s.Stations: ...


def translate_source_exception(error: Exception) -> Failure:
    """Map A's accepted typed errors without exposing driver/configuration text."""
    code = getattr(error, "code", None) or getattr(error, "error_code", None)
    if isinstance(code, Enum):
        code = code.value
    if code == "TIMEOUT" or isinstance(error, TimeoutError):
        return Failure("TIMEOUT", "Oracle request timed out", 504)
    if code == "INVALID_SCOPE":
        return Failure("INVALID_SCOPE", "Source scope requires full naive timestamps with from earlier than to, and nonblank literal identifiers", 422)
    return Failure("SOURCE_UNAVAILABLE", "Oracle source is unavailable", 503)


def raw_number_text(value: int | Decimal | None) -> str | None:
    """An Oracle NUMBER has an exact value, not an original text spelling."""
    if value is None:
        return None
    if type(value) is int:
        return str(value)
    if isinstance(value, Decimal) and value.is_finite():
        return str(value)
    raise TypeError("Expected an exact finite source NUMBER or null")


def source_retrieved_at(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("Source retrieval time must be UTC")
    return stamp


class OracleSource:
    def __init__(
        self, credentials: OracleCredentials | None, *, call_timeout_ms: int = 5000,
        connect_timeout_seconds: int = 5, count_function: Callable[..., int] | None = None,
    ) -> None:
        self._credentials = credentials
        self._count_function = count_function
        self.call_timeout_ms = call_timeout_ms
        self.connect_timeout_seconds = connect_timeout_seconds

    def _connection_args(self) -> dict[str, object]:
        if self._credentials is None:
            raise Failure("SOURCE_UNAVAILABLE", "Oracle server-side credentials are not configured")
        return dict(user=self._credentials.user, password=self._credentials.password,
                    dsn=self._credentials.dsn, call_timeout_ms=self.call_timeout_ms,
                    connect_timeout_seconds=self.connect_timeout_seconds)

    def count_measurements(self) -> int:
        if self._credentials is None:
            raise Failure("SOURCE_UNAVAILABLE", "Oracle server-side credentials are not configured")
        try:
            function = self._count_function
            if function is None:
                function = importlib.import_module("backend.app.oracle_repo").count_measurements
            value = function(
                user=self._credentials.user, password=self._credentials.password, dsn=self._credentials.dsn,
                call_timeout_ms=self.call_timeout_ms, connect_timeout_seconds=self.connect_timeout_seconds,
            )
            if type(value) is not int or value < 0:
                raise ValueError("A count function must return a nonnegative integer")
            return value
        except Failure:
            raise
        except Exception as error:
            # Do not serialize exception text, connection details, credentials or tracebacks.
            raise translate_source_exception(error) from None

    def fetch_measurements(self, scope: s.OpenCaseRequest, *, limit: int) -> Batch:
        try:
            if type(limit) is not int or not 1 <= limit <= 200:
                raise Failure("INVALID_SCOPE", "Measurement row cap must be 1..200", 422)
            repo = importlib.import_module("backend.app.oracle_repo")
            analysis = importlib.import_module("backend.app.measurements")
            page = repo.read_measurements(
                **self._connection_args(), station_number=scope.station_number,
                serial_number=scope.serial_number, from_time=scope.from_time,
                to_time=scope.to_time, limit=limit,
            )
            if not isinstance(page, repo.MeasurementPage) or len(page.records) > limit:
                raise ValueError("Unexpected A2 page")
            accepted_scope = s.OpenCaseRequest(
                station_number=page.scope.station_number, serial_number=page.scope.serial_number,
                from_time=page.scope.from_time, to_time=page.scope.to_time,
            )
            evaluations = tuple(analysis.analyze_measurement(record) for record in page.records)
            rows = tuple(AnalyzedRow(
                measurement=record.measurement,
                raw_fields=s.RawFields(
                    MEASURE_VALUE=record.raw_value, LOWER_LIMIT=record.raw_lower,
                    UPPER_LIMIT=record.raw_upper, UNIT=record.unit,
                    MEASURE_FAIL_CODE=raw_number_text(record.raw_fail_code),
                    station_number=record.station_number, serial_number=record.serial_number,
                    BOOK_STAMP=record.book_stamp,
                ),
                calculation=s.CalculationResult(
                    parsed_value=evaluation.parsed_value, deviation=evaluation.deviation,
                    range_status=evaluation.range_status, quality_flags=evaluation.quality_flags,
                ),
                rule=evaluation.deviation_rule or (
                    "A3 recorded-bound comparison: within bounds; no breach deviation"
                    if evaluation.range_status == "WITHIN_RECORDED_BOUNDS" else
                    "A3 strict numeric and bound validation: not evaluable; no deviation"
                ),
            ) for record, evaluation in zip(page.records, evaluations, strict=True))
            warnings = (*page.warnings, "TIME_SCOPE_HALF_OPEN")
            if page.missing_book_stamps:
                warnings += ("MISSING_SOURCE_TIMESTAMPS",)
            return Batch(
                rows, page.total_matching_rows, page.truncated, warnings,
                retrieved_at=source_retrieved_at(page.retrieved_at), source_scope=accepted_scope,
                source_capture=(page, evaluations),
            )
        except Failure:
            raise
        except Exception as error:
            raise translate_source_exception(error) from None

    def list_stations(self, q: str | None, limit: int) -> s.Stations:
        try:
            if type(limit) is not int or not 1 <= limit <= 100:
                raise Failure("INVALID_SCOPE", "Station limit must be 1..100", 422)
            repo = importlib.import_module("backend.app.oracle_repo")
            page = repo.list_stations(**self._connection_args(), q=q, limit=limit)
            if not isinstance(page, repo.StationPage) or len(page.records) > limit:
                raise ValueError("Unexpected A2 station page")
            return s.Stations(stations=tuple(
                s.Station(station_number=record.station_number, record_count=record.record_count)
                for record in page.records
            ))
        except Failure:
            raise
        except Exception as error:
            raise translate_source_exception(error) from None
