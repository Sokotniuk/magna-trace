"""Fixed read-only Oracle queries owned by Student A."""

import oracledb


_COUNT_MEASUREMENTS_SQL = "SELECT COUNT(*) FROM HACKATON.SNO_MEASUREMENT_DATA"
_TIMEOUT_CODES = frozenset(
    {"DPY-4024", "DPI-1067", "ORA-12170", "ORA-12535"}
)


class SourceUnavailableError(RuntimeError):
    """A read failed without a usable result; safe for B to map to the API."""

    code = "SOURCE_UNAVAILABLE"


class OracleTimeoutError(RuntimeError):
    """Oracle exceeded a connection or database-call timeout."""

    code = "TIMEOUT"


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
    """
    if not user.strip() or not password or not dsn.strip():
        raise ValueError("Oracle connection settings are required.")
    if user.strip().strip('"').upper() in {"SYS", "SYSTEM"}:
        raise ValueError("A dedicated SELECT-only Oracle account is required.")
    if type(call_timeout_ms) is not int or call_timeout_ms <= 0:
        raise ValueError("call_timeout_ms must be a positive integer.")
    if type(connect_timeout_seconds) is not int or connect_timeout_seconds <= 0:
        raise ValueError("connect_timeout_seconds must be a positive integer.")

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
        with oracledb.connect(params=params) as connection:
            connection.call_timeout = call_timeout_ms
            with connection.cursor() as cursor:
                cursor.execute(_COUNT_MEASUREMENTS_SQL)
                row = cursor.fetchone()
                if row is None or len(row) != 1:
                    raise SourceUnavailableError("Oracle returned no valid count.")
                count = row[0]
                if type(count) is not int or count < 0:
                    raise SourceUnavailableError("Oracle returned no valid count.")
                return count
    except oracledb.Error as error:
        # Driver messages may include connection details. Only expose fixed text.
        error_info = error.args[0] if error.args else None
        # DPY-6005 can wrap either a refused connection or a socket timeout.
        if getattr(error_info, "full_code", None) in _TIMEOUT_CODES or isinstance(
            error.__cause__, TimeoutError
        ):
            raise OracleTimeoutError("The Oracle read timed out.") from None
        raise SourceUnavailableError("The Oracle source is unavailable.") from None
