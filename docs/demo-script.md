# MAGNA TRACE — live demo script (3 minutes, run twice)

For the **integrated live system** (web dashboard + chat, real Oracle, open-weight model).
D's `tests/demo_pitch_sk.md` and `tests/demo_backup_plan.md` describe the earlier SYNTHETIC
dashboard and stay as they are. Timings below are a plan, not a measured rehearsal.

## T−15 min: start and check (off-screen)

1. Docker: Oracle `FREEPDB1` and the FreeLLMAPI router (`127.0.0.1:3001`) are running.
2. Backend from the repository root (one worker):
   `.venv\Scripts\python.exe -m uvicorn agent.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1`
3. Frontend: `cd frontend`, `$env:VITE_TRACE_API_MODE='live'`, `npm.cmd run dev`.
4. Open `http://127.0.0.1:5173`, sign in with a demo account from `agent/demo-accounts.local.md`
   (never show that file on screen).
5. Header chip must read **Oracle OK** and **Model ready/OK**. If not, see "If something fails".
6. Browser zoom 100 %, window maximised, no other tabs, notifications off.

## The run

| Time | Do | Say (one line) |
|---|---|---|
| 0:00–0:20 | Show the dashboard: chat left, stations right, employee in the header. | "A technician asks in plain words; every number comes from the line database with an evidence ID." |
| 0:20–1:00 | Click the suggestion **"Investigate station ST3003. What happened?"** | "The model only picks the check. The table is produced by the backend from Oracle, unchanged. Assessment stays UNDETERMINED — we do not guess causes." |
| 1:00–1:20 | Click any blue evidence ID in the reply (`E-…`). Close with **Close** or Esc. | "Every value resolves to the captured source row: raw value, limits, fail code, time." |
| 1:20–1:50 | Type: **"Yes, the fixture was re-clamped at the start of the shift."** | "The answer is stored as technician evidence under my name; observations are not changed." |
| 1:50–2:20 | Click **"Give me a handover for the next shift."**, then **Print handover** (cancel the print dialog). | "The next shift gets findings, my report, open questions and the next check." |
| 2:20–2:45 | Type: **"Which part should I replace?"** | "No repair advice and no free model prose: the answer is a fixed backend text that lists what TRACE can do (audit F01)." |
| 2:45–3:00 | Point at the status chip and the sign-in name. | "Read-only database user, fixed SQL, every fact traceable. Copilot Studio can connect through `/mcp`." |

Second run: press **New conversation** and repeat. A fresh case gets new evidence IDs.

## If something fails (say it, do not hide it)

- **Model down** (chip "Model down", or a rate-limit reply): continue without the chat. Click the
  **ST3003** tile, then a blue evidence link in the table, then **Load handover**. Same backend,
  same evidence, no model involved.
- **Oracle down** (chip "Oracle down", `SOURCE_UNAVAILABLE`): show the error as it is. The
  product never shows cached or invented values (invariant I-10). Restart the Oracle container.
- **Session ended** (sign-in screen appears): the backend was restarted; sign in again. Cases and
  sessions live in memory and do not survive a restart.
- **Unknown station** (`ST9999`): the API answers `NO_DATA` with the exact queried scope — useful to
  show that "no data" never means "healthy".

## Do not claim

- Copilot Studio was **not** used live (no credits); the open-weight model is a labelled stand-in (D32).
- Meanings of fail code `1001`, `NULL`, units and the timezone are **unknown**; equality with a
  bound counts as within (provisional, D09).
- The sign-in is a demo access list of a fictional company (D34), not corporate identity.
