"""Build the diagnostic snapshot for a case (architecture §3 and §5, AGENTS.md §7.5).

Every displayed fact gets an evidence ID. The assessment is UNDETERMINED in P0: equipment and
product explanations are listed as unverified hypotheses with what would distinguish them.
The next action comes from a fixed list of templates, never from generated text.
"""

import copy
from collections import Counter, defaultdict

from . import measurements as m
from .cases import Case

SOURCE_TABLE = "HACKATON.SNO_MEASUREMENT_DATA"
MAX_FINDINGS = 5

RAW_FIELDS = (
    "station_number", "station_desc", "part_number", "part_desc", "workorder_number", "workorder_desc",
    "serial_number", "measure_step_number", "measure_name", "unit", "measure_value",
    "lower_limit", "upper_limit", "nominal", "tolerance", "measure_fail_code", "book_stamp",
    "measure_type", "lower_intervention_limit", "upper_intervention_limit",
    "lower_scrap_limit", "upper_scrap_limit",
)


def build_snapshot(case: Case, rows: list[dict], truncated: bool, retrieved_at: str) -> dict:
    ledger = case.ledger
    station = case.scope["station_number"]

    evaluated = []  # (row, evaluation, observed_id, calculated_id)
    for row in rows:
        observed_id = ledger.add("OBSERVED", {
            "source_table": SOURCE_TABLE,
            "row_locator": row["row_locator"],
            "row_locator_note": "Oracle ROWID at retrieval time; not a verified business key",
            "query_scope": case.scope,
            "retrieved_at": retrieved_at,
            "fields": {k: row.get(k) for k in RAW_FIELDS},
        })
        ev = m.evaluate(row["measure_value"], row["lower_limit"], row["upper_limit"],
                        row["unit"], row["measure_fail_code"])
        calculated_id = None
        if ev.range_status in (m.ABOVE, m.BELOW):
            side = "upper" if ev.range_status == m.ABOVE else "lower"
            calculated_id = ledger.add("CALCULATED", {
                "inputs": [observed_id],
                "rule": ("deviation = value - upper_limit" if side == "upper" else "deviation = lower_limit - value")
                        + "; Decimal arithmetic on the raw strings; bounds inclusive (provisional)",
                "value": m.fmt(ev.value), "lower_limit": m.fmt(ev.lower), "upper_limit": m.fmt(ev.upper),
                "range_status": ev.range_status, "deviation": m.fmt(ev.deviation), "unit": row["unit"],
            })
        evaluated.append((row, ev, observed_id, calculated_id))

    abnormal = [e for e in evaluated if e[1].range_status in (m.ABOVE, m.BELOW)]
    coded_in_range = [e for e in evaluated
                      if e[1].range_status == m.WITHIN and e[0]["measure_fail_code"] is not None]
    not_evaluable = [e for e in evaluated if e[1].range_status == m.NOT_EVALUABLE]

    ordered = abnormal + coded_in_range + not_evaluable
    findings = [_finding(e) for e in ordered[:MAX_FINDINGS]]

    status_counts = Counter(e[1].range_status for e in evaluated)
    serials = sorted({r["serial_number"] for r in rows})
    summary = {
        "measurement_rows": len(rows),
        "serials": len(serials),
        "measurement_names": len({r["measure_name"] for r in rows}),
        "range_status_counts": {s: status_counts.get(s, 0) for s in (m.ABOVE, m.BELOW, m.WITHIN, m.NOT_EVALUABLE)},
        "rows_with_fail_code": sum(1 for r in rows if r["measure_fail_code"] is not None),
        "time_span": [rows[0]["book_stamp"], rows[-1]["book_stamp"]] if rows else None,
    }

    patterns, pattern_id = _abnormal_pattern(ledger, abnormal, serials)

    snapshot = {
        "scope": {**case.scope, "station_desc": rows[0]["station_desc"] if rows else None,
                  "retrieved_at": retrieved_at, "truncated": truncated},
        "summary": summary,
        "findings": findings,
        "more_findings": max(0, len(ordered) - MAX_FINDINGS),
        "patterns": patterns,
        "assessment": _assessment(station, patterns),
        "next_action": _next_action(case, station, patterns, pattern_id, coded_in_range),
        "warnings": _warnings(rows, truncated),
    }
    snapshot["message"] = render_snapshot(case.case_id, snapshot)
    case.state = "AWAITING_CLARIFICATION" if snapshot["next_action"]["kind"] == "QUESTION" else "EVIDENCE_LOADED"
    case.open_question = snapshot["next_action"] if snapshot["next_action"]["kind"] == "QUESTION" else None
    case.snapshot = snapshot
    return snapshot


