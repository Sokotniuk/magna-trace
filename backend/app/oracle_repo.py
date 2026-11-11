"""Fixed read-only Oracle queries owned by Student A."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

import oracledb


_COUNT_MEASUREMENTS_SQL = "SELECT COUNT(*) FROM HACKATON.SNO_MEASUREMENT_DATA"
_TIMEOUT_CODES = frozenset(
    {"DPY-4024", "DPI-1067", "ORA-12170", "ORA-12535"}
)
_CONNECTION_WRAPPERS = frozenset({"DPY-6005", "DPY-4011", "DPI-1080"})


class SourceUnavailableError(RuntimeError):
    """A read failed without a usable result; safe for B to map to the API."""

    code = "SOURCE_UNAVAILABLE"
    driver_code: str | None = None
    phase: str | None = None


class OracleTimeoutError(RuntimeError):
    """Oracle exceeded a connection or database-call timeout."""

    code = "TIMEOUT"
    driver_code: str | None = None
    phase: str | None = None


def _oracle_failure(error: Exception, phase: str) -> SourceUnavailableError | OracleTimeoutError:
    """Classify structured error chains without exposing driver message text."""
    timeout = False
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        info = current.args[0] if current.args else None
        code = getattr(info, "full_code", None)
        timeout |= isinstance(current, TimeoutError) or (type(code) is str and code in _TIMEOUT_CODES)
        # Inspect chains only for known wrapper/recovery codes. An ordinary
        # authentication error must not inherit a caller's unrelated timeout.
        if type(code) is str and code in _CONNECTION_WRAPPERS:
            if current.__cause__ is not None:
                pending.append(current.__cause__)
            elif code != "DPY-6005" and current.__context__ is not None:
                # Thin-mode failed timeout recovery may use exception context.
                pending.append(current.__context__)
    info = error.args[0] if error.args else None
    raw_code = getattr(info, "full_code", None)
    driver_code = raw_code if (
        type(raw_code) is str and re.fullmatch(r"(?:ORA|DPY|DPI)-[0-9]{4,5}", raw_code)
    ) else None
    failure = OracleTimeoutError("The Oracle read timed out.") if timeout else (
        SourceUnavailableError("The Oracle source is unavailable.")
    )
    failure.driver_code, failure.phase = driver_code, phase
    return failure


@contextmanager
def _preserve_read_error(resource):
    """Attempt cleanup without letting a secondary failure replace the read error."""
    value = resource.__enter__()
    try:
        yield value
    except BaseException as primary:
        try:
            resource.__exit__(type(primary), primary, primary.__traceback__)
        except Exception:
            # The outer resource is still closed; preserve the original typed
            # failure instead of misreporting a timeout as a disconnect.
            pass
        raise
    else:
        # A cleanup failure after a successful read must prevent success.
        resource.__exit__(None, None, None)


def count_measurements(
    *,
    user: str,
    password: str,
    dsn: str,
    call_timeout_ms: int = 5000,
    connect_timeout_seconds: int = 5,
) -> int:
    """Return a live scalar count using an approved SELECT-only account.

    B supplies connection settings from its server-side configuration. Timeout
    defaults are provisional pending the real connector budget. The function
    owns its connection and cursor so failures cannot leak a shared session.
    connect_timeout_seconds limits TCP establishment. call_timeout_ms applies
    to each database round trip after login. Neither is a total login deadline.
    Driver recovery and cleanup may add time; this is not a whole-read deadline.
    """
    if not all(isinstance(value, str) and value.strip() for value in (user, dsn)):
        raise ValueError("Oracle connection settings are required.")
    if not isinstance(password, str) or not password:
        raise ValueError("Oracle connection settings are required.")
    if user.strip().strip('"').upper() in {"SYS", "SYSTEM"}:
        raise ValueError("A dedicated SELECT-only Oracle account is required.")
    if type(call_timeout_ms) is not int or call_timeout_ms <= 0:
        raise ValueError("call_timeout_ms must be a positive integer.")
    if type(connect_timeout_seconds) is not int or connect_timeout_seconds <= 0:
        raise ValueError("connect_timeout_seconds must be a positive integer.")

    phase = "connect"
    try:
        # Parse first, then set the limits so DSN options cannot override them.
        params = oracledb.ConnectParams()
        params.parse_connect_string(dsn)
        params.set(
            user=user,
            password=password,
            tcp_connect_timeout=connect_timeout_seconds,
            retry_count=0,
        )
        with _preserve_read_error(oracledb.connect(params=params)) as connection:
            phase = "configure"
            connection.call_timeout = call_timeout_ms
            phase = "execute"
            with _preserve_read_error(connection.cursor()) as cursor:
                cursor.execute(_COUNT_MEASUREMENTS_SQL)
                phase = "fetch"
                row = cursor.fetchone()
                if not isinstance(row, tuple) or len(row) != 1:
                    raise SourceUnavailableError("Oracle returned no valid count.")
                count = row[0]
                if type(count) is not int or count < 0:
                    raise SourceUnavailableError("Oracle returned no valid count.")
                phase = "cleanup"
                return count
    except (oracledb.Error, OSError) as error:
        raise _oracle_failure(error, phase) from None


# D12-approved limits and interval policy; B owns the wire projection.
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
_NAIVE_ISO = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:[.][0-9]{1,6})?"
)
_MEASUREMENTS_SQL = """
SELECT m.STATION_NUMBER, m.SERIAL_NUMBER, m.MEASURE_NAME,
       m.MEASURE_VALUE, m.LOWER_LIMIT, m.UPPER_LIMIT, m.UNIT,
       m.MEASURE_FAIL_CODE,
       TO_CHAR(m.BOOK_STAMP, 'YYYY-MM-DD"T"HH24:MI:SS.FF6') AS raw_book_stamp,
       m.PART_NUMBER, m.WORKORDER_NUMBER, m.MEASURE_STEP_NUMBER, m.MEASURE_TYPE,
       ROWIDTOCHAR(m.ROWID) AS source_rowid,
       COUNT(*) OVER () AS total_matching_rows,
       TO_CHAR(MIN(m.BOOK_STAMP) OVER (), 'YYYY-MM-DD"T"HH24:MI:SS.FF6') AS first_stamp,
       TO_CHAR(MAX(m.BOOK_STAMP) OVER (), 'YYYY-MM-DD"T"HH24:MI:SS.FF6') AS last_stamp,
       COUNT(*) OVER () - COUNT(m.BOOK_STAMP) OVER () AS missing_stamps
