# Student A → B integration contract

Inspected 2026-11-11 on feature/student-a, HEAD `5f205955a762e407f9b299796b30a2bd92ca8ce5` plus existing A6 working-tree changes.
This documents the shipped bytes, not a replacement B2 public schema. The accepted
A2 defaults/success SQL and A3 implementation remain unchanged. A6 completion and
A8 integrated acceptance are separate. See SOURCE_PROVENANCE.json for hashes.

## Exact callables

All Oracle functions are synchronous, open/own/close one connection and cursor per
call, and accept only keyword arguments. No pool or repository class needs initialization.
Only `analyze_measurement` accepts its record positionally. The following signatures
and dataclass field annotations are extracted from the packaged source:

```python
def count_measurements(
    *,
    user: str,
    password: str,
    dsn: str,
    call_timeout_ms: int = 5000,
    connect_timeout_seconds: int = 5,
) -> int:
```

```python
def read_measurements(
    *,
    user: str,
    password: str,
    dsn: str,
    station_number: str | None = None,
    serial_number: str | None = None,
    from_time: str | datetime | None = None,
    to_time: str | datetime | None = None,
    limit: int = DEFAULT_LIMIT,
    call_timeout_ms: int = 5000,
    connect_timeout_seconds: int = 5,
) -> MeasurementPage:
```

```python
def list_stations(
    *,
    user: str,
    password: str,
    dsn: str,
    q: str | None = None,
    limit: int = DEFAULT_LIMIT,
    call_timeout_ms: int = 5000,
    connect_timeout_seconds: int = 5,
) -> StationPage:
```

```python
def analyze_measurement(
    record: MeasurementRecord,
    *,
    extra_raw_fields: Mapping[str, str | None] | None = None,
) -> MeasurementEvaluation:
```

## Exact frozen dataclasses

All are `@dataclass(frozen=True)`. Required constructor fields have no implicit
defaults, even when nullable. Tuples plus immutable scalar fields preserve captures;
evaluation.record is the exact input object. No evidence IDs are created here.

```python
class MeasurementScope:
    station_number: str
    serial_number: str | None
    from_time: str | None
    to_time: str | None
    limit: int
```

```python
class MeasurementRecord:
    station_number: str
    serial_number: str
    measurement: str
    raw_value: str | None
    raw_lower: str | None
    raw_upper: str | None
    unit: str | None
    raw_fail_code: int | Decimal | None
    book_stamp: str | None
    part_number: str
    workorder_number: str
    measure_step_number: int | Decimal
    measure_type: str | None
    source_rowid: str
    snapshot_ordinal: int
```

```python
class MeasurementPage:
    scope: MeasurementScope
    records: tuple[MeasurementRecord, ...]
    total_matching_rows: int
    first_book_stamp: str | None
    last_book_stamp: str | None
    missing_book_stamps: int
    retrieved_at: str
    source_table: str = 'HACKATON.SNO_MEASUREMENT_DATA'
    warnings: tuple[str, ...] = ('SOURCE_TIMEZONE_UNKNOWN', 'ROWID_NOT_DURABLE')
```

```python
class StationRecord:
    station_number: str
    record_count: int
```

```python
class StationPage:
    q: str | None
    limit: int
    records: tuple[StationRecord, ...]
    total_matching_stations: int
    retrieved_at: str
```

```python
class MeasurementEvaluation:
    record: MeasurementRecord
    parsed_value: Decimal | None
    parsed_lower: Decimal | None
    parsed_upper: Decimal | None
    range_status: RangeStatus
    deviation: Decimal | None
    deviation_rule: DeviationRule | None
    quality_flags: tuple[QualityFlag, ...]
    field_issues: tuple[tuple[NumericField, ParseIssue], ...]
    extra_raw_fields: tuple[tuple[str, str | None], ...]
```

Computed properties, which `dataclasses.asdict` alone omits:

- MeasurementPage.returned_count: int = len(records); truncated: bool = returned_count < total_matching_rows.
- StationPage.returned_count: int = len(records); truncated: bool = returned_count < total_matching_stations.
- MeasurementEvaluation.raw_fail_code: int | Decimal | None, delegates to record.raw_fail_code.
- MeasurementEvaluation.numeric_evaluation: IN_RANGE / OUT_OF_RANGE / NOT_EVALUABLE, internal convenience only.
  Never substitute those first two values for canonical B2 range_status.

