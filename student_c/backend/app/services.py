"""Service functions. REST routes and MCP tools both call these, never each other."""

import re
from datetime import datetime

from . import diagnostics, oracle_repo
from .cases import CASES, CaseNotFound
from .evidence import EvidenceNotFound, EvidenceNotInCase
from .schemas import error, normalize_id, ok, utc_now

_STATION = re.compile(r"^[A-Z0-9_-]{1,40}$")
_SERIAL = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")


def _source_error(exc: Exception) -> dict:
    if isinstance(exc, oracle_repo.SourceTimeout):
        return error("TIMEOUT", "Oracle query timed out. No data was returned.")
    return error("SOURCE_UNAVAILABLE", "Oracle is not reachable. No data was returned.")


def health_echo() -> dict:
    """G0 connectivity check: returns a live Oracle-derived value, nothing diagnostic."""
    try:
        rows = oracle_repo.count_measurements()
    except (oracle_repo.SourceTimeout, oracle_repo.SourceUnavailable) as exc:
        return _source_error(exc)
    return ok({"measurement_rows": str(rows)})


def list_stations() -> dict:
    try:
        stations = oracle_repo.list_stations()
    except (oracle_repo.SourceTimeout, oracle_repo.SourceUnavailable) as exc:
        return _source_error(exc)
    return ok({"stations": stations})


def _parse_time(label: str, raw: str | None) -> datetime | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return datetime.fromisoformat(str(raw).strip())
    except ValueError:
        raise ValueError(f"{label} must be an ISO date/time such as 2026-11-09 10:30") from None


def open_case(station_number: str, time_from: str | None = None, time_to: str | None = None,
              serial_number: str | None = None) -> dict:
    station = (station_number or "").strip().upper()
    if not _STATION.match(station):
        return error("INVALID_SCOPE", "station_number must look like ST3003.")
    serial = (serial_number or "").strip() or None
    if serial and not _SERIAL.match(serial):
        return error("INVALID_SCOPE", "serial_number contains unsupported characters.")
    try:
        t_from, t_to = _parse_time("time_from", time_from), _parse_time("time_to", time_to)
    except ValueError as exc:
        return error("INVALID_SCOPE", str(exc))
    if t_from and t_to and t_from > t_to:
        return error("INVALID_SCOPE", "time_from is after time_to.")

    scope = {
        "station_number": station,
        "serial_number": serial,
        "time_from": t_from.isoformat(sep=" ") if t_from else None,
        "time_to": t_to.isoformat(sep=" ") if t_to else None,
    }
    try:
        rows, truncated = oracle_repo.measurements_for_station(station, serial, t_from, t_to)
    except (oracle_repo.SourceTimeout, oracle_repo.SourceUnavailable) as exc:
        return _source_error(exc)
    if not rows:
        return error("NO_DATA", f"No measurement rows for scope {scope}. This does not mean the station is healthy; "
                                "check the station number or widen the time range.")

    retrieved_at = utc_now()
    case = CASES.create(scope, created_at=retrieved_at)
    with case.lock:
        snapshot = diagnostics.build_snapshot(case, rows, truncated, retrieved_at)
    return ok(snapshot, case_id=case.case_id)


MAX_ANSWER_CHARS = 2000


def record_answer(case_id: str, question_id: str, answer_text: str, answer_kind: str | None = None) -> dict:
    """Store the technician's answer as TECHNICIAN_REPORTED evidence and return the updated snapshot."""
    try:
        case = CASES.get(case_id)
    except CaseNotFound:
        return error("CASE_NOT_FOUND_OR_EXPIRED", "This case is not available (unknown, expired, or the server "
                                                  "restarted). Open a new case.")
    text = (answer_text or "").strip()
    if not text or len(text) > MAX_ANSWER_CHARS:
        return error("INVALID_SCOPE", f"answer_text must be 1 to {MAX_ANSWER_CHARS} characters.", case.case_id)
    kind = (answer_kind or "UNKNOWN").strip().upper()
    if kind not in diagnostics.ANSWER_KINDS:
        return error("INVALID_SCOPE", "answer_kind must be YES, NO or UNKNOWN.", case.case_id)

    with case.lock:
        question = case.open_question
        if question is None:
            return error("INVALID_SCOPE", "This case has no open question; the last one was already answered "
                                          "or none was asked.", case.case_id)
        if normalize_id(question_id) != question["question_id"].upper():
            return error("INVALID_SCOPE", f"question_id does not match the open question "
                                          f"{question['question_id']}.", case.case_id)
        recorded_at = utc_now()
        case.state = "ANSWER_RECORDED"
        answer_id = case.ledger.add("TECHNICIAN_REPORTED", {
            "question_id": question["question_id"],
            "question_text": question["text"],
            "answer_text": text,
            "answer_kind": kind,
            "answer_kind_source": "classified by the conversational agent; the raw answer_text is authoritative",
            "recorded_at": recorded_at,
            "attribution": "technician via agent; individual identity not available (shared connector key)",
            "note": "Reported by a person, not independently verified.",
        })
        snapshot = diagnostics.apply_answer(case, answer_id, kind, recorded_at)
    # The case keeps the full snapshot (handover uses it). The response leaves out the findings:
    # an answer never changes them, and repeating them roughly doubled the size of this call.
    view = {k: v for k, v in snapshot.items() if k != "findings"}
    view["findings_unchanged"] = {
        "note": "Recorded findings are unchanged by a technician answer.",
        "evidence_ids": [f["evidence_id"] for f in snapshot["findings"]],
    }
    return ok(view, case_id=case.case_id)


_EVIDENCE_ID = re.compile(r"E-[0-9A-F]{6}-\d{3,}")


def get_handover(case_id: str, text_only: bool = False) -> dict:
    """Handover summary from case state only; no new Oracle query, so nothing shown can drift.

    text_only=True (used by the agent tool) returns the ready-made text and the evidence IDs it
    cites. The structured fields repeat the same content and roughly triple the size, which pushed
    a model request over a per-request token limit.
    """
    try:
        case = CASES.get(case_id)
    except CaseNotFound:
        return error("CASE_NOT_FOUND_OR_EXPIRED", "This case is not available (unknown, expired, or the server "
                                                  "restarted). Open a new case.")
    with case.lock:
        handover = diagnostics.build_handover(case)
        if case.open_question is None:
            case.state = "HANDOVER_READY"
    if text_only:
        handover = {"case_id": handover["case_id"], "text": handover["text"],
                    "evidence_ids": list(dict.fromkeys(_EVIDENCE_ID.findall(handover["text"])))}
    return ok(handover, case_id=case.case_id)


def get_evidence(case_id: str, evidence_id: str) -> dict:
    try:
        case = CASES.get(case_id)
    except CaseNotFound:
        return error("CASE_NOT_FOUND_OR_EXPIRED", "This case is not available (unknown, expired, or the server "
                                                  "restarted). Open a new case.")
    try:
        item = case.ledger.get(evidence_id)
    except EvidenceNotInCase:
        return error("EVIDENCE_NOT_IN_CASE", f"{evidence_id} does not belong to case {case.case_id}.", case.case_id)
    except EvidenceNotFound:
        return error("EVIDENCE_NOT_FOUND", f"{evidence_id} does not exist in case {case.case_id}.", case.case_id)
    return ok({**item, "message": diagnostics.render_evidence(item)}, case_id=case.case_id)
