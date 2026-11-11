"""Deterministic texts for the technician, rendered from B2 responses.

Values are copied from the backend objects, never recomputed. The chat shows these texts as
they are, so no number, status or ID can be changed by a language model on the way.
"""

from collections.abc import Callable

WARNING_TEXT = {
    "SOURCE_TIMEZONE_UNKNOWN": "Timestamps are shown as stored; the source timezone is unknown.",
    "SEMANTICS_UNKNOWN": "Fail code meaning is undocumented; shown raw, never treated as PASS or FAIL.",
    "RELATIONSHIPS_UNVERIFIED": "Rows are not verified to belong to one event.",
    "BOUND_EQUALITY_POLICY_PROVISIONAL": "A value equal to a limit counts as within limits (provisional policy).",
    "ROWID_NOT_DURABLE": "No durable row key; evidence is a snapshot taken at retrieval time.",
    "TIME_SCOPE_HALF_OPEN": "A time filter includes `from` and excludes `to`.",
    "TRUNCATED_SCOPE": "The result was truncated; narrow the scope for full coverage.",
    "UNIT_UNKNOWN": "At least one unit is not recorded.",
    "TECHNICIAN_REPORT_UNVERIFIED": "The technician report is not independently verified.",
    "REPORT_CONFLICT_NOT_AUTOMATICALLY_ASSESSED": "The report was not checked against the records automatically.",
    "REPORT_REVIEWED_NO_CONFLICT_IDENTIFIED": "The report was reviewed; no conflict with the records was identified.",
    "TECHNICIAN_REPORT_CONFLICT": "The report disputes recorded observations; both are kept.",
}

ERROR_TEXT = {
    "NO_DATA": "No measurement rows exist for this exact scope. This does not mean the station is healthy. "
               "Check the station number (I can list the known stations) or change the time range.",
    "INVALID_SCOPE": "The request does not match what the backend accepts (station, time format, or an "
                     "already answered question).",
    "SOURCE_UNAVAILABLE": "The Oracle source is unavailable. No data was retrieved and nothing is assumed.",
    "TIMEOUT": "The Oracle source timed out. No data was retrieved and nothing is assumed.",
    "EVIDENCE_NOT_FOUND": "That evidence ID does not exist in this case.",
    "EVIDENCE_NOT_IN_CASE": "That evidence ID belongs to a different case.",
    "CASE_NOT_FOUND_OR_EXPIRED": "This case is no longer available (expired or the server restarted). "
                                 "Ask me to investigate the station again to open a new case.",
    "UNAUTHORIZED": "The backend rejected the server credentials.",
    "NOT_COMPARABLE": "These records cannot be compared.",
}

Lookup = Callable[[str], dict | None]  # evidence_id -> evidence dict of the same case, or None


def _v(value) -> str:
    return "–" if value is None or value == "" else str(value)


def _warnings(codes) -> list[str]:
    return [f"- {WARNING_TEXT.get(code, code)}" for code in codes]


def _next(action: dict) -> str:
    if action["kind"] == "question":
        return f"**Question for you:** {action['text']}"
    return f"**Next step ({action['kind'].replace('_', ' ')}):** {action['text']}"