## Raw fields and time

| MeasurementRecord field | Oracle source |
| --- | --- |
| station_number / serial_number / measurement | STATION_NUMBER / SERIAL_NUMBER / MEASURE_NAME |
| raw_value / raw_lower / raw_upper | MEASURE_VALUE / LOWER_LIMIT / UPPER_LIMIT, unchanged nullable text |
| unit / raw_fail_code | UNIT nullable text / MEASURE_FAIL_CODE nullable exact NUMBER |
| book_stamp | BOOK_STAMP formatted by SQL as YYYY-MM-DDTHH:MM:SS.ffffff, or null |
| part_number / workorder_number | PART_NUMBER / WORKORDER_NUMBER |
| measure_step_number / measure_type | MEASURE_STEP_NUMBER exact NUMBER / MEASURE_TYPE nullable text |
| source_rowid | ROWIDTOCHAR(ROWID), temporary physical locator, not a durable ID |
| snapshot_ordinal | 1-based index within the captured returned page; not a database key |

Required source text (station, serial, measurement, part, workorder, rowid) must be
nonempty. Value/limit text, whitespace, trailing zeros and nulls are not normalized.
NUMBER fields use a cursor-local Decimal converter; raw_fail_code is validated as
integral but retained as int or Decimal, never a guessed PASS/FAIL string. A3 retains
it in record. Source TIMESTAMP(6) text retains all six fractional digits with no Z,
offset or timezone conversion. `retrieved_at` is separately UTC ISO text with +00:00.

A2 does not fetch STATION_ID or nominal/tolerance/intervention/scrap fields.
station_number is the returned station identifier, not the distinct STATION_ID column.
A3 accepts these optional extra_raw_fields keys only: NOMINAL, TOLERANCE,
LOWER_INTERVENTION_LIMIT, UPPER_INTERVENTION_LIMIT, LOWER_SCRAP_LIMIT,
UPPER_SCRAP_LIMIT. Values are str | None, captured as a sorted immutable tuple.
They are never bounds. Omission is unavailable context, not an invented null source value.

## Scope, count, search and ordering

- read_measurements requires a nonblank station_number at runtime despite its None
  signature default. Serial is optional but, when present, must be nonblank. Identifiers
  are literal and untrimmed; binary, case-sensitive equality applies.
- from_time/to_time each accept None, a naive datetime, or `YYYY-MM-DD[T or space]HH:MM:SS`
  with optional 1–6 fractional digits. Aware timestamps, Z, dates-only, invalid calendar
  values and start >= end are INVALID_SCOPE. Scope echoes normalized six-digit ISO text.
  Interval is [from_time, to_time); either endpoint may be independently omitted.
- limit is an actual int (bool is rejected), 1..500 inclusive; default 100.
- Measurements: BOOK_STAMP DESC NULLS LAST, ROWID ASC. Identical projected records
  remain separate; a ROWID tie-break orders one capture, not a permanent record identity.
- total_matching_rows and min/max/missing BOOK_STAMP metadata cover the entire filtered
  scope before the limit, via analytic values in the same SELECT. They are not returned-page
  coverage or a count of independent units. Returned_count is len(records); exact-cap with
  no omitted rows is not truncated. No distinct-serial count is returned by A2.
- Empty page: records=(), total=0, first/last=None, missing=0, truncated=False, exact scope
  and fresh retrieval time. B maps this successful measurement read to NO_DATA.
- list_stations q=None means no filter; empty/whitespace q is INVALID_SCOPE. Search is
  case-sensitive literal substring (INSTR), not prefix or SQL LIKE; % and _ are literals.
  Results group and sort by station_number COLLATE BINARY ascending. Each has record_count
  across that station. total_matching_stations counts matched groups before the limit.
  No source-time coverage fields exist on StationPage.

## A3 calculations and flags

