<div align="center">

# 🔴 MAGNA TRACE

**Evidence-driven diagnostic assistant for production test & maintenance technicians**

*Built in 24 hours at **MAGNA Hackathon Košice 2026** (Task 9) by team **Codex’sFanClub***

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-TypeScript-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Oracle](https://img.shields.io/badge/Oracle-FREEPDB1-F80000?style=for-the-badge&logo=oracle&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-tool--calling-111827?style=for-the-badge)
![Tests](https://img.shields.io/badge/tests-355_passing-22C55E?style=for-the-badge)

</div>

---

## The problem

A test station on the line flags a part. The technician has a database full of raw measurements,
fail codes nobody documented, and five minutes. Generic AI chatbots answer confidently — and invent
numbers, causes and repair steps.

## What TRACE does

A technician asks in plain words — *"Station ST1003 shows errors. What happened?"* — and gets:

- 📊 **The facts, straight from Oracle** — value, limits, status and deviation for every measurement out of range, computed with exact `Decimal` arithmetic and **shown unchanged**.
- 🔎 **An evidence ID for every number** — click it and see the captured source row and the calculation rule. Nothing is re-queried, nothing is retyped by the model.
- 🧠 **Why it probably happened and what to do** — facts about the pattern (one part or many, one test or a series) plus a fixed troubleshooting table per kind of measurement, clearly marked as *not* a confirmed cause.
- 🌐 **Cross-station analysis** — finds the same error signature repeating on several stations, detects waves and rhythm, points to the likely shared cause and gives **one action plan to fix it once for all stations**.
- 💬 **One clarifying question at a time** — the technician's answer is stored word for word, under their name, as separate evidence.
- 📝 **Handover for the next shift** — findings, technician reports, open questions, next check; printable.

> In the real hackathon data TRACE found that the same error — 4–5 unrelated quantities of one test above their limits, fail code `1001` — hit **6 stations on 4 lines in two waves** (10:55–11:54 and 14:10–14:34), every 13–26 minutes. Not wear: a shared cause.

## How it stays honest

| Rule | How it is enforced |
| --- | --- |
| The model never states facts | The LLM only **chooses a tool**; every table, value and ID is rendered by the backend (`agent/render.py`) |
| No invented SQL | Fixed, parameterised `SELECT` statements only; a **read-only** Oracle user |
| Exact numbers | `decimal.Decimal` from the raw strings; raw strings kept next to parsed values; verified against Oracle's own arithmetic for all 1 524 rows — **0 mismatches** |
| Unknowns stay unknown | Meaning of fail code `1001`, `NULL`, units and timezone are reported as *unknown*, never guessed |
| Pasted IDs can't be hijacked | An evidence ID pasted into the chat is answered **deterministically**, without the model |
| No secrets in the browser | API key stays in the server-side proxy; HttpOnly session cookie; scrypt-hashed demo accounts |

## Architecture

```text
Browser ── React + TypeScript dashboard + chat (no diagnostic logic in TS)
   │  /api/v1/* through the Vite proxy (API key added server-side)
   ▼
FastAPI  agent.main:create_app
   ├─ agent/       chat agent (tool calling), sign-in, guidance, cross-station patterns, MCP endpoint
   └─ backend/app  REST contract B2: cases, evidence, answers, handover, stations
          ├─ oracle_repo.py    fixed parameterised SELECTs, row limits, timeouts
          └─ measurements.py   Decimal parsing, range status, quality flags
   ▼
Oracle FREEPDB1 / HACKATON  (SELECT-only user)
```

| Folder | Content |
| --- | --- |
| `backend/app/` | Oracle repository, measurement analysis, FastAPI app, cases, evidence, diagnostics |
| `agent/` | LLM agent, deterministic rendering, troubleshooting rules, pattern analysis, sign-in, MCP |
| `frontend/` | React dashboard: station tiles, findings table, evidence drill-down, chat |
| `contracts/b2/` | JSON Schema, examples and validator of the REST contract |
| `copilot/` | Instructions for a Microsoft Copilot Studio agent (MCP-ready) |
| `tests/` | 355 tests: analysis, API, agent, independent audit |
| `docs/` | Product spec, architecture, 40+ recorded decisions, independent audit, hackathon process notes |

## Run it locally

Needs Python 3.12+, Node 22+, Docker with Oracle Database Free and a SELECT-only user (`devtools/oracle/create_readonly_user.sql`), and any OpenAI-compatible model endpoint.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-test.txt -r agent\requirements.txt
cd frontend; npm install; cd ..
```

Server environment (never in Git or the browser): `TRACE_API_KEY` (32+ chars), `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_DSN`,
`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `TRACE_EXPECTED_ROUTE`, `TRACE_ALLOW_REAL_DATA=1` (only after data sharing is approved).

```powershell
.venv\Scripts\python.exe -m agent.make_employees          # demo accounts → agent\demo-accounts.local.md (git-ignored)
.venv\Scripts\python.exe -m uvicorn agent.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

```powershell
cd frontend
$env:VITE_TRACE_API_MODE = "live"; npm.cmd run dev        # open http://127.0.0.1:5173
```

Tests: `.venv\Scripts\python.exe -m pytest -q tests --ignore=tests\d5_live_smoke.py`

## Limitations

- Troubleshooting rules are general engineering knowledge, **not** a MAGNA-approved procedure; the system says so in every answer.
- Cases and sessions live in memory (single worker); a restart clears them.
- TRACE is read-only — it plans fixes, it does not send commands to machines.
- Microsoft Copilot Studio was not available during the event (no tenant credits); an open-weight model stood in, and the `/mcp` endpoint is ready for Copilot.

## Team Codex’sFanClub

| Member | |
| --- | --- |
| **Nikita Sokotniuk** | Integration, LLM agent & chat, cross-station analysis, troubleshooting rules, sign-in, UI/UX |
| **Ivan Kysel** | Team member |
| **Mykyta Terenia** | Team member — dashboard |
| **Vasyl Slyvka** | Team member |

Full commit history of all contributors is preserved. Process documents from the event (plans, hand-offs, per-student notes) are in `docs/hackathon/`, the independent backend audit in `docs/audit/`, every design decision in `docs/decisions.md`.
