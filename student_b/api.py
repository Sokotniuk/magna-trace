"""REST routes sharing the B2 models; no second LLM or direct SQL."""

from collections.abc import Callable
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request

from backend.app import schemas as s
from . import diagnostics
from .answers import record_answer as save_answer
from .cases import utc_now
from .evidence import EvidenceStore
from .source import Failure


def ok(request: Request, data: object, case_id: str | None = None) -> s.Success:
    return s.Success(request_id=request.scope["b_request_id"], retrieved_at=utc_now(), case_id=case_id, data=data)


def read_count(request: Request) -> int:
    value = request.app.state.source.count_measurements()
    if type(value) is not int or value < 0:
        raise Failure("SOURCE_UNAVAILABLE", "Source did not return a usable count")
    return value


def make_router(authenticate: Callable, development_routes: bool) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1", dependencies=[Depends(authenticate)],
        responses={status: {"model": s.ErrorResponse} for status in
                   (401, 404, 409, 413, 422, 429, 500, 503, 504)},
    )

    @router.post("/cases", operation_id="open_case", response_model=s.OpenCaseResponse)
    def open_case(body: s.OpenCaseRequest, request: Request):
        store, settings = request.app.state.cases, request.app.state.settings
        case = store.create(body)
        request.scope["b_case_id"] = case.case_id
        try:
            batch = request.app.state.source.fetch_measurements(body, limit=settings.row_limit)
            if not batch.rows:
                raise Failure("NO_DATA", "No measurements for the exact scope in error.scope", 404, body)
            if len(batch.rows) > settings.row_limit:
                raise Failure("SOURCE_UNAVAILABLE", "Source exceeded the requested row cap")
            for row in batch.rows:
                raw = row.raw_fields
                if raw.station_number != body.station_number or (body.serial_number is not None and raw.serial_number != body.serial_number):
                    raise Failure("SOURCE_UNAVAILABLE", "Source returned rows outside the requested scope")
            retrieved_at = utc_now()
            with store.locked(case.case_id) as current:
                # Publish evidence only after the complete snapshot validates.
                captured = EvidenceStore(case.case_id)
                findings = tuple(captured.capture(body, row, i, retrieved_at) for i, row in enumerate(batch.rows, 1))
                question_id = uuid4().hex
                scope = s.Scope(**body.model_dump(), row_count=batch.total_rows, captured_row_count=len(batch.rows), truncated=batch.truncated, coverage_warnings=batch.coverage_warnings)
                result = diagnostics.snapshot(scope, findings, question_id, retrieved_at)
                current.evidence = captured
                current.question_id = question_id
                current.snapshot = result
                current.transition("EVIDENCE_LOADED")
                current.transition("AWAITING_CLARIFICATION")
        except Exception as error:
            store.mark_failed(case.case_id, no_data=isinstance(error, Failure) and error.code == "NO_DATA")
            raise
        return ok(request, result, case.case_id)

    @router.get("/cases/{case_id}/evidence/{evidence_id}", operation_id="get_evidence", response_model=s.GetEvidenceResponse)
    def get_evidence(case_id: str, evidence_id: str, request: Request):
        with request.app.state.cases.locked(case_id) as case:
            return ok(request, case.evidence.get(evidence_id), case.case_id)

    @router.post("/cases/{case_id}/answers", operation_id="record_answer", response_model=s.RecordAnswerResponse)
    def record_answer(case_id: str, body: s.RecordAnswerRequest, request: Request):
        return ok(request, save_answer(request.app.state.cases, case_id, body), case_id)

    @router.get("/cases/{case_id}/handover", operation_id="get_handover", response_model=s.GetHandoverResponse)
    def get_handover(case_id: str, request: Request):
        with request.app.state.cases.locked(case_id) as case:
            if case.snapshot is None:
                raise Failure("INVALID_SCOPE", "Case has no captured snapshot to hand over", 409)
            result = diagnostics.handover(case.snapshot)
            if case.state == "NEXT_CHECK_OR_ESCALATE":
                case.transition("HANDOVER_READY")
            return ok(request, result, case.case_id)

    @router.get("/stations", operation_id="list_stations", response_model=s.ListStationsResponse)
    def list_stations(request: Request, q: str | None = Query(None, max_length=64), limit: int = Query(20, ge=1, le=100)):
        result = s.Stations.model_validate(request.app.state.source.list_stations(q, limit))
        if len(result.stations) > limit:
            raise Failure("SOURCE_UNAVAILABLE", "Source exceeded the station limit")
        return ok(request, result, None)

    if development_routes:
        @router.get("/health/echo", operation_id="health_echo", response_model=s.Success[dict[str, int]])
        def health_echo(request: Request):
            # Always fresh; no hardcoded historical count or mock-source fallback.
            return ok(request, {"measurement_rows": read_count(request)})

    return router
