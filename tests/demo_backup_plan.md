# D7.1 — Demo preparation and backup plan

**Preparation document only. No backup video was created or verified in this
stage.** Recording, playback checks and actual script timing are PENDING.
Every checkbox below is a future action, not a completed test or rehearsal.
The separate D8 task owns the two full rehearsals.

This plan covers the existing **SYNTHETIC local dashboard**. It does not meet or
replace the real Copilot/Oracle demonstration required by
[product.md §§6/9–10](../docs/product.md) and [plan.md D7/D8](../docs/plan.md).

## Preparation checklist — execute later, in this order

- [ ] Confirm the branch is `feature/nikita` with `git status --short --branch`;
  identify the actual recording revision with `git rev-parse HEAD`. Keep any
  uncommitted-document status explicit; do not commit as a preparation step.
- [ ] Check the pinned candidate SHA in
  [PINNED.json](../frontend/mock/b2/PINNED.json):
  `145652f917cd8b5ccda40f214a03ba45d490150d`. Do not edit fixtures to improve a demo.
- [ ] Use Node 22 and npm; Firefox on `PATH` is required for the browser tests.
  From the repository root, install the existing frontend dependencies:

  ```bash
  cd frontend
  npm install
  ```

- [ ] From `frontend/`, run the existing checks and note their actual outcomes.
  Historical D6 results do not establish a fresh pass. Do not record while
  test output or credentials could be visible.

  ```bash
  npm run build
  npm run test:mock
  npm run test:dashboard
  node --test scripts/transport.test.mjs
  ```

- [ ] After test processes exit, start terminal 1 from the repository root.
  Choose a nonempty throwaway key at the hidden prompt, off-camera:

  ```bash
  cd frontend
  read -rsp 'Local TRACE_API_KEY: ' TRACE_API_KEY; echo
  export TRACE_API_KEY
  export TRACE_API_TARGET=http://127.0.0.1:8001
  npm run mock
  ```

- [ ] Start terminal 2 from the repository root, entering the **same** key:

  ```bash
  cd frontend
  read -rsp 'Local TRACE_API_KEY: ' TRACE_API_KEY; echo
  export TRACE_API_KEY
  export TRACE_API_TARGET=http://127.0.0.1:8001
  npm run dev
  ```

- [ ] Open the loopback URL printed by Vite, normally
  `http://127.0.0.1:5173`. Verify that SYNTHETIC ONLY and Backend integration
  pending remain readable. Use the actual printed port below if it differs.
  Do not use `npm run preview` for this API demo: it has no development proxy.
- [ ] Frame the browser so all table columns and warnings are legible. Close
  notifications and unrelated tabs. Keep shell environment, request headers,
  real credentials, private Oracle rows and personal files out of the capture.
- [ ] Prepare the exact answer command below in a third terminal in
  `frontend/`. Send it only after opening the fixture case, once per opening.
  Read the [Slovak script](demo_pitch_sk.md); coordinate who sends this explicit
  synthetic setup step. It is not an answer-entry UI or autonomous AI call.

## Exact post-answer handover preparation

The mock supplies only a post-answer handover. During the demonstration, select
**SYNTHETIC-STATION**, then **Open diagnostic case**. After showing the findings
and their evidence, run the following from `frontend/` with Vite and mock running.
It reads the unchanged `record_answer` request from the pinned examples and
sends it through Vite; no API key belongs in this command.

```bash
node --input-type=module <<'JS'
import { readFileSync } from 'node:fs';
const fixtures = JSON.parse(readFileSync('mock/b2/examples.json', 'utf8'));
const fixture = fixtures.cases.find(item => item.name === 'record_answer');
const response = await fetch(new URL(fixture.path, 'http://127.0.0.1:5173'), {
  method: fixture.method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(fixture.request.body),
});
console.log(`SYNTHETIC answer setup: HTTP ${response.status}`);
if (!response.ok) process.exitCode = 1;
JS
```

Adjust only the loopback Vite port if needed. Expect HTTP 200 from this pinned
success request; confirm the actual result rather than declaring success in
advance. The returned `data` is the updated snapshot directly. The command
does not replace the dashboard's earlier findings snapshot; load the handover
to inspect the post-answer report and next action.

Do not reopen the case between setup and **Load handover**: reopening resets
the answer. Repeating the answer without resetting returns the pinned 409 error.
An unprepared handover returns a plain-text HTTP 501 replay-limit error; that
is a mock limitation, not an Oracle outage or a new B2 error code. If preparation
fails, keep the error visible and follow the failure plan below.

## What to capture in the planned recording

