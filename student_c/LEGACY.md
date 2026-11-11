# Legacy — do not use as a demo fallback

`student_c/` is student C's earlier self-contained backend and console chat. It is kept for
history only. The active application is `agent.main:create_app` (see the root README).

The independent backend audit (finding **F13**, `docs/FINAL_BACKEND_AUDIT.md`) found that this
legacy evaluator has different numeric and error semantics from the active backend and contract
B2. **Do not substitute it for the active backend**, also not when the demo has a problem — use
the fallback steps in `docs/demo-script.md` instead.

Its tests run separately (finding F14, both trees use the package name `backend.app`):

```powershell
.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider student_c\tests
```

Retiring or reconciling it is the owner's (C) decision.