Parsed inputs are Decimal | None, directly from strict text grammar
`[+-]?[0-9]+(?:[.][0-9]+)?` after trimming the parsing copy only. Exponents,
nonfinite values, ambiguous separators and unit suffixes are rejected.
range_status is exactly ABOVE, BELOW, WITHIN_RECORDED_BOUNDS or NOT_EVALUABLE.
Breach deviation is exact Decimal; rule is `value - upper` or `lower - value`.
Non-breach and unevaluable results have deviation=None AND deviation_rule=None,
not zero. D27 records prior B5 acceptance of this shape, despite stale provisional
source docstrings; current B integration still needs verification.

Flags appear in fixed order: MISSING, UNPARSEABLE, LIMIT_UNKNOWN, LIMIT_INVALID,
PARTIAL_BOUNDS, UNIT_UNKNOWN, SEMANTICS_UNKNOWN. field_issues attributes MISSING
or UNPARSEABLE to raw_value/raw_lower/raw_upper. Missing bounds do not alone add
the top-level MISSING flag; malformed nonempty numeric fields add UNPARSEABLE.
One usable bound with the other missing permits a flagged one-sided evaluation;
malformed/reversed limits prevent evaluation. SEMANTICS_UNKNOWN is always present,
including when raw code is null. Missing unit does not alter numeric range status.
Equality within bounds and numeric grammar remain D09 provisional.

## Error responsibilities

| A behavior | Class/base and attributes | B boundary responsibility |
| --- | --- | --- |
| Invalid external scope, before connecting | InvalidScopeError(ValueError), class code=INVALID_SCOPE, message in str(error); no phase/driver_code attributes | Map to frozen INVALID_SCOPE envelope, no data |
| Driver/OS failure or unusable source result | SourceUnavailableError(RuntimeError), code=SOURCE_UNAVAILABLE; driver_code: str or None and phase: str or None (default None) | Map redacted code/message, no measurement data |
| Recognized timeout | OracleTimeoutError(RuntimeError), code=TIMEOUT; same optional diagnostics | Map TIMEOUT, no measurement data |
| Empty successful measurement page | No exception and no NoDataError class | Emit NO_DATA with exact page.scope, retrieval time and zero count, never fabricate a source failure |
| Invalid credentials/configuration/timeout arguments | ValueError, no canonical code | Validate internal server configuration at startup; do not call this an end-user scope error |
| Invalid A3 input/extra field | TypeError or ValueError | Programming/integration fault; no substitute observation |

The two runtime error classes are siblings; neither inherits the other. Structured
driver exceptions and OS failures are classified by A. Timeout codes are DPY-4024,
DPI-1067, ORA-12170, ORA-12535, plus TimeoutError; recognized wrappers DPY-6005,
DPY-4011 and DPI-1080 can carry structured timeout causes/context. Ordinary authentication
errors do not inherit unrelated timeout context. Standalone ORA-01013 cancellation
maps to SOURCE_UNAVAILABLE, not TIMEOUT: cancellation alone is not proof of timeout.
Safe diagnostic driver_code is an allow-listed ORA/DPY/DPI code or None; phase is
connect/configure/execute/fetch/cleanup or None for direct validation errors.
Messages omit driver details. Cleanup is attempted without masking the primary
read error; failure of cleanup after success prevents returning even an empty page.
Do not expose exception context/tracebacks, connection settings or raw driver messages.

B6/B7 owns status/HTTP mapping, request_id, envelope, auth and scope attachment.
This package does not prescribe a new HTTP schema or prove B's envelopes. Catch
InvalidScopeError before a general ValueError. No cached, mock or partial rows on errors.

## Compatibility with B's requested interface

This compares the request supplied for this handoff with inspected A code. B's
current checkout/schema is not supplied here, so field-level B2 acceptance is pending.