| Order | On-screen action | What to explain |
| --- | --- | --- |
| 1 | Opening title and SYNTHETIC banner | Task 9; this is a local dashboard/mock demonstration; live integration pending |
| 2 | Select SYNTHETIC-STATION; Open diagnostic case | Fixed fixture scope and source retrieval time; not fresh Oracle data |
| 3 | Show the three findings and warnings | Value, unit, recorded bounds, deviation; range/quality/raw code separate; in-range `1001` is not PASS/FAIL; invalid value remains NOT_EVALUABLE |
| 4 | Open the first row's Observed and Calculated links, then a calculation input link | Exact captured fields, rule, result and fixture evidence IDs; React does no arithmetic |
| 5 | Announce and send the prepared fixture answer through Vite | Explicit synthetic preparation; no Copilot call and no real technician report |
| 6 | Load handover; open the technician-report evidence link | Separate observations/reports, UNDETERMINED, hypotheses and limitations, unknowns, gaps/warnings, next action and references |
| 7 | Show closing status and limitations | Real Oracle/backend/Copilot integration and mandatory live journeys remain pending |

Follow the approximate timing in [demo_pitch_sk.md](demo_pitch_sk.md). A later
recording must show actual interactions; do not splice a failed request into a
claimed success or imply the prepared report was generated in conversation.

## Recording label and later completion checks

Use a planned filename such as
`magna-trace-backup-synthetic-YYYYMMDD-HHMM.mp4`, replacing the date/time only
when an actual recording exists. This is a naming convention, not an existing
artifact path. Keep the video in a team-approved location outside Git.

Opening card, persistent overlay and playback introduction should state:

> ZÁLOŽNÝ ZÁZNAM — MAGNA TRACE — SYNTHETIC / MOCK
> Lokálny React dashboard; integrácia Oracle/backend/Copilot neoverená.

Record the actual capture date/time, application revision and pinned B2 SHA in
the video description or accompanying approved metadata. Fixture timestamps
are fixed example data, not the recording time. Label prepared technician
reports as synthetic. No Oracle exports or keys may appear in the video.

- [ ] Time the spoken script and interactions; adjust pacing to approximately
  three minutes without adding unverified claims.
- [ ] Record and save the labelled video; note its real permitted location.
- [ ] Review the entire video for readable text, audio, accurate labels and
  absence of confidential information.
- [ ] Check local playback and the permitted presentation channel; have the
  file available without relying on the live app. Confirm organizer acceptance
  of a synthetic backup; acceptance does not establish a P0 gate pass.

All four actions remain PENDING in D7.1. No video location, duration, acceptance
or successful playback is asserted here.

## If the live demonstration fails

1. State what failed: local dashboard/mock, or a separately verified live
   integration if one is available later. Keep the actual error visible; do not
   display old findings as a fresh successful response.
2. For the local demo, check the two running processes and matching mock target
   port off-camera. Never display the key or open `.env`. If a case reset is
   needed, reopen it and repeat the disclosed answer setup once. Do not change
   production code or fixtures during the presentation.
3. If recovery would consume the slot, play the labelled backup **only if it
   has actually been recorded, reviewed and permitted**. Say it is a recording
   of synthetic local behavior and give its capture date. Never silently switch
   from a real backend failure to mock results.
4. If no approved recording exists, continue with the written pitch, README
   architecture and explicit pending status. Claim no successful interaction
   that the audience has not seen or that lacks recorded evidence.
5. Later record the failure and owner follow-up through the agreed team
   process. No live outage tests, fixes or D8 rehearsals are executed by this plan.

## SYNTHETIC versus real evidence

| Material | Classification and permitted claim |
| --- | --- |
| Station, measurements, limits, deviations, codes, times, case/evidence IDs, report, hypotheses and handover shown by this mock | SYNTHETIC pinned B2 examples; not Oracle results or physical diagnoses |
| Dashboard, HTTP mock and Vite proxy interactions | Real local software interactions using synthetic payloads; not live backend/Oracle/Copilot integration |
| D6 log | Historical local test evidence; targeted retest passed, original failures preserved; live checks still PENDING |
| D5 O01–O03 | Student D-reported manual SQL verification of a minimal redacted summary; API comparison and evidence IDs PENDING; do not copy private source rows into the presentation |
| Copilot Studio, Oracle-backed endpoints, autonomous record_answer and full MVP | Target architecture; no verified integrated demonstration in this checkout |

Pending handoffs: A's Oracle/analysis and permitted source scope (A2–A6/A8),
B's final agreed B2 freeze and real cases/evidence/endpoints (B2–B7), and C's
tenant/authentication/approved HTTPS path and live calls (C1–C8). Decisions
D10–D12 remain open. None is closed by a synthetic backup; D4–D6 execution,
D8 and P1 features remain outside this preparation stage.
