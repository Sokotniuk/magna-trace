# Decisions and verified facts

Append-only. Newest at the bottom. No secrets, keys, passwords or tunnel tokens.

## 2026-11-10

**C1 · Copilot Studio environment**
- Tenant: TUKE student account. Only environment: `tuke.sk (default)`; "All environments (0)".
- New agent builder UI (Build / Preview / Evaluate / Monitor). "Add a tool → + Add" offers only MCP and Workflow; no REST/OpenAPI import, no custom connector.
- MCP form supports auth None / API key (header or query) / OAuth 2.0.

**C1 · Integration route changed: REST import → MCP**
- Backend exposes an MCP endpoint `/mcp` over the same service functions as REST. Tool names, envelope, error codes and evidence IDs unchanged.
- Auth: API key in header `X-API-Key`.

**C4 · G0 BLOCKED by platform**
- Copilot Studio Preview: "environment is out of credits", error `EnforcementUsageCredits` (conversation 92de95c4-a9bf-48c8-9837-f19df3226945, 19:05 UTC).
- Students cannot create a developer environment in the TUKE tenant.
- G0 is not passed. Live Copilot remains the target.

**Interim strategy: OpenAI harness**
- Until Copilot has credits, `harness/chat_openai.py` drives the conversation with an OpenAI model through the same `/mcp` and the same `copilot/instructions.md`.
- Engineering harness only: not the product interface, not G0 evidence; labelled as such if shown.
- Real measurement data must not be sent to OpenAI before the organizers confirm it is allowed.

**Security incident (resolved)**
- An early test stub logged all request headers including the API key; the key appeared in screenshots and was used from a ChatGPT connection.
- Stub retired. New backend logs only request_id, method, path, status, duration. A new key was generated. Tunnel closed while not needed.

**Backend skeleton verified (step 2)**
- FastAPI + MCP SDK v1 (`mcp>=1.9,<2`; v2 renamed FastMCP and is not used).
- Oracle 23ai Free in Docker; runtime user `TRACE_RO` with SELECT on the four `HACKATON` tables only (`scripts/create_readonly_user.sql`).
- `SELECT COUNT(*) FROM HACKATON.SNO_MEASUREMENT_DATA` = **1524**, both in sqlplus as TRACE_RO and via `GET /api/v1/health/echo` (request_id 530c2b2526634cc6be47a3d8506aeef4, 19:46 UTC).
- Without the key: 401 `UNAUTHORIZED`. `/readyz` ok.

**Interim model provider**
- OpenAI key of a teammate's friend: no API credits (429). ChatGPT Plus does not provide API credits.
- Chosen: local FreeLLMAPI router (official free tiers, own provider keys) behind `OPENAI_BASE_URL`; setup in `docs/llm_router_setup.md`.
- Harness enforces: one fixed model (`auto`, `auto:*`, `fusion` refused); real-data guard — only `health_echo` results reach the model until `TRACE_ALLOW_REAL_DATA=1` is set after organizer approval.

**Interim model live (step 3)**
- FreeLLMAPI in Docker (`ghcr.io/tashfeenahmed/freellmapi:latest`), published on 127.0.0.1:3001 only (netstat checked). Setup code from server logs used for the local dashboard account.
- Provider: Groq only (1 key, healthy). Model pinned: `gpt-oss-120b`, expected route `groq/openai/gpt-oss-120b` (checked: tool call `get_time` returned, X-Routed-Via matched).
- Harness → `/mcp` → `health_echo` → Oracle: request_id 8b82bd710fbe43a593a518e587e937ec. Backend log match: confirmed (`POST /mcp -> 200 (132 ms)`, preceded by ListToolsRequest, then CallToolRequest). Step 3 closed.
- Real-data guard ON; model fallback forbidden.
- Groq data-use terms: not yet recorded.

