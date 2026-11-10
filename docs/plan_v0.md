
# MAGNA TRACE — Implementation Plan v0

**Project:** MAGNA Hackathon 2026 — Task 9  
**Team:** 4 developers  
**Status:** PROPOSED — pending team approval  
**Date:** 2026-11-10

## 1. Project Goal

Build an evidence-driven AI diagnostic assistant for maintenance and testing technicians using MAGNA's Oracle manufacturing data.

The assistant must:

- Retrieve real station and measurement records.
- Detect numerical deviations from recorded limits.
- Distinguish observations from possible causes.
- Consider equipment-related and product-related hypotheses.
- Ask relevant clarification questions.
- Suggest evidence-backed verification steps.
- Show traceable sources for its findings.

**Primary interface:** Microsoft Copilot (team-selected; integration feasibility not yet confirmed).

## 2. Proposed Architecture

```text
Technician
    |
    v
Microsoft Copilot Agent
    |
    v
FastAPI Backend
    |
    +-- Oracle Data Access
    |
    +-- Measurement Analysis
    |
    +-- Evidence Management
    |
    +-- Diagnostic Case State
    |
    v
Oracle Database (HACKATON)
```

The application must use read-only, parameterized Oracle queries. No autonomous machine control or database modifications.

## 3. Team Responsibilities

| Role | Responsibilities |
|---|---|
| Developer 1 — Data | Oracle connection, SQL queries, measurement parsing, anomaly detection |
| Developer 2 — Backend | FastAPI, endpoint contracts, case management, evidence references |
| Developer 3 — Copilot | Agent configuration, tool integration, dialogue instructions, HTTPS connectivity |
| Developer 4 — QA & Delivery | Tests, documentation, integration verification, demo preparation |

**Assignments are provisional.** Each developer works on a separate Git branch and integrates changes through Pull Requests.

## 4. Development Milestones

### G0 — Integration Feasibility

**Priority: CRITICAL**

- [ ] Confirm available Microsoft Copilot environment and account.
- [ ] Create a minimal FastAPI endpoint.
- [ ] Choose an approved HTTPS connection method.
- [ ] Connect a real Copilot tool to the API.
- [ ] Verify a live response using a request ID.
- [ ] Confirm permission to transmit manufacturing data.

**Done when:** Copilot successfully invokes the running backend.

If blocked, document the issue and discuss an alternative demonstration with MAGNA mentors.

### G1 — Oracle and Data Analysis

**Priority: CRITICAL**

- [x] Install Docker and restore Oracle.
- [x] Confirm schema `HACKATON`.
- [x] Verify four tables and their row counts.
- [ ] Implement a read-only Oracle connection in Python.
- [ ] Implement station and serial-number queries.
- [ ] Implement numeric parsing and limit comparison.
- [ ] Preserve raw values, timestamps and source references.
- [ ] Validate selected relationships between tables.

**Done when:** Backend returns correct, traceable Oracle measurements without modifying the database.

### G2 — Diagnostic Assistant

**Priority: HIGH**

- [ ] Implement the diagnostic API.
- [ ] Generate a Diagnostic Snapshot.
- [ ] Separate observed facts, calculations and hypotheses.
- [ ] Implement `UNDETERMINED` classification for insufficient evidence.
- [ ] Implement one relevant clarification question.
- [ ] Store the active case and technician's answer.
- [ ] Return a supported next verification step.
- [ ] Generate a short investigation summary.

**Done when:** A technician can complete one interactive, evidence-backed investigation.

### G3 — Testing and Demonstration

**Priority: HIGH**

- [ ] Verify at least three displayed measurements against Oracle.
- [ ] Test missing and invalid measurement values.
- [ ] Test unknown failure-code semantics.
- [ ] Test no-data and database-unavailable scenarios.
- [ ] Verify that every evidence ID resolves.
- [ ] Test complete Copilot → API → Oracle flow.
- [ ] Perform two successful end-to-end rehearsals.
- [ ] Prepare a concise presentation and backup demonstration.

**Done when:** The full demonstration is reproducible without manually injecting database results.

## 5. Proposed API Contract

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Check backend availability |
| POST | `/api/diagnose` | Start an investigation |
| POST | `/api/cases/{case_id}/reply` | Submit clarification answer |
| GET | `/api/cases/{case_id}/evidence/{evidence_id}` | Retrieve supporting evidence |

Final endpoint schemas and authentication must be agreed upon by the team and documented in `docs/architecture.md`.

## 6. MVP Acceptance Criteria

The MVP is complete when:

1. A real Copilot agent invokes the live backend.
2. The backend retrieves actual MAGNA Oracle records.
3. Numeric deviations are computed deterministically.
4. Findings include verifiable evidence references.
5. The assistant distinguishes facts from hypotheses.
6. One clarification answer updates the investigation.
7. The assistant provides a supported next action or clearly states that evidence is insufficient.

## 7. Known Risks

| Risk | Mitigation |
|---|---|
| Copilot integration unavailable | Validate G0 immediately; consult mentors |
| Unknown meaning of failure code `1001` | Keep code separate from numeric range status |
| Unverified relationships between records | Validate joins before grouping incidents |
| Missing maintenance procedures | Recommend data verification or escalation, not invented repairs |
| Limited development time | Prioritize G0–G3; postpone optional features |
| Confidential manufacturing data | Restrict access, minimize payloads and protect credentials |

## 8. Optional Features (After MVP)

- Failure Fingerprint across validated related records.
- Persistent case history.
- Cross-station and cross-product comparison.
- Approved maintenance-document retrieval.
- Optional React dashboard.
- Exportable investigation reports.

These features must not delay the working MVP.

## 9. Repository Workflow

Each developer uses a dedicated feature branch.

```bash
git fetch origin
git switch -c feature/task-name origin/main
```

Before merging:

- Test the changes.
- Update relevant documentation.
- Commit with a meaningful message.
- Push the branch.
- Open a Pull Request for review.

Keep database archives, passwords, API keys and confidential data outside Git.

## 10. Immediate Next Actions

1. **Copilot developer:** Prove the first real API tool call.
2. **Data developer:** Implement Oracle queries and measurement analysis.
3. **Backend developer:** Define and implement the diagnostic API contract.
4. **QA developer:** Prepare verified Oracle examples and acceptance tests.

**Project priority:** One reliable, evidence-backed diagnostic investigation is more valuable than multiple unfinished features.

---

**Approval status:** Draft v0. Team responsibilities, API contracts and Microsoft integration method require confirmation.
