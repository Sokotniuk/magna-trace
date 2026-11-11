"""The five diagnostic tools, executed against student B's REST API in-process.

Calls go through the real ASGI app (same validation, auth, envelopes and error handling as any
other client). Each tool returns (text for the technician, compact result for the model).
"""

import re

import httpx

from . import guidance, render
from .auth import current_employee

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
        "description": "Show the stored source behind a finding of the active case. Give either evidence_id "
                       "(exactly as returned earlier) or the measurement name of a finding shown in the case table. "
                       "For 'where does this deviation come from' use kind=calculation; for a raw value or limit "
                       "use kind=observation.",
        "parameters": {"type": "object", "properties": {
            "evidence_id": {"type": "string", "description": "Evidence ID exactly as returned"},
            "measurement": {"type": "string", "description": "Measurement name of a finding in the case table, e.g. 'Weld Time'"},
            "kind": {"type": "string", "enum": ["calculation", "observation"],
                     "description": "With measurement: calculation (deviation) or observation (raw row)"},
        }, "required": []}}},
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
    def __init__(self, app, api_key: str, internal_token: str) -> None:
        self._app = app
        # The internal token passes the employee gate for these in-process calls only.
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://backend.internal",
            headers={"X-API-Key": api_key, "X-Trace-Internal": internal_token}, timeout=60,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, **kwargs) -> dict:
        employee = current_employee.get()
        if employee:
            kwargs["headers"] = {**kwargs.get("headers", {}), "X-Trace-Employee": employee}
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
    def _failed(envelope: dict, session: Session | None = None) -> tuple[str, dict]:
        code = (envelope.get("error") or {}).get("code", "SOURCE_UNAVAILABLE")
        if session is not None and code == "CASE_NOT_FOUND_OR_EXPIRED":
            session.case_id = session.question_id = None
        return render.error(envelope), {"status": "error", "code": code}

    # --- tools ---------------------------------------------------------------

    async def open_case(self, session: Session, station_number: str, **scope) -> tuple[str, dict]:
        # A failed scope switch must not leave an old question as the answer target.
        session.case_id = session.question_id = None
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
        # D41: likely causes and actions for out-of-range findings, placed before the question.
        block = guidance.diagnosis_block(guidance.case_rows(self._app.state.cases, case_id), snap["findings"])
        if block:
            marker = "\n\n**Question for you:**"
            text = text.replace(marker, block + marker, 1) if marker in text else text + block
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
        tail = re.fullmatch(r"([1-9][0-9]*)", value)  # explicit local ordinal only, never repair an invented ID
        return f"E-{session.case_id}-{int(tail.group(1))}" if tail and session.case_id else value

    def _finding_evidence(self, case_id: str, measurement: str, kind: str) -> list[str]:
        """IDs of displayed findings with exactly this measurement name (case-insensitive), from the stored snapshot."""
        try:
            with self._app.state.cases.locked(case_id) as case:
                findings = case.snapshot.findings if case.snapshot is not None else ()
        except Exception:
            return []
        wanted = " ".join(str(measurement).split()).casefold()
        field = "evidence_id" if kind == "observation" else "calculation_evidence_id"
        return [getattr(f, field) for f in findings if " ".join(f.measurement.split()).casefold() == wanted]

    def evidence_id_in_text(self, session: Session, text: str) -> str | None:
        """Full evidence ID in a technician message whose case exists (web chat only, D38).
        A different existing case becomes the active one; IDs of unknown cases are ignored."""
        found = re.search(r"\b[Ee]-([0-9a-f]{32})-[1-9][0-9]*\b", str(text).translate(_DASHES))
        if not found:
            return None
        eid = "E-" + found.group(0)[2:]
        if found.group(1) == session.case_id or self._adopt_case(session, eid):
            return eid
        return None

    def _adopt_case(self, session: Session, evidence_id: str | None) -> str | None:
        """Web chat only (D38): a full evidence ID copied from the dashboard names its case. If that case
        exists in the store, continue the conversation on it, with its open question if one is waiting.
        Unknown cases are not adopted, so their IDs keep failing as before (audit F04)."""
        if not evidence_id:
            return None
        value = str(evidence_id).translate(_DASHES).strip().strip("`'\" ")
        match = re.fullmatch(r"[Ee]-([0-9a-f]{32})-[1-9][0-9]*", value)
        if not match or match.group(1) == session.case_id:
            return None
        try:
            with self._app.state.cases.locked(match.group(1)) as case:
                waiting = case.question_id if case.state == "AWAITING_CLARIFICATION" else None
        except Exception:
            return None
        session.case_id, session.question_id = match.group(1), waiting
        return match.group(1)

    async def get_evidence(self, session: Session, evidence_id: str | None = None, measurement: str | None = None,
                           kind: str = "calculation", adopt_case: bool = False) -> tuple[str, dict]:
        adopted = self._adopt_case(session, evidence_id) if adopt_case else None
        if adopted:
            text, result = await self.get_evidence(session, evidence_id, measurement, kind)
            return (f"Continuing with case `{adopted}` from the dashboard.\n\n{text}",
                    {**result, "adopted_case_id": adopted})
        if not session.case_id:
            return "There is no active case yet. Tell me which station to investigate.", {"status": "error", "code": "NO_ACTIVE_CASE"}
        if not evidence_id and measurement:
            # Resolved only against findings the backend already showed; nothing is guessed (audit F04).
            matches = self._finding_evidence(session.case_id, measurement, kind)
            if len(matches) != 1:
                reason = ("is not among the findings shown for this case" if not matches
                          else "appears in more than one finding; name the evidence ID from the table")
                return (f"\"{measurement}\" {reason}.", {"status": "error", "code": "EVIDENCE_NOT_FOUND"})
            evidence_id = matches[0]
        if not evidence_id:
            return ("Name the measurement or the evidence ID from the table.", {"status": "error", "code": "BAD_ARGUMENTS"})
        eid = self._resolve_evidence(session, evidence_id)
        if not _EVIDENCE.fullmatch(eid):
            return self._failed({"error": {"code": "EVIDENCE_NOT_FOUND"}}, session)
        envelope = await self._call("GET", f"/api/v1/cases/{session.case_id}/evidence/{eid}")
        if envelope.get("status") != "ok":
            return self._failed(envelope, session)
        item = envelope["data"]
        text = render.evidence(item, self.lookup(session.case_id))
        if item["classification"] == "CALCULATED" and item.get("input_evidence_ids"):
            # D41: for a deviation, explain likely causes and what to do for that measurement.
            source = self.lookup(session.case_id)(item["input_evidence_ids"][0]) or {}
            raw = source.get("raw_fields") or {}
            result = item.get("result") or {}
            text += guidance.measurement_block(
                guidance.case_rows(self._app.state.cases, session.case_id), source.get("measurement", ""),
                result.get("range_status", ""), raw.get("MEASURE_VALUE"), raw.get("UNIT"),
                raw.get("LOWER_LIMIT"), raw.get("UPPER_LIMIT"), result.get("deviation"))
        return text, {
            "status": "ok", "shown_to_technician": True, "request_id": envelope["request_id"],
            "evidence_id": item["evidence_id"], "classification": item["classification"]}

    async def record_answer(self, session: Session, answer_text: str) -> tuple[str, dict]:
        if not session.case_id or not session.question_id:
            return ("There is no open question to answer in this conversation.",
                    {"status": "error", "code": "NO_OPEN_QUESTION"})
        envelope = await self._call("POST", f"/api/v1/cases/{session.case_id}/answers",
                                    json={"question_id": session.question_id, "answer_text": str(answer_text).strip()})
        if envelope.get("status") != "ok":
            return self._failed(envelope, session)
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
            return self._failed(envelope, session)
        text = render.handover(session.case_id, envelope["data"], self.lookup(session.case_id))
        text += guidance.diagnosis_block(guidance.case_rows(self._app.state.cases, session.case_id),
                                         envelope["data"].get("observations", []))
        return text, {
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
        if name == "get_evidence" and not args.get("evidence_id") and isinstance(args.get("calculation_id"), str):
            # The compact case result names deviation sources "calculation_id"; models echo that name.
            args = {**args, "evidence_id": args["calculation_id"], "kind": "calculation"}
        args = {k: v for k, v in args.items() if k in accepted}
        if name == "get_evidence":
            args["adopt_case"] = True  # set by the web chat only, never by the model or MCP
        try:
            return await handlers[name](session, **args)
        except TypeError:
            return "The tool was called with unusable arguments.", {"status": "error", "code": "BAD_ARGUMENTS"}