FROM HACKATON.SNO_MEASUREMENT_DATA m
WHERE m.STATION_NUMBER COLLATE BINARY = :station_number
  AND (:serial_number IS NULL OR m.SERIAL_NUMBER COLLATE BINARY = :serial_number)
  AND (:from_time IS NULL OR m.BOOK_STAMP >= :from_time)
  AND (:to_time IS NULL OR m.BOOK_STAMP < :to_time)
ORDER BY m.BOOK_STAMP DESC NULLS LAST, m.ROWID ASC
FETCH FIRST :row_limit ROWS ONLY
"""
_STATIONS_SQL = """
SELECT m.STATION_NUMBER COLLATE BINARY AS station_number,
       COUNT(*) AS record_count, COUNT(*) OVER () AS total_matching_stations
FROM HACKATON.SNO_MEASUREMENT_DATA m
WHERE (:q IS NULL OR INSTR(m.STATION_NUMBER COLLATE BINARY, :q) > 0)
GROUP BY m.STATION_NUMBER COLLATE BINARY
ORDER BY station_number ASC
FETCH FIRST :row_limit ROWS ONLY
"""


class InvalidScopeError(ValueError):
    """A2 scope validation failed before Oracle was contacted."""

    code = "INVALID_SCOPE"


@dataclass(frozen=True)
class MeasurementScope:
    station_number: str
    serial_number: str | None
    from_time: str | None
    to_time: str | None
    limit: int


@dataclass(frozen=True)
class MeasurementRecord:
    station_number: str
    serial_number: str
    measurement: str
    raw_value: str | None
    raw_lower: str | None
    raw_upper: str | None
    unit: str | None
    raw_fail_code: int | Decimal | None
    book_stamp: str | None
    part_number: str
    workorder_number: str
    measure_step_number: int | Decimal
    measure_type: str | None
    source_rowid: str
    snapshot_ordinal: int


@dataclass(frozen=True)
class MeasurementPage:
    scope: MeasurementScope
    records: tuple[MeasurementRecord, ...]
    total_matching_rows: int
    first_book_stamp: str | None
    last_book_stamp: str | None
    missing_book_stamps: int
    retrieved_at: str
    source_table: str = "HACKATON.SNO_MEASUREMENT_DATA"
    warnings: tuple[str, ...] = ("SOURCE_TIMEZONE_UNKNOWN", "ROWID_NOT_DURABLE")

    @property
    def returned_count(self) -> int:
        return len(self.records)

    @property
    def truncated(self) -> bool:
        return self.returned_count < self.total_matching_rows


@dataclass(frozen=True)
class StationRecord:
    station_number: str
    record_count: int


@dataclass(frozen=True)
class StationPage:
    q: str | None
    limit: int
    records: tuple[StationRecord, ...]
    total_matching_stations: int
    retrieved_at: str

    @property
    def returned_count(self) -> int:
        return len(self.records)

    @property
    def truncated(self) -> bool:
        return self.returned_count < self.total_matching_stations


def _text_scope(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidScopeError(f"{name} must be a nonempty string.")
    return value


def _limit(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_LIMIT:
        raise InvalidScopeError(f"limit must be an integer from 1 to {MAX_LIMIT}.")
    return value


def _time_bound(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        if not _NAIVE_ISO.fullmatch(value):
            raise InvalidScopeError(
                "Time bounds require naive ISO timestamps with at most six fractional digits."
            )
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            raise InvalidScopeError("Time bound is not a valid calendar timestamp.") from None
    if type(value) is not datetime or value.tzinfo is not None:
        raise InvalidScopeError(
            "Source timezone is unknown; time bounds must be naive timestamps."
        )
    return value


def _number_output(cursor: oracledb.Cursor, metadata: oracledb.FetchInfo) -> oracledb.Var | None:
    # Keep NUMBER fields out of binary floating-point, without global defaults.
    if metadata.type_code is oracledb.DB_TYPE_NUMBER:
        return cursor.var(
            oracledb.DB_TYPE_VARCHAR, arraysize=cursor.arraysize, outconverter=Decimal
        )
    return None


def _select_rows(
    sql: str,
    binds: dict[str, object],
    *,
    user: str,
    password: str,
    dsn: str,
    call_timeout_ms: int,
    connect_timeout_seconds: int,
    timestamp_inputs: tuple[str, ...] = (),
) -> list[tuple]:
    # A6 preserves the accepted A1/A2 signatures and fixed success-path SQL.
    if not all(isinstance(value, str) and value.strip() for value in (user, dsn)):
        raise ValueError("Oracle connection settings are required.")
    if not isinstance(password, str) or not password:
        raise ValueError("Oracle connection settings are required.")
    if user.strip().strip('"').upper() in {"SYS", "SYSTEM"}:
        raise ValueError("A dedicated SELECT-only Oracle account is required.")
    if type(call_timeout_ms) is not int or call_timeout_ms <= 0:
        raise ValueError("call_timeout_ms must be a positive integer.")
    if type(connect_timeout_seconds) is not int or connect_timeout_seconds <= 0:
        raise ValueError("connect_timeout_seconds must be a positive integer.")
    phase = "connect"
    try:
        params = oracledb.ConnectParams()
        params.parse_connect_string(dsn)
        params.set(
            user=user,
            password=password,
            tcp_connect_timeout=connect_timeout_seconds,
            retry_count=0,
        )
        with _preserve_read_error(oracledb.connect(params=params)) as connection:
            phase = "configure"
            connection.call_timeout = call_timeout_ms
            phase = "execute"
            with _preserve_read_error(connection.cursor()) as cursor:
                cursor.outputtypehandler = _number_output
                # Datetime binds otherwise default to DATE, losing fractions.
                cursor.setinputsizes(
                    **dict.fromkeys(timestamp_inputs, oracledb.DB_TYPE_TIMESTAMP)
                )
                cursor.execute(sql, binds)
                phase = "fetch"
                rows = cursor.fetchmany(binds["row_limit"] + 1)
                phase = "cleanup"
        if not isinstance(rows, list) or len(rows) > binds["row_limit"]:
            raise SourceUnavailableError("Oracle returned an invalid bounded result.")
        return rows
    except (oracledb.Error, OSError) as error:
        raise _oracle_failure(error, phase) from None
    except InvalidOperation:
        raise SourceUnavailableError("Oracle returned an invalid numeric field.") from None


def _integer(value: object) -> int:
    if type(value) is int:
        return value
    if isinstance(value, Decimal) and value.is_finite() and value == int(value):
        return int(value)
    raise SourceUnavailableError("Oracle returned an invalid integral NUMBER field.")


def _count(value: object) -> int:
    count = _integer(value)
    if count >= 0:
        return count
    raise SourceUnavailableError("Oracle returned invalid count metadata.")


def _page_total(rows: list[tuple], width: int, total_index: int, limit: int) -> int:
    if any(not isinstance(row, tuple) or len(row) != width for row in rows):
        raise SourceUnavailableError("Oracle returned an invalid result structure.")
    if not rows:
        return 0
    total = _count(rows[0][total_index])
    if len(rows) != min(total, limit) or any(_count(row[total_index]) != total for row in rows):
        raise SourceUnavailableError("Oracle returned inconsistent count metadata.")
    return total


def _source_time(value: object) -> datetime | None:
    try:
        parsed = _time_bound(value)
    except InvalidScopeError:
        raise SourceUnavailableError("Oracle returned an invalid source timestamp.") from None
    if value is not None and (
        type(value) is not str or parsed.isoformat(timespec="microseconds") != value
    ):
        raise SourceUnavailableError("Oracle returned an invalid source timestamp.")
    return parsed


def read_measurements(
    *,
    user: str,
    password: str,
    dsn: str,
    station_number: str | None = None,
    serial_number: str | None = None,
    from_time: str | datetime | None = None,
    to_time: str | datetime | None = None,
    limit: int = DEFAULT_LIMIT,
    call_timeout_ms: int = 5000,
    connect_timeout_seconds: int = 5,
) -> MeasurementPage:
    """Read one station in [from_time, to_time), newest first, then physical ROWID.

    ROWID only orders this capture. B issues immutable case-local evidence IDs.
    Timezone-free source timestamps retain six digits; text fields stay raw.
    Empty results are successful pages for B to map to NO_DATA with exact scope.
    """
    station = _text_scope(station_number, "station_number")
    serial = _text_scope(serial_number, "serial_number", optional=True)
    row_limit = _limit(limit)
    start, end = _time_bound(from_time), _time_bound(to_time)
    if start is not None and end is not None and start >= end:
        raise InvalidScopeError("from_time must be earlier than to_time.")
    scope = MeasurementScope(
        station, serial,
        start.isoformat(timespec="microseconds") if start is not None else None,
        end.isoformat(timespec="microseconds") if end is not None else None,
        row_limit,
    )
    rows = _select_rows(
        _MEASUREMENTS_SQL,
        {
            "station_number": station, "serial_number": serial,
            "from_time": start, "to_time": end, "row_limit": row_limit,
        },
        user=user, password=password, dsn=dsn, call_timeout_ms=call_timeout_ms,
        connect_timeout_seconds=connect_timeout_seconds, timestamp_inputs=("from_time", "to_time"),
    )
    total = _page_total(rows, 18, 14, row_limit)
    first, last, missing = rows[0][15:18] if rows else (None, None, 0)
    missing = _count(missing)
    if missing > total:
        raise SourceUnavailableError("Oracle returned inconsistent time coverage.")
    first_time, last_time = _source_time(first), _source_time(last)
    if missing < total:
        if first_time is None or last_time is None or first_time > last_time:
            raise SourceUnavailableError("Oracle returned inconsistent time coverage.")
    elif first_time is not None or last_time is not None:
        raise SourceUnavailableError("Oracle returned inconsistent time coverage.")
    records = []
    for ordinal, row in enumerate(rows, 1):
        required_text = (row[0], row[1], row[2], row[9], row[10], row[13])
        optional_text = (*row[3:7], row[8], row[12], row[15], row[16])
        if any(type(value) is not str or not value for value in required_text) or any(
            value is not None and type(value) is not str for value in optional_text
        ):
            raise SourceUnavailableError("Oracle returned invalid raw field types.")
        if row[7] is not None:
            _integer(row[7])
        _integer(row[11])
        stamp = _source_time(row[8])
        if row[0] != station or (serial is not None and row[1] != serial):
            raise SourceUnavailableError("Oracle returned a record outside the requested scope.")
        if (start is not None and (stamp is None or stamp < start)) or (
            end is not None and (stamp is None or stamp >= end)
        ):
            raise SourceUnavailableError("Oracle returned a record outside the requested time window.")
        if stamp is not None and (
            first_time is None or last_time is None or not first_time <= stamp <= last_time
        ):
            raise SourceUnavailableError("Oracle returned inconsistent time coverage.")
        if row[15:17] != (first, last) or _count(row[17]) != missing:
            raise SourceUnavailableError("Oracle returned inconsistent time coverage.")
        records.append(MeasurementRecord(*row[:14], snapshot_ordinal=ordinal))
    captured_missing = sum(record.book_stamp is None for record in records)
    if captured_missing > missing or (len(records) == total and captured_missing != missing):
        raise SourceUnavailableError("Oracle returned inconsistent missing timestamp counts.")
    if len({record.source_rowid for record in records}) != len(records):
        raise SourceUnavailableError("Oracle returned a repeated physical row locator.")
    return MeasurementPage(
        scope, tuple(records), total, first, last, missing,
        datetime.now(timezone.utc).isoformat(timespec="microseconds"),
    )


def list_stations(
    *,
    user: str,
    password: str,
    dsn: str,
    q: str | None = None,
    limit: int = DEFAULT_LIMIT,
    call_timeout_ms: int = 5000,
    connect_timeout_seconds: int = 5,
) -> StationPage:
    """Return bounded station IDs and counts, with case-sensitive literal search."""
    search = _text_scope(q, "q", optional=True)
    row_limit = _limit(limit)
    rows = _select_rows(
        _STATIONS_SQL, {"q": search, "row_limit": row_limit},
        user=user, password=password, dsn=dsn, call_timeout_ms=call_timeout_ms,
        connect_timeout_seconds=connect_timeout_seconds,
    )
    total = _page_total(rows, 3, 2, row_limit)
    records = []
    for station, count, _ in rows:
        if type(station) is not str or not station or _count(count) == 0:
            raise SourceUnavailableError("Oracle returned an invalid station record.")
        records.append(StationRecord(station, _count(count)))
    if len({record.station_number for record in records}) != len(records):
        raise SourceUnavailableError("Oracle returned a repeated station group.")
    return StationPage(
        search, row_limit, tuple(records), total,
        datetime.now(timezone.utc).isoformat(timespec="microseconds"),
    )
