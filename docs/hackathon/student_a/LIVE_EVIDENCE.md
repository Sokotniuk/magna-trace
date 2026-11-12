# Live evidence and independent reproduction

Prepared 2026-11-11. These are previously student-executed observations, not a new
Oracle session by the packaging agent. No credentials, private evidence sheet,
source row exports or Oracle archives are included.

## Recorded evidence

| Observation | Previously verified result | Provenance |
| --- | --- | --- |
| Measurement count | 1524 | A1 repeated baseline and live callable; D16/D18; reiterated in current request |
| Distinct station numbers | 23 | A1 baseline, A2 live station listing; D16/D23 |
| ST3003 measurements | 60 | A2/A4 live SQL and Student D independent D5 report; D32/D38 |
| ST1001 measurements | 104 | Plan A A2 live row: total 104, returned 100, truncated true; current request |
| ST3003 Angle | ABOVE, deviation 7.592, recorded unit deg | A4 independent calculation; D32/D38; current request supplies unit |
| ST3003 Vibration | ABOVE, deviation 0.354, recorded unit mm/s | Same provenance |
| ST3003 Position Accuracy | ABOVE, deviation 0.292, recorded unit mm | Same provenance |
| Screw Count | Value 8, bounds 8..8, unit pcs, raw code 1001; WITHIN_RECORDED_BOUNDS, deviation null | D32/D38; current request supplies unit |

The A4 verifier selected three of four ST3003 breaches; three selected findings
does not mean the station has only three breaches. Records are not merged into an
incident. The Screw Count station/serial/time is deliberately not inferred here.
No private sheet was copied or read for this package. Use the approved A4-02 lookup
below to obtain its current scope locally. ST3003 with no serial/time filters and
limit 100 is a confirmed demo scope (60 rows at the recorded source state).
No narrower serial/time scope is invented. Current-source drift must be reported,
not hidden by pinning historical values into runtime responses.

## Exact approved SQL reference procedure

`docs/data-baseline.sql` is the exact committed A1/A4 Git blob at
`5f205955a762e407f9b299796b30a2bd92ca8ce5`, not the longer uncommitted A5 file.
Its three A4 SELECT templates were compared with the current working tree and
match. SHA-256 and provenance are in SOURCE_PROVENANCE.json. The unchanged A1
tests depend on this file; it is included as reference SQL, never runtime fallback.

An authorized student runs these steps on the approved Oracle host using a verified
SELECT-only account and a parameter-capable SQL client. Do not paste passwords into
commands or use SQL*Plus EXEC/PLSQL to assign binds. Set query/call limits in the
client. Do not publish result rows or spool them into this package.

1. Run the executable A1 baseline SELECTs twice (A4 templates remain inside block
   comments). Inspect A1-01–A1-07 identity/effective privileges, metadata and separate
   exact table counts. Compare like-for-like results and retrieval times. A1-08 gives
   measurement count/distinct stations; A1-09 groups station counts, independently
   confirming ST3003=60 and ST1001=104. These references read the source directly,
   independently of A's runtime SELECTs. If the account has only measurement-table
   access, have the environment owner run the broader privilege/baseline checks;
   do not broaden grants through this handoff.
2. Extract the SQL body of the labelled `/* A4-01 ... */` block unchanged and bind:
   station_number=`ST3003`, serial_number=None, from_time=None, to_time=None,
   row_limit=100. Keep all returned rows local. Bind time parameters as Oracle
   TIMESTAMP when non-null; do not interpolate them into SQL. This SELECT returns
   native source TIMESTAMP values plus scope count, capture ordinal and temporary
   candidate multiplicity. It preserves raw value/limits/code/unit and extra context.
3. Independently select Angle, Vibration and Position Accuracy from that captured
   result. Check the original nine fields (station, serial, name, value, lower,
   upper, unit, code, timestamp), plus the temporary locator/ordinal when needed.
   Apply the documented strict numeric grammar, then Decimal from raw strings.
   For an upper breach independently subtract upper from value. Expected recorded
   deviations are 7.592, 0.354 and 0.292 respectively. Do not call analyze_measurement
   to generate the expected answers. Compare your independently calculated result
   with A2 → A3 afterward. Use enough Decimal precision or hand/Fraction arithmetic;
   never float, SQL implicit locale conversion, rounding or fail-code semantics.
