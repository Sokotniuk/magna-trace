# MAGNA TRACE — Product Specification v1.4 FINAL

> **Product:** MAGNA TRACE — *Evidence-Driven Diagnostic Copilot*  
> **Event:** MAGNA Hackathon · Task 9 — *AI asistent pre technikov údržby a testovania*  
> **Status:** FINAL scope; requirements, not completed features.  
> **Delivery:** Four developers · 24 hours · Live Microsoft Copilot mandatory (organizers verbally confirmed; platform/connector unverified).  
> **Pitch:** *From abnormal test results to evidence-backed next steps.*

## 1. Product Vision & Problem

Technicians investigating abnormal tests search across measurements, product context and observations. MAGNA TRACE combines Oracle data, deterministic analysis and Copilot dialogue to show **observations, unknowns and the next verification**.

TRACE supports judgment; it cannot certify quality, authorize repairs or prove causes. Downtime/yield improvements are not claimed.

## 2. Target Users & Value

| User | Immediate value |
| --- | --- |
| Maintenance technician | A focused diagnostic snapshot, one useful question and a justified next check. |
| Quality/test technician | Actual measurements, recorded limits, deviations and data warnings. |
| Process/quality engineer | Inspectable evidence, competing hypotheses and explicit gaps. |
| Shift lead/next technician | A concise handover that preserves the investigation state. |

**Outcome:** know what deviated, where evidence comes from, and what to check next.

## 3. Core Capabilities & Differentiation

1. **Diagnostic Snapshot:** station/time scope, deviations, data warnings, assessment and one next action.
2. **Evidence Ladder:** distinguish `OBSERVED`, `CALCULATED`, `TECHNICIAN_REPORTED`, `HYPOTHESIS`, `UNKNOWN`; resolve backend-issued case-local evidence IDs.
3. **Honest Measurements:** backend calculates deviations; show range, quality and raw `MEASURE_FAIL_CODE` separately.
4. **Next-Best Question:** check Oracle first, ask one useful unanswered question, record the reply and update the case.
5. **Verification & Handover:** suggest an evidence-backed data check or escalation and summarize the case.

No unrestricted SQL, invented references or causal claims. Group observations only after validating their linkage.

## 4. Real Data & Limitations

**Reported database:** Oracle `FREEPDB1`, schema `HACKATON`. **1,524 measurement rows confirmed by `COUNT(*)`** in project records; other counts are unverified `NUM_ROWS` statistics.

| Table | Role | Provenance |
| --- | --- | --- |
| `MACHINE_LINES` | Stations/production lines | ~29 from `NUM_ROWS`; verify. |
| `SNO_BOOKINGS_WP` | Bookings, serials and work-order context | ~150 from `NUM_ROWS`; verify. |
| `SNO_MEASUREMENT_DATA` | Measurements, limits, codes and timestamps | **1,524 via `COUNT(*)`**. |
| `WORKORDERS` | Manufacturing orders/product context | ~58 from `NUM_ROWS`; verify. |

Earlier profiling reported 23 stations, 27 serials, 164 measurement types and ~4 hours of data; recheck before demo. Values and limits are strings. An in-range `Screw Count` row reportedly has code `1001`: code ≠ range breach; `NULL` ≠ PASS. Code meaning, units, timezone, bounds policy, joins, incident identity and repair outcomes remain unverified. This dataset cannot establish causes, predictions or maintenance instructions.

## 5. Primary Demo Flow

1. **Open:** Technician asks a live Copilot agent about a validated station (e.g., `ST3003`); clarify scope.
2. **Retrieve:** Copilot calls the backend; Oracle returns ≥3 SQL-checkable values/limits with evidence IDs.
3. **Explain:** Show deviations, separate range/quality/code statuses and `UNDETERMINED` where causality is unclear.
4. **Clarify:** Ask one question Oracle cannot answer. If a technician reports a fixture change, store `TECHNICIAN_REPORTED` and revise the next check, **not** the `UNDETERMINED` assessment without independent evidence.
5. **Finish:** Give a supported non-invasive check or escalation, resolve evidence on request and summarize for handover.