def _listed_because(row: dict, ev) -> str:
    """Why this row is in the findings. Gives the agent wording so it does not invent labels."""
    if ev.range_status == m.ABOVE:
        return "value above the recorded upper limit"
    if ev.range_status == m.BELOW:
        return "value below the recorded lower limit"
    if ev.range_status == m.WITHIN and row["measure_fail_code"] is not None:
        return "fail code recorded although the value is within the recorded limits (code meaning unknown)"
    return "value could not be evaluated against the recorded limits"


def _finding(entry) -> dict:
    row, ev, observed_id, calculated_id = entry
    # listed_because only where the status alone does not explain the row (saves tokens per finding).
    extra = {} if ev.range_status in (m.ABOVE, m.BELOW) else {"listed_because": _listed_because(row, ev)}
    return {
        **extra,
        "measurement": row["measure_name"],
        "serial_number": row["serial_number"],
        "book_stamp": row["book_stamp"],
        "raw_value": row["measure_value"],
        "raw_lower": row["lower_limit"],
        "raw_upper": row["upper_limit"],
        "unit": row["unit"],
        "range_status": ev.range_status,
        "deviation": m.fmt(ev.deviation),
        "quality_flags": list(ev.flags),
        "raw_fail_code": row["measure_fail_code"],
        "evidence_id": observed_id,
        "calculation_evidence_id": calculated_id,
    }


def _abnormal_pattern(ledger, abnormal, serials) -> tuple[list[dict], str | None]:
    """Group abnormal rows by (serial, timestamp). A within-case count, not a cause."""
    if not abnormal:
        return [], None
    groups: dict[tuple, list] = defaultdict(list)
    for row, ev, observed_id, _ in abnormal:
        groups[(row["serial_number"], row["book_stamp"])].append((row["measure_name"], observed_id))
    affected = {serial for serial, _ in groups}
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    # The member evidence IDs live in the pattern's CALCULATED evidence, not in the snapshot:
    # they duplicate the findings' IDs and only cost tokens there.
    patterns = [{
        "serial_number": serial,
        "book_stamp": stamp,
        "abnormal_measurements": [name for name, _ in items],
    } for (serial, stamp), items in ordered]
    pattern_id = ledger.add("CALCULATED", {
        "inputs": [oid for _, items in ordered for _, oid in items],
        "rule": "group rows with range_status ABOVE/BELOW by (serial_number, book_stamp) within this case",
        "groups": [{k: p[k] for k in ("serial_number", "book_stamp", "abnormal_measurements")} for p in patterns],
        "serials_in_scope": len(serials),
        "serials_with_abnormal_rows": len(affected),
        "serials_without_abnormal_rows": len(serials) - len(affected),
        "note": "Same serial and timestamp is a recorded coincidence, not a verified single event or cause.",
    })
    for p in patterns:
        p["pattern_evidence_id"] = pattern_id
    return patterns, pattern_id


def _assessment(station: str, patterns: list[dict]) -> dict:
    top = patterns[0] if patterns else None
    unit = f"serial {top['serial_number']}" if top else "the affected unit"
    return {
        "label": "UNDETERMINED",
        "is_hypothesis": True,
        "basis": "Equipment/product classification is disabled in P0; recorded data alone cannot "
                 "separate an equipment-related from a product-related explanation.",
        "hypotheses": [
            {"type": "EQUIPMENT_RELATED",
             "statement": f"Tool, fixture or setup at {station} during this test.",
             "would_be_supported_by": ["other serials abnormal at the same time here",
                                       "a reported tool/fixture/setup change"]},
            {"type": "PRODUCT_RELATED",
             "statement": f"A condition of {unit} itself.",
             "would_be_supported_by": ["same serial abnormal at other stations",
                                       "a reported part or material defect"]},
        ],
    }


