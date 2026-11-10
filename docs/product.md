# MAGNA Diagnostic Copilot — Product Vision v1.0

> **Working name:** MAGNA TRACE — *Evidence-Driven Diagnostic Copilot*
> **Hackathon:** MAGNA Hackathon, Task 9 — *AI asistent pre technikov údržby a testovania*
> **Status:** FINAL / APPROVED — team development baseline. Implementation and gate results require separate evidence.
> **Date:** 2026-11-10
> **Primary surface:** Microsoft Copilot Studio, verified through real tool calls at delivery.
> **Delivery constraint:** 24-hour hackathon; four-person team; prize-competitive, but demo reliability comes before feature count

---

## 1. Executive vision

**MAGNA TRACE helps a production or test technician move from an unexplained abnormal result to a traceable, structured investigation — using real manufacturing data, targeted follow-up questions, and evidence-linked verification suggestions.**

A technician should be able to say: **“Station ST3003 has abnormal results. What do we know, what might be wrong, and what should I verify next?”**

Instead of returning a generic AI answer, TRACE should:

1. Retrieve recorded station measurements. Add product or work-order context only through verified relationships.
2. Calculate deviations deterministically, without asking an LLM to do numerical validation.
3. Explain what is *observed*, what is merely *suspected*, and what remains *unknown*.
4. Present equipment and product explanations as unverified hypotheses. Keep the P0 assessment `UNDETERMINED`.
5. Ask one high-value follow-up question or recommend an appropriate **non-invasive verification** step.
6. Attach an auditable source to every substantive finding or recommended step; explicitly label recommendations that lack an authoritative procedure.
7. Preserve the investigation context and produce a concise case summary for the next technician or engineer.

**One-line pitch:** *From factory alarms to evidence-backed next steps — inside Microsoft Copilot.*

**Product principle:** TRACE supports a technician's judgment; it does not control machinery, certify product quality, or autonomously authorize maintenance actions.

## 2. Problem and why it matters

During production downtime or failed tests, technicians often consult multiple systems, documents, test results, and colleagues. Diagnosis can depend on individual experience. The task brief specifically calls for an assistant that **asks clarifying questions, separates product issues from equipment issues, proposes verification steps, and cites a source for each step**.

A list of out-of-range measurements is not a diagnosis. A fluent LLM explanation without traceable evidence is not a safe or credible industrial assistant. TRACE must connect the two: trustworthy data analysis plus an interactive troubleshooting dialogue.

### Intended users

| User | Immediate need | TRACE's contribution |
| --- | --- | --- |
| Maintenance technician | Understand a station problem and choose the next check | Guided, evidence-linked investigation |
| Quality / test technician | Understand failed measurements and distinguish product vs station patterns | Numeric deviations and cross-record comparison |
| Process / quality engineer | Review what was observed and how the conclusion was reached | Structured case history and reproducible evidence |
| Shift lead | Receive a usable handover rather than an unstructured chat | Short, transparent diagnostic summary |

### Not the problem we are solving

Task 9 is **industrial equipment and product-test diagnosis**, not automatic debugging of software repositories. PLC code, machine configuration, or test scripts could become future *read-only evidence sources* if provided, but reading a developer's local project folder is **not** an MVP requirement.

## 3. Product strategy and differentiation

**Strategy:** Build a **stateful, evidence-first diagnostic experience**, not a generic chatbot that generates SQL or a broad factory analytics platform.

Three differentiating capabilities form the product identity:

1. **Traceable findings.** Keep each P0 observation linked to its captured source. An optional P1 grouping requires independently verified event relationships.
2. **Evidence ladder.** Clearly separate `OBSERVED`, `CALCULATED`, `TECHNICIAN_REPORTED`, `HYPOTHESIS`, and `UNKNOWN`. Every finding links back to a specific source or computation. A hypothesis is never displayed as a confirmed root cause.
3. **Next-best question.** Instead of dumping five generic recommendations, request the one missing detail most useful for distinguishing equipment from product problems, and update the case after the technician answers.

