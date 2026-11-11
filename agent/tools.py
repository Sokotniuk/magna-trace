"""The five diagnostic tools, executed against student B's REST API in-process.

Calls go through the real ASGI app (same validation, auth, envelopes and error handling as any
other client). Each tool returns (text for the technician, compact result for the model).
"""

import re

import httpx

from . import render

_DASHES = str.maketrans({c: "-" for c in "‐‑‒–—―−"})
_EVIDENCE = re.compile(r"^E-[0-9a-f]{32}-[1-9][0-9]*$")

# OpenAI-style tool definitions. The active case and open question are kept by the server per
# conversation, so the model never has to copy 32-character identifiers.
TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "open_case",
        "description": "Open a diagnostic case for one test station and show the technician the findings, warnings, "
                       "assessment and one question. Call it when the technician asks to investigate, check or "
                       "explain a station. Do not call it again for the same station unless they ask for a new "
                       "case, another time range or another serial.",
        "parameters": {"type": "object", "properties": {
            "station_number": {"type": "string", "description": "Station identifier, e.g. ST3003"},
            "from": {"type": "string", "description": "Optional start, ISO without timezone, e.g. 2026-11-09T10:30:00"},
            "to": {"type": "string", "description": "Optional end (exclusive), same format"},
            "serial_number": {"type": "string", "description": "Optional serial number"},
        }, "required": ["station_number"]}}},
    {"type": "function", "function": {
        "name": "get_evidence",
        "description": "Show the stored source behind one evidence ID of the active case. For 'where does this "
                       "deviation come from' use the finding's calculation ID; for a raw value or limit use its "
                       "evidence ID. Use only IDs from earlier tool results.",
        "parameters": {"type": "object", "properties": {
            "evidence_id": {"type": "string", "description": "Evidence ID exactly as returned"},
        }, "required": ["evidence_id"]}}},
    {"type": "function", "function": {
        "name": "record_answer",
        "description": "Record the technician's reply to the open question of the active case. Call it every time "
                       "the technician answers that question, even with 'no' or 'I don't know', before you reply. "
                       "Do not call it for new questions or requests.",
        "parameters": {"type": "object", "properties": {
            "answer_text": {"type": "string", "description": "The technician's words, unchanged"},
        }, "required": ["answer_text"]}}},
    {"type": "function", "function": {
        "name": "get_handover",
        "description": "Show the handover summary of the active case. Call it when the technician asks for a "
                       "summary, handover or report for the next shift.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_stations",
        "description": "List known station identifiers. Call it only when the station is missing, unclear or not found.",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "Optional case-sensitive part of the station identifier"},
        }}}},
]


_ARGUMENTS = {spec["function"]["name"]: set(spec["function"]["parameters"]["properties"]) for spec in TOOL_SPECS}


class Session:
    """Server-side state of one conversation: the active case and its open question."""

    def __init__(self) -> None:
        self.case_id: str | None = None
        self.question_id: str | None = None