def _next_action(case: Case, station: str, patterns, pattern_id, coded_in_range) -> dict:
    if patterns:
        top = patterns[0]
        return {
            "kind": "QUESTION",
            "question_id": f"Q-{case.short}-1",
            "text": f"Were any tool, fixture or setup changes made at {station} around "
                    f"{top['book_stamp']} (serial {top['serial_number']})?",
            "purpose": "Distinguish an equipment-related from a product-related explanation.",
            "basis_evidence_ids": [pattern_id],
        }
    if coded_in_range:
        return {
            "kind": "DATA_CHECK",
            "text": "Fail code values are recorded on rows that are within recorded limits. "
                    "Confirm the meaning of the code with process engineering before interpreting it.",
            "purpose": "Code semantics are undocumented.",
            "basis_evidence_ids": [e[2] for e in coded_in_range[:MAX_FINDINGS]],
        }
    return {
        "kind": "DATA_CHECK",
        "text": "No recorded limit breaches in this scope. Widen the time range or check another station.",
        "purpose": "No abnormal recorded values to investigate in the requested scope.",
        "basis_evidence_ids": [],
    }


def _warnings(rows: list[dict], truncated: bool) -> list[str]:
    warnings = [
        "Timestamps as stored; source timezone unknown.",
        "Only LOWER/UPPER_LIMIT evaluated, bounds inclusive (provisional); intervention and scrap "
        "limits are in the evidence but not interpreted.",
        "No verified unique row key; evidence is a snapshot taken at retrieval time.",
    ]
    if any(r["measure_fail_code"] is not None for r in rows):
        warnings.append("Fail code meaning undocumented; shown raw, never treated as PASS or FAIL.")
    if truncated:
        warnings.append(f"Result truncated at {len(rows)} rows; narrow the scope for full coverage.")
    return warnings


# --- Technician answer ------------------------------------------------------

ANSWER_KINDS = ("YES", "NO", "UNKNOWN")