**Schema and data profile (read-only as TRACE_RO)**
- Row counts confirmed by `COUNT(*)`: MACHINE_LINES 29, SNO_BOOKINGS_WP 150, SNO_MEASUREMENT_DATA 1524, WORKORDERS 58.
- SNO_MEASUREMENT_DATA also holds NOMINAL, TOLERANCE, MEASURE_TYPE (all `PROCESS`), intervention and scrap limits. Only LOWER/UPPER_LIMIT are evaluated; the others are kept in evidence, semantics unverified.
- WORKORDERS column is spelled `PART_NUMBRER` in the source.
- Number strings use Oracle style without leading zero (`.5`, `-.575`); no commas, spaces or exponents. Parser accepts `-?(\d+(\.\d+)?|\.\d+)`, rejects everything else. All 1524 values and limits parse.
- Units recorded on all rows; 23 stations; BOOK_STAMP 2026-11-09 10:39–14:36, 150 distinct stamps.
- 16 groups share (station, serial, step, name, stamp): no unique business key. Evidence stores a captured snapshot plus Oracle ROWID as a locator.

**open_case / get_evidence / list_stations (step 4)**
- Implemented in backend (services, diagnostics, measurements, evidence, cases) and exposed via MCP and REST. 32 unit tests pass (hand-computed expectations).
- Live run on all 23 stations: 29 ABOVE, 0 BELOW, 0 NOT_EVALUABLE, 1495 within recorded bounds. 30 rows carry code 1001 at 6 stations (ST1003, ST1004, ST2003, ST3003, ST4003, ST4004).
- Observation only, not a semantics claim: every ABOVE row carries 1001; one 1001 row is within bounds (ST3003 Screw Count 8 in 8..8).
- ST3003: all five coded rows belong to serial 1000000203 at 2026-11-09 10:55:13.108334. Breaches: Angle 197.592>190 (7.592), Vibration 2.354>2 (0.354), Position Accuracy 1.292>1 (0.292, not listed in the product drafts), Motor Speed 1350.457>1300 (50.457). Snapshot asks Q about tool/fixture/setup changes; assessment UNDETERMINED.
- Harness keeps open_case, get_evidence, list_stations blocked for the model until organizers approve data sharing.

**record_answer (step 6)**
- Answer stored as TECHNICIAN_REPORTED evidence (raw text, question, time, attribution "technician via agent; no individual identity"). Observations and findings unchanged; label stays UNDETERMINED (product v1.4 §5.4).
- Contract extension: optional `answer_kind` YES / NO / UNKNOWN (default UNKNOWN), set by the agent; raw `answer_text` stays authoritative. The backend picks the next step from fixed templates: YES → escalation to verify the reported change per approved setup procedure; NO → escalation to quality engineering (product hypothesis, cross-station check not available); UNKNOWN → check shift/maintenance log.
- A question can be answered once; wrong question_id or no open question → INVALID_SCOPE (no new error code added).
- 41 unit tests pass; live run on ST3003 for all three kinds verified.

**get_handover (step 7) — P0 backend complete**
- Built from case state only (no new Oracle query): scope, observations with evidence IDs, assessment, technician reports, open questions, unresolved gaps, next step; plain-text version included.
- 47 unit tests pass. Live journey on ST3003 verified in-process: open_case → get_evidence (197.592) → record_answer (YES) → get_handover.
- Not yet done: the same journey driven by a model (blocked by the real-data guard until organizers approve), and by Copilot (no credits).

**Organizer answers (2026-11-10, reported by student C)**
1. Copilot credits: none will be provided. **Scope change:** the demo uses the current setup — same backend and `/mcp`, conversation driven by the interim model (`gpt-oss-120b` via Groq through FreeLLMAPI). It is presented as a stand-in for Copilot, not as Copilot. G0 (live Copilot call) is not passed; P0-01 is replaced by this organizer-accepted alternative. Copilot Studio wiring stays documented for later.
2. Sending HACKATON measurement data to Groq during development and the demo: **allowed**. `TRACE_ALLOW_REAL_DATA=1` may be set.
3. Showing the interim model at the demo, clearly labelled: **accepted**.
4. Data semantics (code 1001, intervention/scrap limits, BOOK_STAMP timezone, bound equality): **no answer available.** Provisional policies stay and are stated in every snapshot: 1001 shown raw with `SEMANTICS_UNKNOWN`; only LOWER/UPPER_LIMIT evaluated, inclusive; intervention/scrap limits kept in evidence, not interpreted; timestamps passed through, timezone unknown.