The expected outcome is **faster, clearer, more reproducible diagnosis**, *not* a claimed improvement in downtime or yield that we have not measured.

## 4. Previously reported data baseline and limitations

The adopted source reports a prior restoration of the Task 9 archives and reads of `HACKATON` in `FREEPDB1`. A1 must independently establish current access and counts.

| Table | Known role | Row count status |
| --- | --- | --- |
| `MACHINE_LINES` | Stations and production lines | ~29 in Oracle table statistics; not yet independently counted |
| `SNO_BOOKINGS_WP` | Production bookings, serial numbers, work-order links | ~150 in table statistics |
| `SNO_MEASUREMENT_DATA` | Recorded measurements, bounds, units, result codes, timestamps | 1,524 in the previously reported `COUNT(*)`; rerun at A1 |
| `WORKORDERS` | Manufacturing orders and product context | ~58 in table statistics |

Historical measurements profile reported on 2026-11-10. A1/A4 and D5 must reproduce the relevant results locally before demo use.

- **23** distinct station numbers; **27** distinct serial numbers; **164** distinct measurement names.
- Records span **2026-11-09 10:39 to 14:36**, as reported by Oracle `BOOK_STAMP` formatting.
- `MEASURE_FAIL_CODE` is `1001` on **30** rows and `NULL` on **1,494** rows.
- The 30 coded rows occur at **six stations**, with **five rows per station** in the sampled result.
- ST3003 is a historical lead for the Angle, Motor Speed and Vibration checks. Capture their actual values, limits, units and scopes locally at A4.

**Critical data caveats:**

- Preserve raw `MEASURE_FAIL_CODE` separately from range status and data-quality flags. Use `SEMANTICS_UNKNOWN` for undocumented codes, including raw null. Both `1001` and null have unconfirmed result semantics.
- The source reports an in-range Screw Count with code `1001`. A4 checks the original row and D independently verifies the arithmetic.
- Values and limits were reported as text. Retain the raw inputs. Classify null, empty or whitespace-only numeric input as `MISSING` and other invalid text as `UNPARSEABLE`. Return `NOT_EVALUABLE` when evaluation is impossible. With one valid bound and the other missing, evaluate only the recorded side and flag `PARTIAL_BOUNDS`.
- The dataset is short and small. It does **not** support reliable predictive maintenance claims or statistically justified root-cause probabilities.
- Separate maintenance logs, verified repair outcomes, equipment manuals, and approved troubleshooting procedures have **not yet been confirmed** in the provided data.
- There is currently no evidence that an identified anomaly establishes a particular physical failure mechanism.

**Resulting product decision:** Oracle is the source of **manufacturing evidence**, not an automatically sufficient source of maintenance procedures or ground-truth fault labels. Missing knowledge must remain visible as missing.

## 5. Core product experience

### Primary interface

**Microsoft Copilot Studio is the primary user interface.** D develops an optional read-only React dashboard in parallel against the same API. The real Copilot journey remains mandatory.

### Primary demo flow — happy path

1. The technician opens the **MAGNA TRACE agent in Microsoft Copilot**.
2. The technician asks: **“Investigate station ST3003. Why are its test results abnormal?”**
3. Copilot calls the team's protected diagnostic API and receives sourced station data and deterministic anomaly analysis.
4. TRACE presents separate findings with the observed value, recorded bound, source timestamp and captured evidence reference for each.
5. TRACE explains **what is known** and offers an **equipment / product / unknown** hypothesis, clearly marked as tentative.
6. TRACE asks one question the available records cannot answer, for example whether the technician observed anything unusual during the test.
7. Before replying, Copilot calls `record_answer` using the active `case_id` and offered `question_id`. The backend captures the answer and returns an updated next check; the P0 assessment remains `UNDETERMINED`.
8. The technician asks for a summary. TRACE returns a short handover: observations, data sources, answered questions, unresolved hypotheses, next checks, and limitations.

### Example response contract (illustrative, not a claim of an implemented feature)