def apply_answer(case: Case, answer_evidence_id: str, answer_kind: str, recorded_at: str) -> dict:
    """Update the snapshot after a technician answer. Oracle observations are never changed.

    The answer is evidence (TECHNICIAN_REPORTED), not proof: per product v1.4 the assessment stays
    UNDETERMINED without independent evidence. Only the next step changes, from fixed templates.
    """
    question = case.open_question
    snapshot = copy.deepcopy(case.snapshot)
    station = case.scope["station_number"]
    top = snapshot["patterns"][0] if snapshot["patterns"] else None
    affected = {p["serial_number"] for p in snapshot["patterns"]}
    unaffected = snapshot["summary"]["serials"] - len(affected)
    serial = top["serial_number"] if top else "the affected serial"
    when = top["book_stamp"] if top else "the affected test"
    basis = [answer_evidence_id] + (question.get("basis_evidence_ids") or [])

    if answer_kind == "YES":
        what_changed = [f"Technician reports a tool, fixture or setup change at {station} around {when}."]
        still_open = [
            "The report is not independently verified.",
            f"Whether serial {serial} is also abnormal at other stations (product-related explanation) "
            "is not checked: cross-station comparison is not available yet.",
        ]
        next_action = {
            "kind": "ESCALATION",
            "text": f"Have maintenance verify the reported change at {station} against the approved setup "
                    f"procedure and record the result. In the recorded data, {unaffected} other serial(s) at "
                    f"this station have no limit breaches; only serial {serial} at {when} does.",
            "purpose": "Confirm or rule out the reported change as the equipment-related explanation.",
            "basis_evidence_ids": basis,
        }
    elif answer_kind == "NO":
        what_changed = [f"Technician reports no tool, fixture or setup change at {station} around {when}."]
        still_open = [
            "Equipment-related causes without a recorded change are not excluded.",
            f"Whether serial {serial} is abnormal at other stations is not checked: cross-station "
            "comparison is not available yet.",
        ]
        next_action = {
            "kind": "ESCALATION",
            "text": f"Escalate to quality engineering with this case: check serial {serial} and its part "
                    f"history outside {station}. Recorded data at {station} shows {unaffected} other serial(s) "
                    "without limit breaches.",
            "purpose": "Test the product-related explanation, which station data alone cannot do.",
            "basis_evidence_ids": basis,
        }
    else:
        what_changed = ["Technician could not confirm whether a change was made."]
        still_open = ["Whether a tool, fixture or setup change happened is unknown."]
        next_action = {
            "kind": "DATA_CHECK",
            "text": f"Check the shift or maintenance log for {station} around {when}. If no record exists, "
                    "escalate to the shift lead with this case.",
            "purpose": "Obtain a recorded answer to the open question.",
            "basis_evidence_ids": basis,
        }

    snapshot["assessment"]["note"] = ("Technician reports are recorded as evidence but do not change the "
                                      "assessment without independent data.")
    for hyp in snapshot["assessment"]["hypotheses"]:
        if hyp["type"] == "EQUIPMENT_RELATED":
            hyp.setdefault("technician_reports", []).append(
                {"evidence_id": answer_evidence_id, "answer_kind": answer_kind})

    unchanged = ["Recorded measurements and their evidence.",
                 f"Assessment label: {snapshot['assessment']['label']}."]
    # Ready-made text so the agent does not have to assemble (and drop parts of) the update.
    message = "\n".join(
        [f"Recorded your answer as technician report `{answer_evidence_id}` (not independently verified)."]
        + ["What changed: " + " ".join(what_changed)]
        + ["Unchanged: " + " ".join(unchanged)]
        + ["Still open:"] + [f"- {item}" for item in still_open]
        + [f"Next step ({next_action['kind']}): {next_action['text']}"]
    )
    snapshot["case_update"] = {
        "question_id": question["question_id"],
        "answer_evidence_id": answer_evidence_id,
        "answer_kind": answer_kind,
        "recorded_at": recorded_at,
        "what_changed": what_changed,
        "unchanged": unchanged,
        "still_open": still_open,
        "message": message,
    }
    snapshot["message"] = message  # the ready text of this tool result is the case update
    snapshot["next_action"] = next_action

    case.answers.append({"question_id": question["question_id"], "evidence_id": answer_evidence_id,
                         "answer_kind": answer_kind, "recorded_at": recorded_at})
    case.open_question = None
    case.state = "NEXT_CHECK_OR_ESCALATE"
    case.snapshot = snapshot
    return snapshot


# --- Handover ---------------------------------------------------------------

