"""MCP server: the interface Copilot Studio (and the interim harness) connects to.

Tools only. Each tool calls a function in services.py and returns the same envelope
as the REST API. Descriptions come from copilot/tool_descriptions.md word for word.
"""

from mcp.server.fastmcp import FastMCP

from . import services

# stateless_http: no MCP session state on the server; case state lives in cases.py.
# json_response: plain JSON responses instead of SSE streams.
mcp = FastMCP("MAGNA TRACE", stateless_http=True, json_response=True)


@mcp.tool(description=(
    "Connectivity check for MAGNA TRACE. Returns a request_id, the retrieval time and the "
    "number of measurement rows currently readable in Oracle. Call it only when the user "
    "explicitly asks to test the connection. It contains no diagnostic information."
))
def health_echo() -> dict:
    return services.health_echo()


@mcp.tool(description=(
    "Opens a new diagnostic case for one test station and returns a snapshot: scope, up to five "
    "measurement findings with evidence IDs, data warnings, an assessment label and exactly one next "
    "step (a question with question_id, a data check, or escalation). "
    "Call it when the technician asks to investigate, check or explain a station, or asks what "
    "happened at a station. Do not call it again for the same station in the same conversation "
    "unless the technician asks for a new case or a different time range or serial number; reuse the "
    "existing case_id instead. Do not call it for general questions. "
    "Arguments: station_number (required, for example ST3003); time_from, time_to (optional, ISO date "
    "and time such as 2026-11-09 10:30); serial_number (optional)."
))
def open_case(station_number: str, time_from: str | None = None, time_to: str | None = None,
              serial_number: str | None = None) -> dict:
    return services.open_case(station_number, time_from, time_to, serial_number)


@mcp.tool(description=(
    "Returns the captured source record behind one evidence ID of a case: source table, raw stored "
    "values and limits, unit, raw fail code, timestamp, retrieval time and, for calculated values, the "
    "inputs and the rule. Call it when the technician asks where a number came from, asks for the "
    "source, raw value or limits, or doubts a finding. Use only evidence IDs that appeared in tool "
    "results of this case. Never invent or modify an evidence ID."
))
def get_evidence(case_id: str, evidence_id: str) -> dict:
    return services.get_evidence(case_id, evidence_id)


@mcp.tool(description=(
    "Records the technician's answer to the open case question as a technician report, and returns "
    "what changed, what is still open and the new next step. Observations from the database are "
    "never changed by it, so the findings are not repeated in the result. Call it every time the technician replies to the question you asked from the "
    "last tool result, even if the reply is short, uncertain or negative ('no', 'I don't know', "
    "'nothing was changed'). Call it before you answer the technician. Do not call it for new questions "
    "or requests that are not an answer to the open question. "
    "Arguments: case_id and question_id from the latest tool result; answer_text = the technician's "
    "words, unchanged; answer_kind = YES if the technician clearly confirms, NO if they clearly deny, "
    "UNKNOWN if unsure or unclear. When in doubt use UNKNOWN."
))
def record_answer(case_id: str, question_id: str, answer_text: str, answer_kind: str = "UNKNOWN") -> dict:
    return services.record_answer(case_id, question_id, answer_text, answer_kind)


@mcp.tool(description=(
    "Returns a short handover summary of a case: scope, findings with evidence IDs, technician reports, "
    "open questions, unresolved gaps and the next step. Call it when the technician asks for a summary, "
    "handover, report for the next shift, or to finish the investigation. Do not use it to answer "
    "questions about single measurements; use the case snapshot or get_evidence instead."
))
def get_handover(case_id: str) -> dict:
    # The agent only needs the ready-made text; REST keeps the structured fields for other clients.
    return services.get_handover(case_id, text_only=True)


@mcp.tool(description=(
    "Returns known station identifiers with their record counts. Call it only when the station the "
    "technician means is missing, unclear or not found, to offer valid choices. Do not call it before "
    "every case."
))
def list_stations() -> dict:
    return services.list_stations()
