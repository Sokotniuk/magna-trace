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

## The run — demo station ST1003 (real data, nothing staged)

ST1003 (welding) has one real test of serial `1000000004`, recorded 2026-11-09 11:54:42, where five
values are above their recorded limits, all with fail code `1001`: Weld Voltage 28.255 V (23–27),
Weld Time 1286.156 ms (1050–1250), Cooling Flow 15.987 l/min (11–15), Resistance .295 mOhm
(.16–.26), Penetration 2.973 mm (1.6–2.6). Checked against Oracle's own arithmetic (D35).
Five other stations show the same pattern (ST1004, ST2003, ST4003, ST4004 with five values,
ST3003 with four); any of them is a backup.

| Time | Do | Say (one line) |
|---|---|---|
| 0:00–0:20 | Show the dashboard: 6 station tiles outlined in red ("5 out"). | "These six stations have recorded values outside their limits. The count comes from the database; it is not a diagnosis." |
| 0:20–0:45 | Click the outlined **ST1003** tile. Five red rows appear, status **ABOVE**. | "Weld Time 1286.156 ms against an upper limit of 1250: 36.156 above. Five values of one test, one part." |
| 0:45–1:15 | On the **Weld Time** row click **Copy for chat**. The text (with the error ID `E-…-48`) is copied and already sits in the chat field — press **Enter** (or paste it with Ctrl+V). | "We hand the error ID to the assistant. It continues the same case and shows the rule, the inputs and the raw source row." |
| 1:15–1:45 | Type: **"Yes, the welding electrode tips were changed at the start of the shift."** | "My answer is stored word for word under my name, in the same case; the measurements are not changed." |
| 1:45–2:15 | Type: **"Give me a handover for the next shift."**, then **Print handover** (cancel the dialog). | "The next shift gets findings, my report, open questions and the next check." |
| 2:15–2:40 | Type: **"Which part should I replace?"** | "No repair advice and no free model prose: a fixed backend text lists what TRACE can do." |
| 2:40–3:00 | Point at the status chip and the sign-in name. | "Read-only database user, fixed SQL, every fact traceable. Copilot Studio can connect through `/mcp`." |

Alternative start without the dashboard: type **"Station ST1003 shows errors. What happened?"** in the chat.

Second run: press **New conversation** and repeat (new case, new evidence IDs). Leave a few seconds
between messages: the free model tier can rate-limit bursts (seen once in rehearsal; the reply says
so and nothing is changed — send the message again).

## If something fails (say it, do not hide it)

- **Model down** (chip "Model down", or a rate-limit reply): continue without the chat. Click the
  outlined **ST1003** tile, then a blue evidence link in the table, then **Load handover**. Same backend,
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