def build_handover(case: Case) -> dict:
    """Short summary for the next shift, built only from case state (no new Oracle query)."""
    snap = case.snapshot
    scope = snap["scope"]
    reports = [case.ledger.get(a["evidence_id"]) for a in case.answers]
    update = snap.get("case_update") or {}
    open_questions = [case.open_question] if case.open_question else []

    findings = [{k: f[k] for k in ("measurement", "serial_number", "book_stamp", "raw_value", "raw_lower",
                                   "raw_upper", "unit", "range_status", "deviation", "raw_fail_code",
                                   "evidence_id", "calculation_evidence_id")} for f in snap["findings"]]
    gaps = list(update.get("still_open") or []) + [
        "Meaning of MEASURE_FAIL_CODE values is undocumented.",
        "No approved maintenance procedure was consulted by this system.",
    ]

    lines = [
        f"MAGNA TRACE handover - case {case.case_id}",
        f"Scope: {scope['station_number']} ({scope.get('station_desc') or 'no description'}); "
        f"time {scope.get('time_from') or 'all'} to {scope.get('time_to') or 'all'}; "
        f"serial {scope.get('serial_number') or 'all'}; data retrieved {scope['retrieved_at']} UTC.",
        f"Data: {snap['summary']['measurement_rows']} rows, {snap['summary']['serials']} serials; "
        f"status counts {snap['summary']['range_status_counts']}; "
        f"{snap['summary']['rows_with_fail_code']} rows carry a fail code.",
        "Observations:",
    ]
    for f in findings:
        dev = f" by {f['deviation']}" if f["deviation"] else ""
        lines.append(f"  - {f['measurement']} = {f['raw_value']} {f['unit'] or ''} (limits {f['raw_lower']}..{f['raw_upper']}): "
                     f"{f['range_status']}{dev}; serial {f['serial_number']} at {f['book_stamp']}; "
                     f"code {f['raw_fail_code'] if f['raw_fail_code'] is not None else 'none'} [{f['evidence_id']}]")
    if snap["more_findings"]:
        lines.append(f"  - plus {snap['more_findings']} more, available as evidence in the case.")
    lines.append(f"Assessment (hypothesis): {snap['assessment']['label']}. {snap['assessment']['basis']}")
    lines.append("Technician reports:" if reports else "Technician reports: none.")
    for r in reports:
        lines.append(f"  - Q: {r['question_text']} A: \"{r['answer_text']}\" ({r['answer_kind']}, "
                     f"{r['recorded_at']}, not independently verified) [{r['evidence_id']}]")
    for q in open_questions:
        lines.append(f"Open question: {q['text']} [{q['question_id']}]")
    lines.append("Unresolved:")
    lines.extend(f"  - {g}" for g in gaps)
    lines.append(f"Next step ({snap['next_action']['kind']}): {snap['next_action']['text']}")

    return {
        "case_id": case.case_id,
        "scope": scope,
        "summary": snap["summary"],
        "observations": findings,
        "more_findings": snap["more_findings"],
        "assessment": {"label": snap["assessment"]["label"], "basis": snap["assessment"]["basis"],
                       "note": snap["assessment"].get("note")},
        "technician_reports": [{k: r[k] for k in ("evidence_id", "question_id", "question_text", "answer_text",
                                                  "answer_kind", "recorded_at")} for r in reports],
        "open_questions": [{"question_id": q["question_id"], "text": q["text"]} for q in open_questions],
        "unresolved": gaps,
        "next_action": snap["next_action"],
        "warnings": snap["warnings"],
        "text": "\n".join(lines),
    }


# --- Ready-made texts -------------------------------------------------------
# Deterministic renderings of tool results. A client may show them as they are; values are
# copied from the snapshot or evidence, never recomputed, so no number can drift on the way.

def _dash(value) -> str:
    return "–" if value is None or value == "" else str(value)