> **Observed:** Report each independently verified breach using its tool-returned measurement, value and upper or lower bound.
> **Evidence:** Cite the backend-issued case-local evidence ID for each observation and calculation. It resolves to the captured fields and retrieval time.
> **Interpretation:** Multiple deviations coincide; this does not establish a common physical cause.
> **Classification:** `UNDETERMINED` — equipment vs product cannot yet be established.
> **Next question:** What did you observe during the test that the measurement record cannot show?
> **Suggested verification:** Use the data check or escalation returned for the active case.

The UI must not fabricate citations, maintenance manuals, or numeric confidence percentages.

### Secondary journey — insufficient evidence

If a technician asks **“Which component must I replace?”** without a verified procedure and adequate evidence, TRACE responds that the specific root cause is **not established**, shows the evidence gap, asks a narrowing question, and suggests escalation/consultation of the approved maintenance procedure. This refusal-to-overclaim is a feature, not a failure.

### Secondary journey — product vs equipment

In conditional P1, `same_station_across_serials` holds station fixed and counts distinct comparable serials; `same_serial_across_stations` holds serial fixed and counts distinct comparable stations. Each needs at least two entities on its comparison dimension. Two receive `LOW_SAMPLE`; three or more clear that warning. Record count and time coverage remain visible. Verify keys, names, units, numerically equal bounds, test semantics and product context before comparing parseable values. A failed criterion yields `NOT_COMPARABLE` with its reason. A pattern cannot prove a physical cause.

## 6. Functional scope and priorities

### P0 — Must work for a credible MVP

| ID | Capability | Observable acceptance criterion |
| --- | --- | --- |
| P0-01 | **Real Microsoft Copilot integration** | A real Copilot agent invokes at least one live backend tool and uses its returned data in a response; recorded in a reproducible test/demo. |
| P0-02 | **Read-only Oracle access** | Backend retrieves correct station and measurement records from the restored `HACKATON` schema with restricted, parameterized queries. |
| P0-03 | **Deterministic anomaly detection** | Backend compares valid numeric values with limits; handles equality, invalid/missing data, and coded failures without assuming undocumented semantics. |
| P0-04 | **Evidence-linked findings** | Each displayed fact cites a backend-issued case-local ID for immutable captured evidence or a calculation with identified inputs. |
| P0-05 | **Equipment vs product reasoning** | The backend returns `UNDETERMINED` throughout P0 and identifies evidence that could distinguish competing hypotheses. |
| P0-06 | **Interactive clarification** | Agent asks a relevant follow-up question and incorporates the technician's answer into the ongoing case. |
| P0-07 | **Verification guidance** | Agent offers a safe data-based next check, with supporting evidence and limitations; never claims an unverified step is an approved repair SOP. |
| P0-08 | **End-to-end reliability and handover** | Run the live station journey twice through evidence, clarification, recorded answer, updated next check and a concise evidence-backed handover from the active case. |

### P1 — Valuable only after P0 is stable

| ID | Capability | Reason to add |
| --- | --- | --- |
| P1-01 | Persisted diagnostic cases | Reliable continuity, auditability, and handover |
| P1-02 | Richer handover and structured exports | Extended reporting and PDF/HTML output beyond the basic P0 handover |
| P1-03 | Cross-serial / cross-station comparison | Better evidence for equipment/product distinction, where dataset relationships permit |
| P1-04 | Failure fingerprint / simple incident grouping | Clearer explanation of grouped measurement abnormalities |
| P1-05 | Second independently tested scenario | Demonstrates robustness beyond one hardcoded example |
| P1-06 | Conditional knowledge retrieval | Only when approved manuals and permission to use them are available; cite document, revision and section |

### P2 — Stretch goals, not MVP promises

- Optional dashboard enhancements after the core journey is stable. D can develop the contract-based read-only dashboard in parallel.
- Explicit technician feedback: `verified / rejected / unresolved` for a suggested hypothesis (human-entered, never silently learned as truth).
- Similar-case retrieval once genuine resolved historical cases exist.
- Slovak/English localization and optional Microsoft Teams channel delivery, if access permits.