**Model journey with real data (interim client, gpt-oss-120b via Groq)**
- Turn 1 open_case (request 03d772c8…): table with serial, fail code and evidence IDs in ASCII; no invented labels after instruction rule 11.
- Turn 2 get_evidence E-0FBA80-033 (request b457039e…): source explained.
- Turn 3 **record_answer called autonomously** (request 11f9be06…): case_id, question_id, raw answer text and answer_kind YES passed correctly; reply shows what changed, what is open, escalation; label UNDETERMINED.
- Fixes made on the way: IDs normalised for typographic dashes; instructions require fail code column and forbid invented labels; harness waits on 429 and sends only the last two tool results in full.
- Limitation: Groq free tier tokens-per-minute makes each turn take 20–90 s.
- Second run (case C-6002363AEC8B36C2): refusal on "Which part should I replace?" without invented repair; get_handover called autonomously and showed the open question. Full journey now seen with the model across two runs.
- Model still added "(reference)" to the in-range coded row despite rule 11. Fix: each finding now carries backend-issued `listed_because`; instructions require quoting it for rows that are not ABOVE/BELOW. Not yet re-checked with the model.

**Second model provider: Cerebras (2026-11-10)**
- Reason: Groq free tier for gpt-oss-120b is 8,000 tokens/min (router catalog), about one technician turn per minute. Faster Groq models are not served by Groq in this router.
- Organizers approved sending the same HACKATON data to Cerebras (reported by student C).
- Cerebras account on the free "Limited Credits" plan ($5 free credits, lower rate limits than paid).
- Harness accepts a comma-separated list in TRACE_EXPECTED_ROUTE; planned value: Groq and Cerebras routes of gpt-oss-120b. Exact Cerebras route to be confirmed from X-Routed-Via.

**Speed-up: second Groq model instead of Cerebras (2026-11-10)**
- Cerebras free credits require a payment card; not used. Its key was not added.
- Groq limits are per organization and per model, so another key in the same account adds nothing; extra accounts to evade limits are not used.
- Probed without MAGNA data: `gpt-oss-20b` → `groq/openai/gpt-oss-20b`, `qwen3.8-27b` → `groq/qwen/qwen3.8-27b`; both call tools.
- Harness: OPENAI_MODEL accepts an ordered list; on 429 the next model is tried at once, waits only when all are limited; every reply prints `[model] <route>`.
- Set: OPENAI_MODEL = `gpt-oss-120b,gpt-oss-20b`; TRACE_EXPECTED_ROUTE = both Groq routes. Behaviour of gpt-oss-20b on the full journey not yet checked.

**Two-model run and token budget (2026-11-10)**
- Run with gpt-oss-120b + gpt-oss-20b (case C-6AB32B8C89EFD226): listed_because quoted (no invented label); gpt-oss-20b opened the calculation evidence for 50.457 and called record_answer autonomously with correct arguments. Second call of each turn still waited 50–90 s.
- An earlier failed run was a network/DNS outage (EAI_AGAIN / ENOTFOUND api.groq.com), not a rate limit; the router then put routes on cooldown and answered 429.
- Router output reserve is 1,000 tokens when max_tokens is unset (not the main cost). Main cost: 3–5k input tokens per call, two calls per turn, against 8k TPM per model.
- Probe: `reasoning_effort: low` on gpt-oss-20b cut completion tokens 491 → 133. Harness now sends TRACE_REASONING_EFFORT (default `low`) and prints input/output tokens per call. Rule-following at `low` not yet checked on the full journey.

**Token diet and third model (2026-11-11)**
- Snapshot: `listed_because` only for rows that are not ABOVE/BELOW; pattern member IDs moved to the pattern's CALCULATED evidence (still resolvable); shorter warning and hypothesis wording. ST3003 envelope 4,347 → 3,924 chars.
- record_answer response no longer repeats findings (`findings_unchanged` with their evidence IDs); the case keeps the full snapshot for handover. 5,238 → 3,167 chars. Agent told not to redraw the table after an answer.
- Harness keeps only the latest tool result in full (was two).
- Third model: `qwen3.8-27b` (route `groq/qwen/qwen3.8-27b`, tool calling probed). reasoning_effort sent only to gpt-oss models.
- 49 unit tests pass. Speed and rule-following of the three-model setup not yet checked on the full journey.