def render_snapshot(case_id: str, snap: dict) -> str:
    scope, summary = snap["scope"], snap["summary"]
    span = summary.get("time_span") or [None, None]
    lines = [
        f"**Case** `{case_id}` · station **{scope['station_number']}** ({_dash(scope.get('station_desc'))}) · "
        f"data {_dash(span[0])} to {_dash(span[1])} · retrieved {scope['retrieved_at']} UTC",
        f"{summary['measurement_rows']} rows, {summary['serials']} serials; "
        + ", ".join(f"{k} {v}" for k, v in summary["range_status_counts"].items()),
        "",
        "| Measurement | Serial | Value | Limits | Status | Deviation | Fail code | Evidence | Calculation |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for f in snap["findings"]:
        unit = f" {f['unit']}" if f["unit"] else ""
        lines.append(
            f"| {f['measurement']} | {f['serial_number']} | {f['raw_value']}{unit} | "
            f"{_dash(f['raw_lower'])}..{_dash(f['raw_upper'])} | {f['range_status']} | {_dash(f['deviation'])} | "
            f"{f['raw_fail_code'] if f['raw_fail_code'] is not None else 'none'} | `{f['evidence_id']}` | "
            f"{'`' + f['calculation_evidence_id'] + '`' if f['calculation_evidence_id'] else '–'} |")
    stamps = {(f["serial_number"], f["book_stamp"]) for f in snap["findings"]}
    if len(snap["findings"]) > 1 and len(stamps) == 1:
        serial, stamp = next(iter(stamps))
        lines.append(f"\nAll findings above: serial {serial} at {stamp}.")
    for f in snap["findings"]:
        if f.get("listed_because"):
            lines.append(f"{f['measurement']} is listed because: {f['listed_because']}.")
    if snap["more_findings"]:
        lines.append(f"{snap['more_findings']} more finding(s) are available as evidence in the case.")
    lines.append("\n**Warnings**")
    lines.extend(f"- {w}" for w in snap["warnings"])
    a = snap["assessment"]
    lines.append(f"\n**Assessment (hypothesis): {a['label']}.** {a['basis']}")
    lines.append(_render_next(snap["next_action"]))
    return "\n".join(lines)


def _render_next(action: dict) -> str:
    if action["kind"] == "QUESTION":
        return f"\n**Question `{action['question_id']}`:** {action['text']}"
    return f"\n**Next step ({action['kind']}):** {action['text']}"


def render_evidence(item: dict) -> str:
    eid, cls = item["evidence_id"], item["evidence_class"]
    head = f"**Evidence `{eid}` ({cls})**"
    if cls == "OBSERVED":
        f = item["fields"]
        unit = f" {f['unit']}" if f.get("unit") else ""
        code = f"{f['measure_fail_code']} (meaning unknown)" if f.get("measure_fail_code") is not None else "none"
        return "\n".join([
            head,
            f"- Source: `{item['source_table']}`, row `{item['row_locator']}` "
            f"(Oracle ROWID at retrieval time; not a verified business key); retrieved {item['retrieved_at']} UTC",
            f"- {f['measure_name']} (step {f['measure_step_number']}), serial {f['serial_number']}, "
            f"station {f['station_number']}, recorded {f['book_stamp']} (timezone unknown)",
            f"- Raw value `{f['measure_value']}`{unit}; limits `{_dash(f['lower_limit'])}`..`{_dash(f['upper_limit'])}`; "
            f"nominal `{_dash(f['nominal'])}`; tolerance `{_dash(f['tolerance'])}`; fail code {code}",
            f"- Other recorded limits, not interpreted: intervention `{_dash(f['lower_intervention_limit'])}`.."
            f"`{_dash(f['upper_intervention_limit'])}`, scrap `{_dash(f['lower_scrap_limit'])}`..`{_dash(f['upper_scrap_limit'])}`",
        ])
    if cls == "CALCULATED" and "deviation" in item:
        unit = f" {item['unit']}" if item.get("unit") else ""
        return "\n".join([
            head,
            f"- Rule: {item['rule']}",
            f"- Inputs: " + ", ".join(f"`{i}`" for i in item["inputs"]),
            f"- Value {item['value']}{unit}, limits {_dash(item['lower_limit'])}..{_dash(item['upper_limit'])} "
            f"→ {item['range_status']}, deviation **{item['deviation']}**{unit}",
        ])
    if cls == "CALCULATED":
        groups = "; ".join(f"serial {g['serial_number']} at {g['book_stamp']}: {', '.join(g['abnormal_measurements'])}"
                           for g in item.get("groups", []))
        return "\n".join([
            head,
            f"- Rule: {item['rule']}",
            f"- Groups: {groups or 'none'}",
            f"- Serials in scope {item.get('serials_in_scope')}, with abnormal rows {item.get('serials_with_abnormal_rows')}, "
            f"without {item.get('serials_without_abnormal_rows')}",
            f"- Note: {item.get('note', '')}",
        ])
    if cls == "TECHNICIAN_REPORTED":
        return "\n".join([
            head,
            f"- Question `{item['question_id']}`: {item['question_text']}",
            f"- Answer: \"{item['answer_text']}\" ({item['answer_kind']}), recorded {item['recorded_at']} UTC",
            f"- {item['note']} Attribution: {item['attribution']}.",
        ])
    return head