### Explicit non-goals

- Autonomous machine control, PLC write operations, parameter changes, repair execution, or safety-critical action authorization.
- Training or fine-tuning a custom foundation model.
- Generating root-cause probabilities unsupported by labeled failure history.
- Predictive maintenance claims from a few hours of records.
- A general-purpose coding agent or unrestricted filesystem/SQL agent.
- Replacing MAGNA's official maintenance procedures, technical supervision, or safety rules.
- A production-grade enterprise deployment within 24 hours.

## 7. Evidence and trust contract

Every response must visibly distinguish these classes:

- **Observed:** original field and value from the dataset, with source locator.
- **Calculated:** deterministic computation with inputs, rule, and source IDs.
- **Technician-reported:** user-provided information, explicitly attributed.
- **Hypothesis:** possible explanation, labeled unverified, with supporting and contradictory evidence where available.
- **Unknown / unavailable:** unanswered questions, undocumented codes, missing manuals, uncertain linkage.

**Evidence link design.** B issues a case-local ID for each immutable captured observation and calculation. Capture the table, queried scope, raw fields, source time, retrieval time and row ordinal or fingerprint. A fingerprint is a snapshot locator. A durable database key and cross-table joins require independent validation.

**Safety constraints:** All production reads are read-only. No credentials or Oracle dumps in Git or LLM prompts. Only minimized, task-relevant data should be shared with an authorized model; organizer permission to use external LLMs during development is not proof that all manufacturing data may be uploaded to any third-party service. The assistant must identify missing approved procedures, refrain from hazardous maintenance instructions, and refer physical interventions to qualified personnel under plant rules.

## 8. High-level technical direction (not the architecture specification)

**Target interaction:**

`Technician → Microsoft Copilot agent → approved tool/connector → team-owned HTTPS Diagnostic API → Oracle read-only adapter + deterministic analysis → structured findings → Copilot response`

- **Copilot Studio** owns dialogue, one clarification and bounded tool invocation. It quotes facts returned by the backend.
- **Python/FastAPI** owns facts, Decimal arithmetic, evidence IDs, diagnostic rules and case state. Queries are fixed parameterized SELECTs.
- **Oracle layer:** read-only queries over the four supplied tables; explicit relationship validation.
- **Session layer:** one worker, in-memory cases in P0. B returns `CASE_NOT_FOUND_OR_EXPIRED` for nonexistent, expired and pre-restart IDs. Persistent history is P1.
- **Knowledge layer:** optional retrieval of approved documents *only if available*.
- **Local development:** direct API calls and mocked LLM interaction are permitted for tests; **final proof requires Microsoft Copilot invoking the live API**.

**Integration dependency.** C must test the actual tenant, import, authentication and permitted HTTPS path at G0. The Oracle listener stays on loopback. The dashboard keeps the connector secret in its server-side proxy.

**Technical implementation details belong in** `docs/architecture.md`, not in this product vision. API endpoints, authentication mechanism, deployment route, and case schema are intentionally not frozen here.

### Development stack

| Component | Team choice | Verification or constraint |
| --- | --- | --- |
| Frontend | Microsoft Copilot Studio; parallel React + TypeScript + Vite dashboard | Real Copilot delivery is mandatory. D uses B2 examples until the API is available. |
| Backend | **Python 3 / FastAPI** | Team-owned read-only diagnostic tools and evidence contracts |
| Database | Existing Oracle Free environment, `HACKATON` schema | Confirm local SELECT-only access at A1. P0 cases live in backend memory. |
| Authentication | Secured API authentication compatible with chosen Copilot tool mechanism | **Unresolved** until tenant, connectors, and permitted deployment are tested |
| AI/LLM integration | Copilot Studio owns dialogue and tool selection | Any additional LLM layer, vector database or LangChain dependency requires a justified approved change. |
| Deployment | Oracle in Docker + backend on an approved, reachable **HTTPS** endpoint | Do not assume Copilot cloud can reach a laptop's `localhost` or that public tunnels are permitted |