**Three-model run (2026-11-11, case C-C710783B586CA190)**
- Turn 1 (120b) and turn 2 (20b tool call, qwen reply) answered without waiting; qwen showed the full source record and stated it did no arithmetic. Turns 3–4 waited about 50 s with messages sent back to back.
- record_answer called autonomously (120b); reply by 20b was too terse (no "what changed / still open"). Fix: record_answer now returns `case_update.message`, a ready-made text with report ID, what changed, unchanged, still open and next step; instructions require replying with it in full. 49 tests pass; not yet re-checked with the model.
- Remaining cost: 3.3–4.1k input tokens per call plus the router's 1,000-token output reserve against 8k TPM per model.

**Run with case_update.message and handover limit (2026-11-11, case C-B83198D74BC97869)**
- Turn 3 now gives the full update (report ID, what changed, unchanged, still open, next step); waited 20 s.
- Turn 5: get_handover called autonomously, but the follow-up call hit qwen's per-request limit (Groq 413, ITPM 7,000, requested 7,088) while the other two models were limited.
- Fix: the agent tool get_handover returns only the ready-made text plus cited evidence IDs (6,005 → 2,347 chars); REST keeps the structured handover. Harness also stubs agent replies older than the last two (tool calls with case_id kept).
- 50 unit tests pass. Not yet re-run with the model.

**Full journey passed with the interim model (2026-11-11, case C-0601FD594A87644B)**
- open_case → get_evidence → record_answer (autonomous, full case_update.message) → get_handover all succeeded; one 20 s wait. Refusal turn passed in earlier runs.
- Remaining model liberties: qwen called the deviation OBSERVED and said the breach "triggered" code 1001; gpt-oss-20b turned the handover text into a table with "+" signs and filled Screw Count deviation with 0.
- Instructions tightened: rule 8 forbids linking values to fail codes; rule 12 requires opening calculation_evidence_id for deviations and naming the evidence class exactly; rule 13 requires returning handover text as is. Not yet re-checked with the model.

**Rules 8, 12, 13 verified (2026-11-11, case C-335E2964D57F21EC)**
- Turn 2 (qwen): opened calculation evidence E-335E29-034, named class CALCULATED, gave rule and inputs, no causal link to code 1001.
- Turn 5 (qwen): handover returned as text, no table, no added signs or values.
- Turn 3 waited ~70 s with messages sent close together. Presentation limit is 3 minutes (organizers): the live demo must be planned around the per-minute limits (docs/demo_script.md).

**One model call per turn: ready-made backend texts (2026-11-11)**
- Every successful open_case, get_evidence and record_answer result now carries a deterministic `message` (handover already had `text`): table with evidence and calculation IDs, listed_because lines, warnings, assessment, question or next step; evidence texts per class (OBSERVED, CALCULATED, TECHNICIAN_REPORTED, pattern).
- The interim chat shows such a text as is and skips the second model call (`TRACE_RELAY_TOOL_TEXT`, default on). The model still understands the request and chooses tool and arguments, including the autonomous record_answer. Errors still go back to the model to explain. The stored tool result drops the duplicated text.
- Effect expected: about half the tokens per turn and no restated numbers. Instructions: when a ready text is present, reply with it as is (applies to Copilot too).
- 51 unit tests pass; relay helper checked. Not yet run with the model.

**Demo speed reached (2026-11-11, case C-72ED2A2E07E9FE43)**
- With the backend restarted on the ready-text code: open_case, get_evidence (E-72ED2A-034, CALCULATED), record_answer (autonomous) and get_handover each took one model call and were relayed; no rate-limit waits; open_case to recorded answer within about 10 s.
- The model also handled a typo ("here did 50.457 come from?") and still picked the calculation evidence.
- Lesson: after backend changes the server must be restarted; an earlier run used the old process and still made second model calls.

**Open**
- Oracle container publishes port 1521 on all interfaces (`0.0.0.0`); should be bound to `127.0.0.1` before working on shared Wi-Fi.
- Organizers not yet asked: demo channel acceptance, sending data to OpenAI, Copilot credits.
