"""Station overview for the dashboard tiles: counts of range statuses per station.

Counts come from the same source and Decimal rules as a case (student B's DataSource, student A's
analysis), so the dashboard can outline stations with recorded out-of-range values without any
logic in TypeScript. A count is not a diagnosis: it says nothing about cause, severity or whether
the rows belong to one event. Results are cached briefly so tile polling does not load Oracle.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from fastapi import APIRouter, Request

from backend.app import schemas as s
from backend.app.cases import utc_now
from backend.app.source import Failure, translate_source_exception

CACHE_SECONDS = 60


def make_overview_router(authenticate: Callable[[Request], None], row_limit: int) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    cache: dict[str, object] = {}
    lock = threading.Lock()

    def build(source) -> dict:
        stations = []
        for station in source.list_stations(None, 100).stations:
            batch = source.fetch_measurements(s.OpenCaseRequest(station_number=station.station_number), limit=row_limit)
            statuses = [row.calculation.range_status for row in batch.rows]
            out = [row for row in batch.rows if row.calculation.range_status in ("ABOVE", "BELOW")]
            stations.append({
                "station_number": station.station_number,
                "record_count": station.record_count,
                "captured_rows": len(batch.rows),
                "truncated": batch.truncated,
                "above": statuses.count("ABOVE"),
                "below": statuses.count("BELOW"),
                "not_evaluable": statuses.count("NOT_EVALUABLE"),
                "rows_with_fail_code": sum(row.raw_fields.MEASURE_FAIL_CODE is not None for row in batch.rows),
                "out_of_range_serials": len({row.raw_fields.serial_number for row in out}),
            })
        return {"stations": stations, "computed_at": utc_now().isoformat(),
                "note": "Counts of recorded range statuses; not a diagnosis, cause or severity."}

    @router.get("/stations/overview", operation_id="stations_overview")
    def overview(request: Request):
        authenticate(request)
        with lock:
            fresh = cache.get("at") and time.monotonic() - cache["at"] < CACHE_SECONDS
            if not fresh:
                try:
                    cache["data"] = build(request.app.state.source)
                except Failure:
                    raise
                except Exception as error:  # driver errors map to the canonical codes
                    raise translate_source_exception(error) from None
                cache["at"] = time.monotonic()
            data = cache["data"]
        return {"request_id": request.scope["b_request_id"], "retrieved_at": utc_now().isoformat(),
                "status": "ok", "case_id": None, "error": None, "data": data}

    return router