class Toolbox:
    def __init__(self, app, api_key: str) -> None:
        self._app = app
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://backend.internal",
            headers={"X-API-Key": api_key}, timeout=60,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, **kwargs) -> dict:
        response = await self._client.request(method, path, **kwargs)
        return response.json()

    def lookup(self, case_id: str):
        """Read-only access to captured evidence of a case, for rendering serials and inputs."""
        def get(evidence_id: str) -> dict | None:
            try:
                with self._app.state.cases.locked(case_id) as case:
                    return case.evidence.get(evidence_id).model_dump(mode="json", by_alias=True)
            except Exception:
                return None
        return get

    @staticmethod
    def _failed(envelope: dict) -> tuple[str, dict]:
        code = (envelope.get("error") or {}).get("code", "SOURCE_UNAVAILABLE")
        return render.error(envelope), {"status": "error", "code": code}

    # --- tools ---------------------------------------------------------------

    async def open_case(self, session: Session, station_number: str, **scope) -> tuple[str, dict]:
        body = {"station_number": str(station_number).strip().upper()}
        body.update({k: v for k, v in scope.items() if k in ("from", "to", "serial_number") and v})
        envelope = await self._call("POST", "/api/v1/cases", json=body)
        if envelope.get("status") != "ok":
            return self._failed(envelope)
        snap, case_id = envelope["data"], envelope["case_id"]
        session.case_id = case_id
        action = snap["next_action"]
        session.question_id = action.get("question_id") if action["kind"] == "question" else None
        text = render.snapshot(case_id, snap, self.lookup(case_id))
        compact = {
            "status": "ok", "shown_to_technician": True, "request_id": envelope["request_id"],
            "open_question": action["text"] if session.question_id else None,
            # Values are included so the model can tell which finding a question such as
            # "where does 50.457 come from" refers to; it still never restates them.
            "findings": [{"measurement": f["measurement"], "range_status": f["range_status"],
                          "raw_value": f["raw_value"], "deviation": f["deviation"],
                          "evidence_id": f["evidence_id"], "calculation_id": f["calculation_evidence_id"]}
                         for f in snap["findings"]],
        }
        return text, compact

    def _resolve_evidence(self, session: Session, raw: str) -> str:
        value = str(raw).translate(_DASHES).strip().strip("`'\" ")
        if _EVIDENCE.match(value.lower().replace("e-", "E-", 1)):
            return value.lower().replace("e-", "E-", 1)
        tail = re.search(r"(\d+)$", value)  # a bare or shortened number refers to the active case
        return f"E-{session.case_id}-{int(tail.group(1))}" if tail and session.case_id else value

    async def get_evidence(self, session: Session, evidence_id: str) -> tuple[str, dict]:
        if not session.case_id:
            return "There is no active case yet. Tell me which station to investigate.", {"status": "error", "code": "NO_ACTIVE_CASE"}
        eid = self._resolve_evidence(session, evidence_id)
        envelope = await self._call("GET", f"/api/v1/cases/{session.case_id}/evidence/{eid}")
        if envelope.get("status") != "ok":
            return self._failed(envelope)
        item = envelope["data"]
        return render.evidence(item, self.lookup(session.case_id)), {
            "status": "ok", "shown_to_technician": True, "request_id": envelope["request_id"],
            "evidence_id": item["evidence_id"], "classification": item["classification"]}

    async def record_answer(self, session: Session, answer_text: str) -> tuple[str, dict]:
        if not session.case_id or not session.question_id:
            return ("There is no open question to answer in this conversation.",
                    {"status": "error", "code": "NO_OPEN_QUESTION"})
        envelope = await self._call("POST", f"/api/v1/cases/{session.case_id}/answers",
                                    json={"question_id": session.question_id, "answer_text": str(answer_text).strip()})
        if envelope.get("status") != "ok":
            return self._failed(envelope)
        snap = envelope["data"]
        session.question_id = None
        return render.answer(snap), {
            "status": "ok", "shown_to_technician": True, "request_id": envelope["request_id"],
            "report_evidence_id": snap["report_evidence_id"], "next_action_kind": snap["next_action"]["kind"]}

    async def get_handover(self, session: Session) -> tuple[str, dict]:
        if not session.case_id:
            return "There is no active case yet. Tell me which station to investigate.", {"status": "error", "code": "NO_ACTIVE_CASE"}
        envelope = await self._call("GET", f"/api/v1/cases/{session.case_id}/handover")
        if envelope.get("status") != "ok":
            return self._failed(envelope)
        return render.handover(session.case_id, envelope["data"], self.lookup(session.case_id)), {
            "status": "ok", "shown_to_technician": True, "request_id": envelope["request_id"]}

    async def list_stations(self, session: Session, q: str | None = None) -> tuple[str, dict]:
        params = {"limit": 100, **({"q": q} if q else {})}
        envelope = await self._call("GET", "/api/v1/stations", params=params)
        if envelope.get("status") != "ok":
            return self._failed(envelope)
        return render.stations(envelope["data"]), {
            "status": "ok", "shown_to_technician": True, "request_id": envelope["request_id"],
            "stations": [s["station_number"] for s in envelope["data"]["stations"]]}

    async def run(self, session: Session, name: str, args: dict) -> tuple[str, dict]:
        handlers = {"open_case": self.open_case, "get_evidence": self.get_evidence,
                    "record_answer": self.record_answer, "get_handover": self.get_handover,
                    "list_stations": self.list_stations}
        if name not in handlers:
            return f"Unknown tool {name}.", {"status": "error", "code": "UNKNOWN_TOOL"}
        # Models sometimes add arguments a tool does not take (e.g. a case_id); ignore those.
        accepted = _ARGUMENTS[name]
        args = {k: v for k, v in args.items() if k in accepted}
        try:
            return await handlers[name](session, **args)
        except TypeError:
            return "The tool was called with unusable arguments.", {"status": "error", "code": "BAD_ARGUMENTS"}