**Copilot integration.** C prepares a hand-checked Swagger/OpenAPI 2.0 tool specification and tests import and authenticated invocation in the actual tenant. An alternative connector requires a documented decision and equivalent live verification.

## 9. Quality bar and measurable success

The project is **demo-ready** only when all of the following are demonstrably true:

1. Copilot calls a real live tool connected to the team's backend (not a pasted result).
2. The backend reads the actual supplied Oracle database and returns the expected results for the demo station.
3. At least three deliberately chosen data values and bounds in a Copilot response can be independently checked against SQL results.
4. The system shows an out-of-range result correctly and does **not** mislabel an in-range `1001` row as automatically out-of-range.
5. A missing or ambiguous code meaning leads to explicit uncertainty, not invented semantics.
6. Copilot records a technician answer against the active case and question before replying from the updated result.
7. The P0 assessment stays `UNDETERMINED` throughout the investigation.
8. A non-invasive next step and a supporting source are shown; no unauthorized repair instruction is given.
9. Run the full scenario twice in real Copilot, including resolution of evidence IDs and a basic handover. Document setup, test references and any permitted backup capture.
10. A reviewer can locate the implementation, tests, architecture decisions, and limitations in the private repository.

### Tests that matter more than a large passing-test count

- Correct numeric parsing and boundaries (`value == bound`, negative values, blanks, comma/period formats where relevant).
- Correct handling of `MEASURE_FAIL_CODE = 1001` without pretending its meaning is known.
- Cross-station and cross-serial queries cannot silently conflate distinct products or events.
- Unauthorized SQL write attempts and unapproved tool calls are impossible by design.
- Citation IDs refer to actual returned evidence, not generated labels without backing data.
- Agent responds safely when Oracle is unavailable, when no records match, or when the tool times out.
- No credentials or confidential raw data appear in logs, repository, or demo artifacts.

**Success metrics for the hackathon:** A completed P0 scenario, demonstrable source traceability, actual Copilot tool integration, no known critical safety/data-integrity defects, and a clear 3-minute presentation. Measured downtime savings and model diagnostic accuracy are **not** claimed without a valid study.

## 10. Three-minute presentation concept

| Time | Story beat | What judges see |
| --- | --- | --- |
| 0:00–0:25 | **Problem** — a technician faces abnormal factory tests and fragmented evidence | One concrete manufacturing problem and the cost of searching manually (qualitative, no invented savings) |
| 0:25–0:50 | **Product** — MAGNA TRACE in Microsoft Copilot | The actual Copilot agent and its task |
| 0:50–1:45 | **Live investigation** — ST3003 | Real Oracle retrieval, three numerical deviations, exact source references |
| 1:45–2:20 | **Interactive reasoning** — equipment or product? | Follow-up question, captured answer, competing hypotheses and `UNDETERMINED` |
| 2:20–2:45 | **Operational value** — next verification and handover | Evidence-backed next check and concise active-case summary |
| 2:45–3:00 | **Why this matters** | Show how a judge can inspect a captured finding and its limitations. |

**Hero moment:** A judge can ask **“Where did that number come from?”** and the team can show the specific Oracle-backed evidence immediately. A second hero moment is the system saying **“Not enough evidence to determine root cause”** instead of hallucinating certainty.

If time is short, prioritize a real live Copilot call and accurate citations over transitions, animations, or a separate dashboard.

## 11. Delivery and repository expectations

Keep the organizers' general layout, adapted to this task:

```text
codexsfunclub/
├── README.md                 # Product summary, prerequisites, startup and live demo
├── AGENTS.md                 # Coding-agent and contribution rules
├── docs/
│   ├── product.md           # Adopted product requirements
│   ├── architecture.md      # Actual components, security, data flow, Copilot integration
│   ├── plan.md              # Milestones, ownership, interfaces, acceptance tests
│   └── decisions.md         # Dated baseline decisions and unresolved questions
├── backend/                 # FastAPI, Oracle adapter, analytics and evidence tools
├── copilot/                 # Agent setup, instructions, tool schemas, reproducible config
├── tests/                   # Unit, API, integration, safety and demo smoke tests
├── frontend/                # D's optional parallel read-only dashboard
└── .github/                 # Optional workflows if useful
```