| B requirement | Classification | Actual behavior / required action |
| --- | --- | --- |
| Required station, optional serial/from/to | EXACT MATCH | Runtime station required; exact serial, independent optional endpoints |
| Exact pre-limit total, bounded deterministic rows | EXACT MATCH | One SELECT, analytic total; newest first/ROWID tie-break |
| Truncation and time coverage | EXACT MATCH | Full filtered scope coverage; explicitly map properties and missing timestamp count |
| Original raw fields | EXACT MATCH | Listed projection only, no normalization or guessed metadata |
| q + limit and stable station sorting | EXACT MATCH | Literal case-sensitive substring; q=None unfiltered |
| Identifier and measurement count | ADAPTER REQUIRED | Map station_number and record_count to B2 names; STATION_ID is not fetched |
| Decimal parsed values/deviation/rule | EXACT MATCH | nullable non-breach deviation, no float |
| Independent flags, raw code, immutable record | EXACT MATCH | Retained raw source object; no evidence ID on A objects |
| External from/to naming; JSON fields | ADAPTER REQUIRED | Translate B aliases to from_time/to_time; map nested record to B2 explicitly |
| Decimal/raw NUMBER wire format | ADAPTER REQUIRED | Exact decimal strings; string/null helper for raw NUMBER if B2 requires it |
| Canonical statuses and evidence references | ADAPTER REQUIRED | Use range_status, B-generated stored IDs; never emit internal IN_RANGE/OUT_OF_RANGE as range_status |
| NO_DATA/SOURCE_UNAVAILABLE/TIMEOUT/INVALID_SCOPE | ADAPTER REQUIRED | Typed errors plus successful empty page; B owns error envelope |
| B mentions max 200 vs A max 500 | CONTRACT DECISION REQUIRED | Proposal H1: external cap 200; retain A default 100/max 500 unchanged; B confirmation required |
| Prefix/case-insensitive/blank search if expected by B | CONTRACT DECISION REQUIRED | H2: confirm literal substring/case sensitivity and blank rejection; never silently alter A2 |
| Inclusive end or timezone-bearing bounds if expected by B | CONTRACT DECISION REQUIRED | H3: retain half-open naive timestamps; reject unsupported input or obtain approved contract change |
| Hard total login/handshake deadline | CONTRACT DECISION REQUIRED | D15 remains OPEN; 5s TCP and 5000ms post-login round-trip are not total request deadlines |

H1–H3 are local handoff review items, not new approved decisions in the repository.
If B2 already promises incompatible behavior/types, B/C/D must agree the public
change, append docs/decisions.md and update Swagger/drift tests. A2 is not changed.
Raw NUMBER can be int or Decimal internally; generic projection preserves int as
JSON integer and Decimal as string. B must explicitly choose the accepted wire
field type; use raw_number_text for a consistent string/null field. This preserves
the exact number without claiming a source text spelling for an Oracle NUMBER.

## Minimal calls and serialization

See README_FOR_STUDENT_B.md for environment settings and runnable commands.

```python
from backend.app.oracle_repo import count_measurements, read_measurements, list_stations
from backend.app.measurements import analyze_measurement
from handoff_adapter import dumps_exact, raw_number_text

# settings is populated server-side from ORACLE_USER/ORACLE_PASSWORD/ORACLE_DSN.
total = count_measurements(**settings)
stations = list_stations(**settings, q=None, limit=100)
page = read_measurements(**settings, station_number="ST3003", limit=100)
evaluations = tuple(analyze_measurement(record) for record in page.records)
internal_json = dumps_exact({"page": page, "evaluations": evaluations})
# For a B2 string/null field: raw_number_text(evaluations[0].raw_fail_code).
# Guard empty page before indexing; B maps an empty measurement page to NO_DATA.
```

The helper is an internal projection example, not a FastAPI response. It retains
raw fields, nullable values, tuples as arrays, source timestamp strings and page
properties; only finite Decimal becomes exact str. It rejects floats and unsupported
objects rather than default=str on everything. Native datetime is deliberately not
accepted: A2 already serializes TIMESTAMP(6) losslessly. Do not convert its text via
a timezone-aware Pydantic field. Decimal strings may use exact exponent notation
for tiny values; if B requires fixed-point presentation, use format(value, 'f')
without quantizing/rounding and validate against the frozen schema.

B3 must capture OBSERVED source + scope/table/retrieved_at/ordinal, issue its own
case-local ID, and link each CALCULATED record to that stored input ID and rule.
Pass B-issued references through unchanged. Neither source_rowid, snapshot_ordinal
nor a hash is itself a case-local evidence ID. Never requery old evidence. Preserve
coverage and raw capture privately while minimizing fields sent to the cloud.
