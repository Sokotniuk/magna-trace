"""A/B boundary: no SQL, measurement arithmetic, or demonstration fallback."""

import importlib
from dataclasses import dataclass, field
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

    def __post_init__(self) -> None:
        if type(self.total_rows) is not int or self.total_rows < len(self.rows) or self.truncated != (self.total_rows > len(self.rows)):
            raise ValueError("Batch counts must describe the exact queried scope")


class DataSource(Protocol):
    def count_measurements(self) -> int: ...
    def fetch_measurements(self, scope: s.OpenCaseRequest, *, limit: int) -> Batch: ...
    def list_stations(self, q: str | None, limit: int) -> s.Stations: ...


def translate_source_exception(error: Exception) -> Failure:
    """A must confirm its concrete exception attributes when its module is supplied."""
    code = getattr(error, "code", None) or getattr(error, "error_code", None)
    if isinstance(code, Enum):
        code = code.value
    if code == "TIMEOUT" or isinstance(error, TimeoutError):
        return Failure("TIMEOUT", "Oracle request timed out", 504)
    return Failure("SOURCE_UNAVAILABLE", "Oracle source is unavailable", 503)


class OracleSource:
    def __init__(
        self, credentials: OracleCredentials | None, *, call_timeout_ms: int = 5000,
        connect_timeout_seconds: int = 5, count_function: Callable[..., int] | None = None,
    ) -> None:
        self._credentials = credentials
        self._count_function = count_function
        self.call_timeout_ms = call_timeout_ms
        self.connect_timeout_seconds = connect_timeout_seconds

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
        raise Failure("SOURCE_UNAVAILABLE", "A2/A3 measurement adapter is not connected")

    def list_stations(self, q: str | None, limit: int) -> s.Stations:
        raise Failure("SOURCE_UNAVAILABLE", "A2 station adapter is not connected")