4. Extract A4-02 unchanged and bind fail_code=1001, measurement=`Screw Count`,
   row_limit=100. Verify total_matching_rows and truncation before claiming complete
   coverage. Identify the actual 8/8/8 pcs record locally; verify numerical equality
   independently. Expect WITHIN_RECORDED_BOUNDS with null deviation while code 1001
   remains semantically unknown. Retain its actual station/serial/time locally;
   do not assume it belongs to ST3003.
5. For each selected record, extract A4-03 unchanged and bind its just-captured
   station_number, serial_number, source_rowid and row_limit=2. Expect one exact
   recheck and compare all captured fields, including nulls/whitespace. Compare
   native naive timestamps to native naive timestamps; for comparison with A2's
   source string, use `.isoformat(timespec="microseconds")` without adding a zone.
   These are verification rechecks only, not the implementation of get_evidence.
6. Recheck scope totals and source stability; a changed/missing locator or changed
   value invalidates the comparison and must be reported. Save reviewer/date,
   code/SQL hashes, safe aggregate results and discrepancies in the team's accepted
   record. Keep source rows private. Student D independently checks the actual
   integrated revision before A8 can be DONE.

The A4 blocks are intentionally commented so running the baseline does not execute
unbound queries. Use only their exact SELECT bodies with separate bind values;
no dynamic predicates or source identifiers. A4-03's ROWID is a temporary check of
the current source snapshot and has no lifetime guarantee.

## Later A6 live evidence supplied in the current request

| Check | Student-reported result |
| --- | --- |
| Restricted identity | PASS |
| Oracle COUNT = 1524 | PASS |
| Empty scope | PASS |
| Post-login timeout DPY-4024 observed | PASS |
| Explicit cancellation ORA-01013 observed | PASS |
| Source stability | PASS |

Summary: **PASS=6 FAIL=0 NOT_VERIFIED=2**. This updates the earlier plan ledger's
pending live probes for this handoff report only; no repository ledger is rewritten.
The request does not include the full live execution transcript or hash manifest,
so the package's current source hashes are not asserted to be independently pinned
by that run. Historical A2 live hash was
`7c6cf9117c76317584dc196081a2e4acf560221007b2b09bf5e99e4130becb41`;
current A6 working-tree oracle_repo.py is a different, explicitly hashed version.
The current A3 hash is unchanged from its recorded acceptance.

The two remaining gaps are the hard whole-login/handshake deadline (D15) and real
B-side envelope/integration verification. A's live runner cannot verify B6/B7's
FastAPI responses. Observation of explicit cancellation does not by itself mean
A maps ORA-01013 to TIMEOUT: current standalone cancellation mapping is
SOURCE_UNAVAILABLE. See INTEGRATION_CONTRACT.md for the actual classifier.

## Limits retained

- D15 OPEN: a TCP establishment timeout is not a hard Oracle login/handshake
  deadline. Post-login call_timeout applies per round trip, not to the whole call.
  Recovery/cleanup can add time. B/C must settle the connector budget and runtime
  containment; this package adds no cancellation/deadline framework.
- Raw MEASURE_FAIL_CODE=1001 and null: semantics UNKNOWN; never PASS/FAIL inference.
- Source timezone UNKNOWN; preserve TIMESTAMP(6), separate UTC retrieved_at.
- Inclusive numerical specification boundaries PROVISIONAL (D09).
- Intervention/scrap/nominal/tolerance semantics UNKNOWN; do not use as bounds.
- Unverified joins DISABLED. A5 technical work is complete, D10 review still pending.
- ROWID is not a durable evidence identifier; B generates immutable case-local IDs.
- A6 code completion is not integrated acceptance; A8 remains pending. No A7 work.
- No live Oracle, tunnel or Copilot call was performed while assembling this package.
