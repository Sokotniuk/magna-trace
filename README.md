# MAGNA TRACE

*Evidence-driven diagnostic assistant* for MAGNA Hackathon **Task 9 — AI asistent pre technikov údržby a testovania**.

A technician asks about a test station in a web chat. TRACE reads the live Oracle measurements, shows what is outside its recorded limits and where every number comes from, asks one question the database cannot answer, records the reply, and produces a handover. It never names a cause, a repair or a probability: the assessment stays `UNDETERMINED`.

## One system

```text
Browser: React dashboard + chat panel (D)
   │  /api/v1/*  via Vite proxy — the API key stays on the server
   ▼
FastAPI  agent.main:create_app
   ├─ /api/v1/cases, /evidence, /answers, /handover, /stations   contract B2, cases, evidence (B)
   ├─ /api/v1/chat   agent: the model picks a tool, the backend renders the text (C)
   └─ /mcp           the same tools for MCP clients such as Copilot Studio (C)
   ▼
Oracle access and Decimal analysis (A) ──► Oracle FREEPDB1 / HACKATON, SELECT-only user
```

| Folder | Owner | Content |
| --- | --- | --- |
| `backend/app/` | A, B | `oracle_repo.py`, `measurements.py` (A); `schemas.py` — contract B2 (B) |
| `student_b/` | B | FastAPI app, cases, evidence, answers, handover |
| `agent/` | C | Web-chat agent, deterministic texts, MCP endpoint, application factory |
| `frontend/` | D | React dashboard with mock and live modes; chat panel in live mode |
| `contracts/b2/` | B | JSON Schema, examples and validator of the REST contract |
| `tests/` | A, D | A's module tests; D's QA checklist, expected values, demo backup plan and pitch |
| `docs/` | team | Product, architecture, plan, decisions (D30–D33 describe this integration) |
| `student_c/` | C | Earlier self-contained backend and console chat — demo fallback, see its README |

## What is verified, and what is not

| Check | Result (2026-11-11, integrator's machine) |
| --- | --- |
| Tests | A 192 · B 93 · agent 6 · legacy `student_c` 51 · B2 validator PASS |
| Live Oracle through the integrated app | 1524 measurement rows, 23 stations |
| Station ST3003 | Four values above their upper limit (Angle 7.592, Vibration 0.354, Position Accuracy 0.292, Motor Speed 50.457), all serial `1000000203` at one timestamp; Screw Count within limits with fail code 1001 |
| Chat journey, API and browser | Case → source of 50.457 (calculated evidence) → technician answer recorded by the agent on its own → refusal of repair advice → handover; one model call and under 2 s per turn |
| **Microsoft Copilot** | **Not verified.** The available Copilot Studio tenant has no credits. An open-weight model stands in and is labelled so in the UI; `/mcp` is ready for Copilot Studio |
| Not claimed | Root causes, meaning of fail code 1001, intervention/scrap limits, timezone of timestamps, repair procedures |

## Run it (Windows PowerShell, from the repository root)

Needs Python 3.12+, Node 22+, and the Oracle container with a SELECT-only user (`student_c/scripts/create_readonly_user.sql`).

**1. Install once**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r student_b\requirements-test.txt -r agent\requirements.txt
cd frontend; npm install; cd ..
```

**2. Server settings** — environment variables of the server process; never in Git, the browser or `VITE_*`.

| Variable | Meaning |
| --- | --- |
| `TRACE_API_KEY` | 32–256 ASCII characters; shared by backend and Vite proxy |
| `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_DSN` | SELECT-only account, e.g. DSN `localhost:1521/FREEPDB1` |
| `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI-compatible model endpoint; `OPENAI_MODEL` is a comma-separated list of fixed model IDs (setup: `student_c/docs/llm_router_setup.md`) |
| `TRACE_EXPECTED_ROUTE` | Comma-separated approved `provider/model` routes; answers from other routes are rejected |
| `TRACE_ALLOW_REAL_DATA` | `1` only after data sharing with the model provider is approved; otherwise tools are blocked in the chat |

**3. Backend** (one worker: cases live in memory)

```powershell
.venv\Scripts\python.exe -m uvicorn agent.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

**4. Dashboard with chat**, in a second terminal

```powershell
cd frontend
$env:TRACE_API_TARGET = "http://127.0.0.1:8000"; $env:VITE_TRACE_API_MODE = "live"
npm run dev
```

Open `http://127.0.0.1:5173`. In **Ask TRACE** try:

1. `Investigate station ST3003. What happened?`
2. `Where did 50.457 come from?`
3. `Yes, the fixture was re-clamped after the morning shift.`
4. `Which part should I replace?`
5. `Give me a handover for the next shift.`

The station selector below the chat is D's read-only dashboard on the same API. Without a model configured the chat answers 503 and the dashboard still works. The synthetic mock mode is described in `docs/README_dashboard_mock.md` and `frontend/README.md`.

**5. Tests**

```powershell
.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests student_b\tests agent\tests --ignore=tests\d5_live_smoke.py
.venv\Scripts\python.exe -B contracts\b2\validate.py
```

## How the agent stays honest

- The model only chooses a tool and its arguments. Every table, value, limit, deviation and evidence ID in the chat is rendered by the backend (`agent/render.py`) and shown unchanged.
- Each displayed fact has a case-local evidence ID that resolves to the captured source row or to the calculation with its rule and inputs.
- Range status, quality flags and the raw fail code are separate; `1001` and an empty code are never read as FAIL or PASS.
- A technician's answer is stored as an unverified report; it changes the next step, never the observations or the label.
- All routes except `/healthz` and `/readyz` require `X-API-Key`; logs contain request IDs, not headers or keys. The server keeps the active case per conversation, so the model never handles case identifiers.

## Open points

- B to review the ordering of displayed findings in `student_b/diagnostics.py` (decision D31).
- Live Copilot gate G0 (credits), conflict-review flow for answers, total Oracle login deadline (D15), comparison module (A7).
- Two timed rehearsals of the demo (`student_c/docs/demo_script.md`, `tests/demo_backup_plan.md`).
