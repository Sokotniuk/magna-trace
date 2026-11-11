"""Allow-listed, read-only Oracle access.

Rules (AGENTS.md I-1, I-2): only constant SELECT statements with bind variables,
row limits, timeouts and explicit ordering. No SQL text is ever built from input.
"""

import logging
from datetime import datetime

import oracledb

from .config import settings

log = logging.getLogger("trace.oracle")

MAX_CASE_ROWS = 500  # hard cap per open_case query


class SourceUnavailable(Exception):
    """Oracle could not be reached or refused the connection."""


class SourceTimeout(Exception):
    """The query exceeded the call timeout."""


def _reason(exc: Exception) -> str:
    """Driver text may contain connection details; log only the exception type."""
    return type(exc).__name__


def _connect() -> oracledb.Connection:
    try:
        conn = oracledb.connect(
            user=settings.oracle_user,
            password=settings.oracle_password,
            dsn=settings.oracle_dsn,
            tcp_connect_timeout=5,
        )
    except oracledb.Error as exc:
        log.warning("Oracle connect failed: %s", _reason(exc))
        raise SourceUnavailable(type(exc).__name__) from None
    conn.call_timeout = settings.oracle_call_timeout_ms
    return conn


def _query(sql: str, binds: dict | None = None, input_sizes: dict | None = None) -> list[dict]:
    """Run one allow-listed SELECT and return rows as dicts with lower-case column names."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            if input_sizes:
                cur.setinputsizes(**input_sizes)
            cur.execute(sql, binds or {})
            columns = [d[0].lower() for d in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    except oracledb.Error as exc:
        # DPI-1067: call timeout exceeded
        if "DPI-1067" in str(exc):
            log.warning("Oracle query timed out")
            raise SourceTimeout() from None
        log.warning("Oracle query failed: %s", _reason(exc))
        raise SourceUnavailable(type(exc).__name__) from None
    finally:
        conn.close()


# --- Allow-listed queries ---------------------------------------------------

SQL_COUNT_MEASUREMENTS = "SELECT COUNT(*) AS n FROM HACKATON.SNO_MEASUREMENT_DATA"

SQL_LIST_STATIONS = """
SELECT station_number, MAX(station_desc) AS station_desc,
       COUNT(*) AS measurement_rows, COUNT(DISTINCT serial_number) AS serials
FROM HACKATON.SNO_MEASUREMENT_DATA
GROUP BY station_number
ORDER BY station_number
"""

# Optional filters use "(:x IS NULL OR ...)" so the SQL text is constant for every request.
# ROWID is captured as the physical row locator at retrieval time; it is not a business key.
SQL_MEASUREMENTS_FOR_STATION = """
SELECT ROWIDTOCHAR(ROWID) AS row_locator,
       station_number, station_desc, part_number, part_desc, workorder_number, workorder_desc,
       serial_number, measure_step_number, measure_name, unit,
       measure_value, lower_limit, upper_limit, nominal, tolerance, measure_fail_code,
       book_stamp, measure_type,
       lower_intervention_limit, upper_intervention_limit, lower_scrap_limit, upper_scrap_limit
FROM HACKATON.SNO_MEASUREMENT_DATA
WHERE station_number = :station
  AND (:serial IS NULL OR serial_number = :serial)
  AND (:t_from IS NULL OR book_stamp >= :t_from)
  AND (:t_to IS NULL OR book_stamp <= :t_to)
ORDER BY book_stamp, serial_number, measure_step_number, measure_name, ROWID
FETCH FIRST :max_rows ROWS ONLY
"""


def count_measurements() -> int:
    """Number of rows in the measurement table. Used by health_echo for G0."""
    return int(_query(SQL_COUNT_MEASUREMENTS)[0]["n"])


def ping() -> bool:
    _query("SELECT 1 AS ok FROM DUAL")
    return True


def list_stations() -> list[dict]:
    return [
        {"station_number": r["station_number"], "station_desc": r["station_desc"],
         "measurement_rows": int(r["measurement_rows"]), "serials": int(r["serials"])}
        for r in _query(SQL_LIST_STATIONS)
    ]


def measurements_for_station(station: str, serial: str | None, t_from: datetime | None,
                             t_to: datetime | None, limit: int = MAX_CASE_ROWS) -> tuple[list[dict], bool]:
    """Measurement rows for one station scope. Returns (rows, truncated)."""
    limit = max(1, min(limit, MAX_CASE_ROWS))
    rows = _query(
        SQL_MEASUREMENTS_FOR_STATION,
        {"station": station, "serial": serial, "t_from": t_from, "t_to": t_to, "max_rows": limit + 1},
        input_sizes={"t_from": oracledb.DB_TYPE_TIMESTAMP, "t_to": oracledb.DB_TYPE_TIMESTAMP,
                     "serial": oracledb.DB_TYPE_VARCHAR},
    )
    truncated = len(rows) > limit
    rows = rows[:limit]
    for r in rows:  # JSON-safe primitives; measurement strings stay raw
        r["measure_step_number"] = int(r["measure_step_number"])
        r["measure_fail_code"] = None if r["measure_fail_code"] is None else int(r["measure_fail_code"])
        r["book_stamp"] = r["book_stamp"].isoformat(sep=" ") if r["book_stamp"] else None
    return rows, truncated
