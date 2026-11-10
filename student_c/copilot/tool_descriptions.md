# Tool descriptions for the MCP server (C → B)

B pastes these texts as the `description` of each MCP tool in `backend/app/mcp_server.py`.
The agent (GPT harness now, Copilot Studio later) decides when to call a tool **only from these texts**, so keep them word for word; changes go through C.

Argument names are proposals; B confirms the final names. `from` is a reserved word in Python, so the time range uses `time_from` / `time_to`.

---

## health_echo — development only, remove after G0

Connectivity check for MAGNA TRACE. Returns a request_id, the retrieval time and the number of measurement rows currently readable in Oracle. Call it only when the user explicitly asks to test the connection. It contains no diagnostic information.

Arguments: none.

## open_case

Opens a new diagnostic case for one test station and returns a snapshot: scope, up to five measurement findings with evidence IDs, data warnings, an assessment label and exactly one next step (a question with question_id, a data check, or escalation).
Call it when the technician asks to investigate, check or explain a station, or asks what happened at a station.
Do not call it again for the same station in the same conversation unless the technician asks for a new case or a different time range or serial number; reuse the existing case_id instead.
Do not call it for general questions.

Arguments: `station_number` (required, for example ST3003); `time_from`, `time_to` (optional, as given by the technician); `serial_number` (optional).

## get_evidence

Returns the captured source record behind one evidence ID of a case: source table, raw stored values and limits, unit, raw fail code, timestamp, retrieval time and, for calculated values, the inputs and the rule.
Call it when the technician asks where a number came from, asks for the source, raw value or limits, or doubts a finding.
Use only evidence IDs that appeared in tool results of this case. Never invent or modify an evidence ID.

Arguments: `case_id`, `evidence_id` (both required).

## record_answer

Records the technician's answer to the open case question as a technician report, and returns the updated snapshot with what changed and the new next step. Observations from the database are never changed by it.
Call it every time the technician replies to the question you asked from the last tool result — even if the reply is short, uncertain or negative ("no", "I don't know", "nothing was changed"). Call it before you answer the technician.
Do not call it for new questions or requests that are not an answer to the open question.

Arguments: `case_id`, `question_id` (both from the latest tool result), `answer_text` (the technician's words, unchanged), `answer_kind` (`YES` if the technician clearly confirms, `NO` if they clearly deny, `UNKNOWN` if unsure or unclear; when in doubt `UNKNOWN`).

`answer_kind` is the agent's reading of the answer and is stored as such; the raw `answer_text` stays authoritative. The backend picks the next step from fixed templates by `answer_kind`; the assessment label does not change.

## get_handover

Returns a short handover summary of a case: scope, findings with evidence IDs, technician reports, open questions, unresolved gaps and the next step.
Call it when the technician asks for a summary, handover, report for the next shift, or to finish the investigation.
Do not use it to answer questions about single measurements; use the case snapshot or get_evidence instead.

Arguments: `case_id` (required).

## list_stations

Returns known station identifiers with their record counts.
Call it only when the station the technician means is missing, unclear or not found, to offer valid choices.
Do not call it before every case.

Arguments: `query` (optional text filter), `limit` (optional).
