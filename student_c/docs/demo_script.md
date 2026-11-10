# MAGNA TRACE — 3-minute demo script

> **Constraint:** the interim model runs on Groq's free tier: three models × 8,000 tokens per minute. Since 2026-11-11 a turn is one model call (the chat shows the backend's ready text directly), about 2–4k tokens. Measured 2026-11-11: four live turns (case, evidence, answer, handover) with no waits, about 10 s from opening the case to the recorded answer. The handover can therefore be shown live in the chat as well; keep the REST backup for failures.
> **Talking point:** "The model understands the request and picks the tool; the text you see is produced by the backend, so no number can be changed on the way."
> **Honesty rule:** say that the chat is a stand-in for Microsoft Copilot (no Copilot credits), and label anything prepared in advance as prepared.

## 10 minutes before

| # | Check | Command / action | Expected |
| --- | --- | --- | --- |
| 1 | Oracle up | `docker ps` | `oracle-free … (healthy)` |
| 2 | Router up | `docker ps` | `freellmapi-freellmapi-1 … (healthy)` |
| 3 | Backend up | Tab 1: `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` | `Application startup complete` |
| 4 | Backend reaches Oracle | `curl.exe -H "X-API-Key: $env:TRACE_API_KEY" http://127.0.0.1:8000/readyz` | `{"status":"ok"}` |
| 5 | Router reaches the internet | `curl.exe -s http://127.0.0.1:3001/api/ping` | `{"status":"ok",…}` |
| 6 | Chat open | Tab 2: `.venv\Scripts\python.exe harness\chat_openai.py` | `Real MAGNA data to model: ALLOWED` |
| 7 | Backup ready | Tab 3: PowerShell in `student_c`, backup commands below pasted but not run; screen recording of a full run available | — |
| 8 | **Do not use the model for the last 2 minutes** | — | All three per-minute limits full |

Font size: enlarge the terminal (Ctrl + mouse wheel) so the table is readable from the room.

## Timeline (3:00)

| Time | Say | Do |
| --- | --- | --- |
| **0:00–0:20** | "A technician sees abnormal test results at a station. Today they search measurements, limits and notes by hand. MAGNA TRACE answers from live Oracle data, and every number has a source." | — |
| **0:20–0:55** | While it answers: "The agent calls our backend; the backend reads Oracle read-only and computes deviations with exact decimal arithmetic. The model never calculates." Then: "Four measurements above limit, all on one serial at one moment. Screw Count is within limits but carries code 1001 — the meaning of the code is undocumented, so we show it raw and never call it pass or fail. Assessment: UNDETERMINED." | Type `Investigate station ST3003. What happened?` |
| **0:55–1:30** | "Where does 50.457 come from?" — **key moment.** "It resolves to a calculated evidence record: the rule, the raw inputs from Oracle, the row locator. Nothing is invented." | Type `Where did 50.457 come from?` |
| **1:30–2:15** | "The system asked one question Oracle cannot answer. I answer as the technician." While it answers: "Notice I did not tell it to record anything — the agent calls `record_answer` by itself. The answer becomes evidence; the measurements don't change, and the label stays UNDETERMINED, because a report is not proof. The next step is an escalation to maintenance — no invented repair." | Type `Yes, the fixture was re-clamped after the morning shift.` |
| **2:15–2:35** | "And the handover for the next shift is built from the case, so every number in it is the one shown before." | **Backup command H** (instant, no model call) — or skip if time is short |
| **2:35–3:00** | "Honest limits: this chat stands in for Copilot because the Copilot environment has no credits — the backend is the same MCP server Copilot would call. Code 1001 and the scrap limits are undocumented, so we don't interpret them. Next: Copilot, cross-station comparison." | — |

Do **not** do "Which part should I replace?" live — it costs a turn. Mention it: "It refuses repair advice without an approved procedure."

## If the model is slow or fails

`[rate limit] … waiting` on stage: keep talking for up to 20 s. If it is still waiting, switch to the backup for that step and say so.

Backup commands — Tab 3, same data, no model involved:

```powershell
$h = @{ "X-API-Key" = $env:TRACE_API_KEY }
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/cases -Headers $h -ContentType "application/json" -Body '{"station_number":"ST3003"}'
$r.data.findings | Format-Table measurement, raw_value, raw_upper, range_status, deviation, raw_fail_code, evidence_id -AutoSize
```

Evidence for 50.457 (the calculation record of Motor Speed):

```powershell
$calc = ($r.data.findings | Where-Object measurement -eq "Motor Speed").calculation_evidence_id
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/cases/$($r.case_id)/evidence/$calc" -Headers $h | ConvertTo-Json -Depth 6
```

Technician answer:

```powershell
$body = @{ question_id = $r.data.next_action.question_id; answer_text = "Fixture was re-clamped after the morning shift."; answer_kind = "YES" } | ConvertTo-Json
(Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/cases/$($r.case_id)/answers" -Headers $h -ContentType "application/json" -Body $body).data.case_update.message
```

**H — Handover:**

```powershell
(Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/cases/$($r.case_id)/handover" -Headers $h).data.text
```

Note: H shows the handover of the case opened in Tab 3. If you use it right after the live chat, say "this is the same handover from the API".

Last resort: the screen recording of a full run, announced as a recording.

## Rehearsal

Run the timeline twice with a stopwatch before the presentation, with the 2-minute idle period before each run. Note the wait times; if turn 3 waits more than 20 s in both rehearsals, plan to show turn 3 from the backup.