def _finding_rows(findings: list[dict], lookup: Lookup) -> tuple[list[str], set[tuple]]:
    lines = [
        "| Measurement | Serial | Recorded | Value | Limits | Status | Deviation | Fail code | Evidence | Calculation |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    origins: set[tuple] = set()
    for f in findings:
        raw = ((lookup(f["evidence_id"]) or {}).get("raw_fields")) or {}
        origins.add((raw.get("serial_number"), raw.get("BOOK_STAMP")))
        unit = f" {f['unit']}" if f.get("unit") else ""
        lines.append(
            f"| {f['measurement']} | {_v(raw.get('serial_number'))} | {_v(raw.get('BOOK_STAMP'))} | "
            f"{_v(f['raw_value'])}{unit} | {_v(f['raw_lower'])}..{_v(f['raw_upper'])} | {f['range_status']} | "
            f"{_v(f['deviation'])} | {_v(f['raw_fail_code']) if f['raw_fail_code'] is not None else 'none'} | "
            f"`{f['evidence_id']}` | `{f['calculation_evidence_id']}` |")
    return lines, origins


def snapshot(case_id: str, snap: dict, lookup: Lookup) -> str:
    scope, findings = snap["scope"], snap["findings"]
    lines = [
        f"**Case** `{case_id}` · station **{scope['station_number']}** · {scope['row_count']} measurement rows "
        f"in scope, {scope['captured_row_count']} captured · retrieved {snap['observations_retrieved_at']}",
        "",
    ]
    table, origins = _finding_rows(findings, lookup)
    lines += table
    breaches = [f for f in findings if f["range_status"] in ("ABOVE", "BELOW")]
    lines.append("")
    if not breaches:
        lines.append("No value outside its recorded limits was found in the captured rows; the rows shown are examples.")
    if len(findings) > 1 and len(origins) == 1 and None not in next(iter(origins)):
        serial, stamp = next(iter(origins))
        lines.append(f"All rows shown belong to serial {serial}, recorded {stamp}.")
    for f in findings:
        if f["range_status"] == "WITHIN_RECORDED_BOUNDS" and f["raw_fail_code"] is not None:
            lines.append(f"{f['measurement']} is listed because a fail code is recorded although the value is "
                         "within the recorded limits (code meaning unknown).")
        elif f["range_status"] == "NOT_EVALUABLE":
            lines.append(f"{f['measurement']} is listed because it could not be evaluated against the recorded "
                         f"limits ({', '.join(f['quality_flags']) or 'no flag'}).")
    more = len(snap["additional_evidence_ids"]) // 2
    if more:
        lines.append(f"{more} more captured row(s) are kept as evidence in this case.")
    lines += ["", "**Warnings**", *_warnings(snap["warnings"]), ""]
    lines.append(f"**Assessment (hypothesis): {snap['assessment']['label']}.** Recorded data alone cannot separate "
                 "an equipment-related from a product-related explanation. Unknown: "
                 + ", ".join(snap["assessment"]["unknowns"]).lower() + ".")
    lines += ["", _next(snap["next_action"])]
    return "\n".join(lines)


def evidence(item: dict, lookup: Lookup) -> str:
    eid, cls = item["evidence_id"], item["classification"]
    head = f"**Evidence** `{eid}` **({cls})**"
    if cls == "OBSERVED":
        raw = item["raw_fields"]
        unit = f" {raw['UNIT']}" if raw.get("UNIT") else ""
        code = f"{raw['MEASURE_FAIL_CODE']} (meaning unknown)" if raw.get("MEASURE_FAIL_CODE") is not None else "none"
        return "\n".join([
            head,
            f"- Source: `{item['source_table']}`, captured row {item['row_ordinal']} of this case; "
            f"retrieved {item['retrieved_at']}",
            f"- {item['measurement']}: station {raw['station_number']}, serial {_v(raw.get('serial_number'))}, "
            f"recorded {_v(raw.get('BOOK_STAMP'))} (timezone unknown)",
            f"- Raw value `{_v(raw.get('MEASURE_VALUE'))}`{unit}; recorded limits `{_v(raw.get('LOWER_LIMIT'))}`.."
            f"`{_v(raw.get('UPPER_LIMIT'))}`; fail code {code}",
        ])
    if cls == "CALCULATED":
        result = item["result"]
        lines = [head, f"- Rule: {item['rule']}",
                 "- Inputs: " + ", ".join(f"`{i}`" for i in item["input_evidence_ids"])]
        for ref in item["input_evidence_ids"]:
            raw = ((lookup(ref) or {}).get("raw_fields")) or {}
            if raw:
                unit = f" {raw['UNIT']}" if raw.get("UNIT") else ""
                lines.append(f"- Input `{ref}`: raw value `{_v(raw.get('MEASURE_VALUE'))}`{unit}, recorded limits "
                             f"`{_v(raw.get('LOWER_LIMIT'))}`..`{_v(raw.get('UPPER_LIMIT'))}`")
        flags = ", ".join(result["quality_flags"]) or "none"
        lines.append(f"- Result: {result['range_status']}, deviation **{_v(result['deviation'])}**; "
                     f"parsed value {_v(result['parsed_value'])}; quality flags: {flags}")
        return "\n".join(lines)
    return "\n".join([
        head,
        f"- Answer to question `{item['question_id']}`: \"{item['answer_text']}\"",
        f"- Reported {item['reported_at']}; attribution: {item['attribution']}; not independently verified",
    ])


def answer(snap: dict) -> str:
    report = snap["technician_reports"][-1]
    lines = [
        f"Recorded your answer as technician report `{snap['report_evidence_id']}` (not independently verified).",
        f"**What changed:** {snap['change_summary']}",
        f"**Unchanged:** the {len(snap['findings'])} findings shown and all captured evidence; "
        f"assessment {snap['assessment']['label']}.",
        "**Still open:** " + ", ".join(snap["assessment"]["unknowns"]).lower() + "; the report itself is unverified.",
        "",
        _next(snap["next_action"]),
    ]
    if report.get("conflict_evidence_ids"):
        lines.insert(2, "**Conflict:** the report disputes " + ", ".join(f"`{i}`" for i in report["conflict_evidence_ids"]))
    return "\n".join(lines)


def handover(case_id: str, data: dict, lookup: Lookup) -> str:
    scope = data["scope"]
    lines = [
        f"**MAGNA TRACE handover — case** `{case_id}`",
        f"Station **{scope['station_number']}** · {scope['row_count']} rows in scope, {scope['captured_row_count']} "
        f"captured · data retrieved {data['observations_retrieved_at']}",
        "",
        "**Observations**",
    ]
    table, _ = _finding_rows(data["observations"], lookup)
    lines += table
    lines += ["", f"**Assessment (hypothesis): {data['assessment']['label']}.**", ""]
    if data["technician_reports"]:
        lines.append("**Technician reports (not independently verified)**")
        lines += [f"- \"{r['answer_text']}\" — reported {r['reported_at']} [`{r['evidence_id']}`]"
                  for r in data["technician_reports"]]
    else:
        lines.append("**Technician reports:** none.")
    if data["open_questions"]:
        lines += ["", "**Open questions**", *[f"- {q}" for q in data["open_questions"]]]
    lines += ["", "**Unresolved**"]
    lines += [f"- {WARNING_TEXT.get(gap, gap)}" for gap in data["gaps"]]
    lines.append("- No approved maintenance procedure was consulted by this system.")
    lines += ["", _next(data["next_action"])]
    return "\n".join(lines)


def stations(data: dict) -> str:
    items = data["stations"]
    if not items:
        return "No station matches."
    return "**Known stations** (measurement rows): " + ", ".join(
        f"{s['station_number']} ({s['record_count']})" for s in items)


def error(envelope: dict) -> str:
    err = envelope.get("error") or {}
    code = err.get("code", "SOURCE_UNAVAILABLE")
    text = f"**{code}.** {ERROR_TEXT.get(code, err.get('message', 'The request failed.'))}"
    if err.get("scope"):
        scope = {k: v for k, v in err["scope"].items() if v is not None}
        text += f" Queried scope: `{scope}`."
    return text