- The repository remains **private**, with organizer collaborators as requested.
- Follow `docs/plan.md` §7 for feature branches, full or incremental bundles, D’s verification and B’s integration. Keep the module and interface ownership in plan §1.
- Never commit Oracle archive/image files, Docker volumes, credentials, tokens, private manufacturing exports, or generated secret-bearing configs.
- Keep `README.md` current with what **actually works**; distinguish runnable functionality from roadmap items.
- Provide a reproducible Copilot integration guide, not only backend source code.
- Create optional directories only when they contain actual deliverables; Git does not track empty directories.

## 12. Risks, dependencies and decision gates

| Risk / unknown | Impact | Mitigation or gate |
| --- | --- | --- |
| **Copilot access, licensing, tenant permissions** | Core requirement blocked | **Gate 0:** Prove a toy Copilot → HTTPS API call early, with the actual account/tenant. |
| **Cloud connectivity to locally hosted Oracle-backed API** | Tool cannot access backend | Choose a permitted secured endpoint/network route; do not assume `localhost` is reachable. |
| **Unknown meaning of code 1001** | False diagnosis | Ask MAGNA; interpret only verified numeric limit violations until clarified. |
| **No maintenance manuals or fault labels** | Weak repair-specific advice | Offer data-grounded verification and documented uncertainty; RAG only with real documents. |
| **Incomplete joins / unstable IDs** | Wrong incident attribution | Validate keys and station/serial/time relationships before cross-record conclusions. |
| **Model fabricates citations or actions** | Safety and trust failure | Backend-produced evidence IDs; validation; strict tool descriptions; negative tests. |
| **24-hour time limit** | Features remain unfinished | Pause side work when a P0 gate needs support; use the delivery plan's cut order. |
| **External AI data handling** | Confidentiality concern | Minimize payload; confirm approved data access and provider constraints. |

### Suggested delivery gates (scope control, not a fixed timetable)

- **G0 — Integration feasibility:** Two real authenticated Copilot calls, including one live Oracle count, correlated request IDs and rejection without the key.
- **G1 — Data correctness:** Oracle adapter returns traceable evidence; deterministic boundary tests pass.
- **G2 — Diagnostic interaction:** Demonstrate the full evidence, clarification, autonomous `record_answer`, next-check and handover journey in real Copilot.
- **G3 — Live demo readiness:** Full script works twice without manual intervention; backup presentation ready.
- **G4 — Stretch work:** Add only features that do not destabilize G0–G3.

## 13. Open decisions requiring explicit approval

1. **Which Copilot Studio environment, agent type and channel are permitted?** Confirm tenant capabilities and demo acceptance with organizers.
2. **Which tenant/account and licenses** will be used for the final demo and by the judges?
3. **What HTTPS exposure and authentication method** are permitted for the backend? What can be shown publicly?
4. **What does `MEASURE_FAIL_CODE = 1001` mean?** Does it apply per measurement, test cycle, serial number, or station event?
5. **Will more Task 9 material arrive?** Maintenance SOPs, manuals, error-code glossary, ticket history, verified root causes?
6. **Which columns form trustworthy cross-table relationships and event identities?** Confirm with targeted SQL and MAGNA mentors.
7. **What information may leave the local Oracle environment** when external LLMs or cloud Copilot are used?
8. **Which features are genuinely essential to judging?** Confirm expected presentation, reproducibility, technical innovation, and documentation requirements.


## Reference links (technical feasibility, not proof of MAGNA requirements)

- Microsoft Learn, **Add tools to custom agents**: https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-tools-custom-agent
- Microsoft Learn, **Extend your agent with tools from a REST API (preview)**: https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-rest-api
- Microsoft Learn, **Microsoft 365 Copilot extensibility FAQ**: https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/faq