Missing evidence or invalid comparisons are explicit gaps, never guessed answers.

## 6. MVP & Acceptance Criteria

| P0 end-to-end capability | Testable acceptance criterion |
| --- | --- |
| **1. Live Copilot integration** | Real agent calls protected backend; fresh request ID/value match agent output and logs. Mocks or localhost-only paths fail. |
| **2. Oracle + analysis** | Read-only parameterized queries return real records; backend handles invalid values, computes deviations and separates range, quality and code. |
| **3. Traceable snapshot** | ≥3 values and limits match SQL; each finding resolves to source fields or calculation. No fabricated incident links or diagnoses. |
| **4. Clarification + case state** | A relevant technician answer updates its active case and next question/check; source observations stay unchanged. |
| **5. Verification + handover** | Safe, evidence-backed data check or escalation; summary includes scope, observations, reports, gaps and next action. |

**Only an end-to-end journey passes P0.** Do not use unvalidated R1a/R2a thresholds or reports to output `EQUIPMENT_LIKELY`, `PRODUCT_LIKELY` or `MIXED`; default to `UNDETERMINED` unless independent evidence and validated criteria justify otherwise.

## 7. Technical Direction & Microsoft Copilot

**Target:** technician → live Microsoft Copilot agent → authorized tool → protected HTTPS Python/FastAPI API → read-only Oracle + deterministic analysis → sourced response. Maintain active-case state.

**Organizers verbally confirmed live Copilot as mandatory.** Platform, tenant, channel, connector, authentication and network route remain unverified. Test a real call early. Cloud Copilot cannot reach laptop `localhost` without an approved route; keep Oracle private. Standalone UI or mock is not a substitute.

## 8. Safety & Evidence Rules

- Distinguish evidence classes; every substantive finding has a **verifiable evidence reference**, not an invented or necessarily clickable link.
- Preserve raw values; use decimal-safe backend arithmetic. Keep range, data quality and `MEASURE_FAIL_CODE` independent; never infer PASS/FAIL from unknown `1001`/`NULL`.
- Correlations and reports generate hypotheses only; invalid units/joins or weak evidence require `UNDETERMINED` or `NOT_COMPARABLE`.
- Enforce read-only Oracle, isolated cases and minimal authorized cloud data; keep secrets/dumps out of Git and logs.
- No physical repairs, settings changes or replacements without approved procedures/qualified oversight; offer verification or escalation.

## 9. Stretch Goals & Non-Goals

**After P0:** validated cross-station/serial comparison, failure fingerprint, durable cases, technician check status, second scenario, richer exports/cards, approved-manual retrieval and dashboard.

**Excluded:** machine/PLC control, Oracle writes, fabricated procedures, arbitrary AI SQL, model training, prediction, root-cause probabilities and production deployment.

## 10. Success Criteria & Critical Risks

**Demo-ready:** the full live Copilot → Oracle → analysis → clarification → case update → evidence → handover flow runs twice. SQL-check ≥3 values; demonstrate an in-range `1001` row and an ambiguous case staying `UNDETERMINED`. Test no-data, Oracle-down and invalid evidence IDs; reveal no secrets.

| Critical risk | Required action |
| --- | --- |
| Copilot access/connector fails | Validate early and escalate to organizers; fallback UI does not satisfy the mandate. |
| Cloud cannot reach `localhost` | Arrange approved authenticated HTTPS access; do not expose Oracle. |
| Ambiguous records/codes | Verify SQL, units and joins; disable unsupported comparisons/classifications. |
| Missing procedures/fault labels | Only data checks and escalation; disclose uncertainty. |
| Demo instability | Freeze stretch work; rehearse one scenario, label backup recording if permitted. |

**Status:** data provenance ≠ implemented features; platform, semantics and classification remain validation risks.
