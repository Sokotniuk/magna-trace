# Validation — 2026-11-11

## Commands actually run

Interpreter: `F:\tuke\hackaton\.venvs\student-a\Scripts\python.exe`, Python
3.13.15; installed oracledb 26.1.0 and pytest 9.2.0. No packages added.

| Working directory | Command (using the interpreter above) | Result |
| --- | --- | --- |
| F:\tuke\hackaton\magna-trace-student-a | `python -B -m pytest -q -p no:cacheprovider` | 179 passed in 8.17s; 0 failed/skipped |
| Same source directory | `python -B -m pip check` | No broken requirements found |
| F:\tuke\hackaton\data\A-to-B-integration | `python -B -m pytest -q -p no:cacheprovider` | 192 passed in 8.28s; 0 failed/skipped |
| Same package directory | Import oracle_repo, measurements and handoff_adapter; assert module paths resolve inside package root | PASS |
| Source repository | `git diff --check` and `git diff --cached --check` | PASS |

Packaged tests: unchanged A1 (48), A2 (52), A3 (41), A4 SQL (7), A6 (26),
plus 18 new isolated handoff checks = 192. A5's five verification tests and its
uncommitted SQL are deliberately excluded from this integration package, but all
five passed in the 179-test source run. No test was weakened, skipped or deleted.

New checks exercise A2 -> A3 -> exact JSON with synthetic rows, preserved raw
whitespace/code/source time, frozen record identity, hand-derived deviation 0.0150,
high precision under low Decimal context, empty page/scope, null/blank raw values,
invalid scope before connection, typed failures (including ORA-01013), station
page counts/truncation, explicit raw-number projection, and rejection of floats,
nonfinite Decimal and unsupported objects. Synthetic reference strings are passed
through unchanged; this does not validate B's real evidence ID generator/store.

## Content and provenance review

- All seven copied Python source/test files match their working-tree bytes and
  SHA-256 values. No line-ending normalization of these copies.
- Approved A1/A4 baseline is the exact HEAD Git blob, with provenance recorded.
  All three A4 query bodies match the longer current A5 working-tree SQL.
- AST comparison against HEAD confirms A6 did not change the three public Oracle
  signatures, default/internal max limits or fixed success-path SQL constants.
- All package Python parses. The only non-standard imports are oracledb/pytest.
- Credential-literal, private-key/token/URL patterns and excluded-artifact scan
  passed. Credential literals in existing tests are explicitly synthetic, not
  real account secrets. Included SQL is reference SELECT text, not an exported
  result set. No private A4 sheet, full database export, .env, log, Git metadata,
  unrelated SCA file, bytecode or cache directory is included.
- Source file hashes, HEAD, branch, status, working diff and staged diff match the
  pre-assembly snapshot. Existing A5/A6 work remains unchanged and unstaged.
- No commit, push, merge, bundle, repository edit, dependency installation or A7 work.

`MANIFEST.md` lists every archive file. `SHA256SUMS.txt` covers every other file;
it excludes itself to avoid a circular hash. `verify_package.py` verifies this
manifest and rejects unexpected files. The archive is built only from these files;
ZIP integrity, exact entry names and each member's bytes are checked against the
directory. The final ZIP hash is distributed in the external `.zip.sha256` sidecar
and final report, not embedded recursively inside the archive.

## Acceptance not established here

No authenticated Oracle, tunnel, Copilot or B FastAPI run was performed in this
packaging session. A6's six reported live passes and two pending checks come from
the user's current handoff request; a full run/hash transcript was not supplied.
D15 remains OPEN. B's actual checkout/public schema was not tested. The adapter is
an internal projection example, not proof of B2/B5/B6 compatibility. B7/D6 real
envelopes and independent integrated-revision review remain pending. A5 still
awaits D10 disposition acceptance. A8 is not DONE; A7 remains unimplemented.
