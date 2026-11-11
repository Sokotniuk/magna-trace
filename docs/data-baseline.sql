-- A1 metadata, count and profile baseline. Run from the SELECT-only session.
-- All statements are SELECTs. Keep results local; do not commit row exports.
-- SNO_MEASUREMENT_DATA column names/types were supplied by the student from
-- ALL_TAB_COLUMNS on 2026-11-10 (23 columns). Record each labelled result and
-- rerun this file twice, comparing totals only when the source is unchanged.
-- Application code does not query these profiles; this file is an A1 SQL check.

-- A1-01: Record session identity, PDB and retrieval time before verifying grants.
SELECT SYS_CONTEXT('USERENV', 'SESSION_USER') AS session_user,
       SYS_CONTEXT('USERENV', 'CON_NAME') AS pdb_name,
       SYS_EXTRACT_UTC(SYSTIMESTAMP) AS retrieved_at_utc
FROM dual;

-- A1-02: Effective system privileges. CREATE SESSION is needed for login.
-- Any broad or write privilege requires review before application use.
SELECT privilege
FROM session_privs
ORDER BY privilege;

-- A1-03: Enabled roles and their system/object grants. A metadata visibility
-- gap needs administrator attestation; an empty result does not prove safety.
SELECT role
FROM session_roles
ORDER BY role;

SELECT role, privilege, admin_option
FROM role_sys_privs
WHERE role IN (SELECT role FROM session_roles)
ORDER BY role, privilege;

SELECT role, owner, table_name, column_name, privilege, grantable
FROM role_tab_privs
WHERE role IN (SELECT role FROM session_roles)
ORDER BY role, owner, table_name, column_name, privilege;

SELECT owner, table_name, privilege, grantable
FROM user_tab_privs_recd
ORDER BY owner, table_name, privilege;

SELECT owner, table_name, column_name, privilege, grantable
FROM user_col_privs_recd
ORDER BY owner, table_name, column_name, privilege;

SELECT grantee, table_schema, table_name, privilege, grantable
FROM all_tab_privs
WHERE grantee = 'PUBLIC' AND table_schema = 'HACKATON'
ORDER BY table_name, privilege;

-- Object owners can change their own objects without explicit write grants.
SELECT object_type, COUNT(*) AS owned_object_count
FROM user_objects
GROUP BY object_type
ORDER BY object_type;

-- A1-04: Confirm the accessible tables; NUM_ROWS is only a statistic.
SELECT owner, table_name, num_rows, last_analyzed
FROM all_tables
WHERE owner = 'HACKATON'
  AND table_name IN (
      'MACHINE_LINES', 'SNO_BOOKINGS_WP', 'SNO_MEASUREMENT_DATA', 'WORKORDERS'
  )
ORDER BY table_name;

-- A1-05: Exact counts, independent of Oracle's NUM_ROWS statistics.
SELECT COUNT(*) AS measurement_count FROM HACKATON.SNO_MEASUREMENT_DATA;
SELECT COUNT(*) AS machine_line_count FROM HACKATON.MACHINE_LINES;
SELECT COUNT(*) AS booking_count FROM HACKATON.SNO_BOOKINGS_WP;
SELECT COUNT(*) AS workorder_count FROM HACKATON.WORKORDERS;

-- A1-06: This inventory must precede field-specific profiling.
SELECT owner, table_name, column_id, column_name, data_type,
       data_length, data_precision, data_scale, nullable
FROM all_tab_columns
WHERE owner = 'HACKATON'
  AND table_name IN (
      'MACHINE_LINES', 'SNO_BOOKINGS_WP', 'SNO_MEASUREMENT_DATA', 'WORKORDERS'
  )
ORDER BY table_name, column_id;

-- A1-07: Declared constraints are candidates for later validation, not proof
-- of event identity. Inspect columns without assuming similarly named joins.
SELECT c.table_name, c.constraint_name, c.constraint_type, c.status,
       c.validated, cc.column_name, cc.position
FROM all_constraints c
JOIN all_cons_columns cc
  ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name
WHERE c.owner = 'HACKATON'
  AND c.table_name IN (
      'MACHINE_LINES', 'SNO_BOOKINGS_WP', 'SNO_MEASUREMENT_DATA', 'WORKORDERS'
  )
ORDER BY c.table_name, c.constraint_name, cc.position;

-- A1-08: Exact population and source coverage. Timestamp formatting retains
-- the verified six fractional digits and deliberately has no timezone suffix.
SELECT COUNT(*) AS measurement_count,
       COUNT(DISTINCT STATION_NUMBER) AS distinct_stations,
       COUNT(DISTINCT SERIAL_NUMBER) AS distinct_serials,
       COUNT(DISTINCT MEASURE_NAME) AS distinct_measurement_names,
       COUNT(*) - COUNT(BOOK_STAMP) AS missing_source_timestamps,
       TO_CHAR(MIN(BOOK_STAMP), 'YYYY-MM-DD"T"HH24:MI:SS.FF6') AS first_book_stamp,
       TO_CHAR(MAX(BOOK_STAMP), 'YYYY-MM-DD"T"HH24:MI:SS.FF6') AS last_book_stamp
FROM HACKATON.SNO_MEASUREMENT_DATA;

-- A1-09: Station/serial distributions. These scopes do not define incidents.
SELECT STATION_NUMBER, COUNT(*) AS record_count,
       COUNT(DISTINCT SERIAL_NUMBER) AS distinct_serials,
       MIN(BOOK_STAMP) AS first_book_stamp, MAX(BOOK_STAMP) AS last_book_stamp
FROM HACKATON.SNO_MEASUREMENT_DATA
GROUP BY STATION_NUMBER
ORDER BY STATION_NUMBER;

SELECT SERIAL_NUMBER, COUNT(*) AS record_count,
       COUNT(DISTINCT STATION_NUMBER) AS distinct_stations
FROM HACKATON.SNO_MEASUREMENT_DATA
GROUP BY SERIAL_NUMBER
ORDER BY SERIAL_NUMBER;

-- A1-10: Preserve recorded unit spellings, including null/whitespace groups.
SELECT UNIT, COUNT(*) AS record_count
FROM HACKATON.SNO_MEASUREMENT_DATA
GROUP BY UNIT
ORDER BY UNIT NULLS FIRST;

SELECT MEASURE_NAME, COUNT(*) AS record_count,
       COUNT(DISTINCT UNIT) AS distinct_recorded_units,
       COUNT(*) - COUNT(UNIT) AS null_unit_count
FROM HACKATON.SNO_MEASUREMENT_DATA
GROUP BY MEASURE_NAME
HAVING COUNT(DISTINCT UNIT) > 1 OR COUNT(*) > COUNT(UNIT)
ORDER BY MEASURE_NAME;

-- A1-11: Fail codes are NUMBER(10,0), nullable. Do not label a group PASS/FAIL.
SELECT MEASURE_FAIL_CODE, COUNT(*) AS record_count
FROM HACKATON.SNO_MEASUREMENT_DATA
GROUP BY MEASURE_FAIL_CODE
ORDER BY MEASURE_FAIL_CODE NULLS FIRST;

-- A1-12: Profile provisional numeric grammar without converting values.
-- Raw text remains in the source. Normalization here trims surrounding
-- whitespace for classification only. Exponents and comma/group separators
-- are outside the provisional grammar and require review if observed.
WITH numeric_fields AS (
    SELECT field_name, raw_text
    FROM HACKATON.SNO_MEASUREMENT_DATA
    UNPIVOT INCLUDE NULLS (
        raw_text FOR field_name IN (
            MEASURE_VALUE AS 'MEASURE_VALUE',
            LOWER_LIMIT AS 'LOWER_LIMIT',
            UPPER_LIMIT AS 'UPPER_LIMIT'
        )
    )
), normalized AS (
    SELECT field_name,
           REGEXP_REPLACE(raw_text, '^[[:space:]]+|[[:space:]]+$') AS parsing_text
    FROM numeric_fields
)
SELECT field_name, COUNT(*) AS record_count,
       COUNT(CASE WHEN parsing_text IS NULL THEN 1 END) AS missing_count,
       COUNT(CASE WHEN REGEXP_LIKE(
           parsing_text, '^[+-]?[0-9]+([.][0-9]+)?$', 'c'
       ) THEN 1 END) AS decimal_text_count,
       COUNT(CASE WHEN parsing_text IS NOT NULL AND NOT REGEXP_LIKE(
           parsing_text, '^[+-]?[0-9]+([.][0-9]+)?$', 'c'
       ) THEN 1 END) AS invalid_text_count
FROM normalized
GROUP BY field_name
ORDER BY field_name;

-- A1-13: Missing bound combinations and units. This is a presence profile;
-- grammar validity is counted separately in A1-12 and arithmetic belongs to A3.
WITH normalized AS (
    SELECT REGEXP_REPLACE(LOWER_LIMIT, '^[[:space:]]+|[[:space:]]+$') AS lower_text,
           REGEXP_REPLACE(UPPER_LIMIT, '^[[:space:]]+|[[:space:]]+$') AS upper_text,
           REGEXP_REPLACE(UNIT, '^[[:space:]]+|[[:space:]]+$') AS unit_text
    FROM HACKATON.SNO_MEASUREMENT_DATA
)
SELECT COUNT(*) AS record_count,
       COUNT(CASE WHEN lower_text IS NULL AND upper_text IS NULL
             THEN 1 END) AS both_bounds_missing,
       COUNT(CASE WHEN lower_text IS NOT NULL AND upper_text IS NULL
             THEN 1 END) AS lower_only_present,
       COUNT(CASE WHEN lower_text IS NULL AND upper_text IS NOT NULL
             THEN 1 END) AS upper_only_present,
       COUNT(CASE WHEN lower_text IS NOT NULL AND upper_text IS NOT NULL
             THEN 1 END) AS both_bounds_present,
       COUNT(CASE WHEN unit_text IS NULL THEN 1 END) AS unit_missing
FROM normalized;

-- A1-14: Test a scope locator separately from an extended candidate locator.
-- Even a zero duplicate count in this dataset does not establish a durable key.
WITH multiplicities AS (
    SELECT COUNT(*) OVER (
               PARTITION BY STATION_NUMBER, SERIAL_NUMBER, BOOK_STAMP
           ) AS scope_multiplicity,
           COUNT(*) OVER (
               PARTITION BY STATION_NUMBER, SERIAL_NUMBER, BOOK_STAMP,
                            MEASURE_STEP_NUMBER, MEASURE_NAME,
                            PART_NUMBER, WORKORDER_NUMBER
           ) AS candidate_multiplicity
    FROM HACKATON.SNO_MEASUREMENT_DATA
)
SELECT COUNT(*) AS record_count,
       COUNT(CASE WHEN scope_multiplicity > 1 THEN 1 END)
           AS rows_with_repeated_scope,
       COUNT(CASE WHEN candidate_multiplicity > 1 THEN 1 END)
           AS rows_with_repeated_candidate
FROM multiplicities;

-- A1-15: Full-row duplication check over the 23 verified columns.
-- Only aggregate counts leave this query; duplicate observations stay separate.
WITH multiplicities AS (
    SELECT COUNT(*) OVER (
        PARTITION BY STATION_ID, STATION_NUMBER, STATION_DESC,
                     PART_NUMBER, PART_DESC, WORKORDER_NUMBER, WORKORDER_DESC,
                     SERIAL_NUMBER, MEASURE_STEP_NUMBER, MEASURE_NAME, UNIT,
                     MEASURE_VALUE, LOWER_LIMIT, UPPER_LIMIT, NOMINAL, TOLERANCE,
                     MEASURE_FAIL_CODE, BOOK_STAMP, MEASURE_TYPE,
                     LOWER_INTERVENTION_LIMIT, UPPER_INTERVENTION_LIMIT,
                     LOWER_SCRAP_LIMIT, UPPER_SCRAP_LIMIT
    ) AS row_multiplicity
    FROM HACKATON.SNO_MEASUREMENT_DATA
)
SELECT COUNT(*) AS record_count,
       COUNT(CASE WHEN row_multiplicity > 1 THEN 1 END) AS rows_in_duplicate_groups
FROM multiplicities;

-- A4 prepared SELECTs. These comment blocks are executable query templates for
-- the temporary A4 verifier / a parameter-capable restricted SQL client.
-- Keeping them commented preserves @data-baseline.sql's existing A1 procedure;
-- bind values are supplied separately, never by textual substitution or EXEC.
-- All raw fields stay local. No Oracle numeric coercion is used: D independently
-- computes Decimal expectations from these raw SELECT results under D04/D09.
-- Each query orders before its bound cap. Counts/multiplicity describe the
-- queried scope, not a durable key. ROWID is a temporary capture locator only.

/* A4-01
SELECT m.STATION_NUMBER AS station_number, m.SERIAL_NUMBER AS serial_number,
       m.MEASURE_NAME AS measurement, m.MEASURE_VALUE AS raw_value,
       m.LOWER_LIMIT AS raw_lower, m.UPPER_LIMIT AS raw_upper, m.UNIT AS unit,
       m.MEASURE_FAIL_CODE AS raw_fail_code, m.BOOK_STAMP AS book_stamp,
       m.PART_NUMBER AS part_number, m.WORKORDER_NUMBER AS workorder_number,
       m.MEASURE_STEP_NUMBER AS measure_step_number, m.MEASURE_TYPE AS measure_type,
       ROWIDTOCHAR(m.ROWID) AS source_rowid,
       m.NOMINAL AS nominal, m.TOLERANCE AS tolerance,
       m.LOWER_INTERVENTION_LIMIT AS lower_intervention_limit,
       m.UPPER_INTERVENTION_LIMIT AS upper_intervention_limit,
       m.LOWER_SCRAP_LIMIT AS lower_scrap_limit,
       m.UPPER_SCRAP_LIMIT AS upper_scrap_limit,
       ROW_NUMBER() OVER (ORDER BY m.BOOK_STAMP DESC NULLS LAST, m.ROWID ASC)
           AS capture_ordinal,
       COUNT(*) OVER () AS total_matching_rows,
       COUNT(*) OVER (PARTITION BY m.STATION_NUMBER, m.SERIAL_NUMBER,
           m.BOOK_STAMP, m.MEASURE_STEP_NUMBER, m.MEASURE_NAME,
           m.PART_NUMBER, m.WORKORDER_NUMBER) AS candidate_multiplicity
FROM HACKATON.SNO_MEASUREMENT_DATA m
WHERE m.STATION_NUMBER COLLATE BINARY = :station_number
  AND (:serial_number IS NULL OR m.SERIAL_NUMBER COLLATE BINARY = :serial_number)
  AND (:from_time IS NULL OR m.BOOK_STAMP >= :from_time)
  AND (:to_time IS NULL OR m.BOOK_STAMP < :to_time)
ORDER BY m.BOOK_STAMP DESC NULLS LAST, m.ROWID ASC
FETCH FIRST :row_limit ROWS ONLY
*/

/* A4-02
SELECT m.STATION_NUMBER AS station_number, m.SERIAL_NUMBER AS serial_number,
       m.MEASURE_NAME AS measurement, m.MEASURE_VALUE AS raw_value,
       m.LOWER_LIMIT AS raw_lower, m.UPPER_LIMIT AS raw_upper, m.UNIT AS unit,
       m.MEASURE_FAIL_CODE AS raw_fail_code, m.BOOK_STAMP AS book_stamp,
       m.PART_NUMBER AS part_number, m.WORKORDER_NUMBER AS workorder_number,
       m.MEASURE_STEP_NUMBER AS measure_step_number, m.MEASURE_TYPE AS measure_type,
       ROWIDTOCHAR(m.ROWID) AS source_rowid,
       m.NOMINAL AS nominal, m.TOLERANCE AS tolerance,
       m.LOWER_INTERVENTION_LIMIT AS lower_intervention_limit,
       m.UPPER_INTERVENTION_LIMIT AS upper_intervention_limit,
       m.LOWER_SCRAP_LIMIT AS lower_scrap_limit,
       m.UPPER_SCRAP_LIMIT AS upper_scrap_limit,
       ROW_NUMBER() OVER (ORDER BY m.BOOK_STAMP DESC NULLS LAST, m.ROWID ASC)
           AS capture_ordinal,
       COUNT(*) OVER () AS total_matching_rows,
       COUNT(*) OVER (PARTITION BY m.STATION_NUMBER, m.SERIAL_NUMBER,
           m.BOOK_STAMP, m.MEASURE_STEP_NUMBER, m.MEASURE_NAME,
           m.PART_NUMBER, m.WORKORDER_NUMBER) AS candidate_multiplicity
FROM HACKATON.SNO_MEASUREMENT_DATA m
WHERE m.MEASURE_FAIL_CODE = :fail_code
  AND m.MEASURE_NAME COLLATE BINARY = :measurement
ORDER BY m.BOOK_STAMP DESC NULLS LAST, m.ROWID ASC
FETCH FIRST :row_limit ROWS ONLY
*/

/* A4-03
SELECT m.STATION_NUMBER AS station_number, m.SERIAL_NUMBER AS serial_number,
       m.MEASURE_NAME AS measurement, m.MEASURE_VALUE AS raw_value,
       m.LOWER_LIMIT AS raw_lower, m.UPPER_LIMIT AS raw_upper, m.UNIT AS unit,
       m.MEASURE_FAIL_CODE AS raw_fail_code, m.BOOK_STAMP AS book_stamp,
       m.PART_NUMBER AS part_number, m.WORKORDER_NUMBER AS workorder_number,
       m.MEASURE_STEP_NUMBER AS measure_step_number, m.MEASURE_TYPE AS measure_type,
       ROWIDTOCHAR(m.ROWID) AS source_rowid,
       m.NOMINAL AS nominal, m.TOLERANCE AS tolerance,
       m.LOWER_INTERVENTION_LIMIT AS lower_intervention_limit,
       m.UPPER_INTERVENTION_LIMIT AS upper_intervention_limit,
       m.LOWER_SCRAP_LIMIT AS lower_scrap_limit,
       m.UPPER_SCRAP_LIMIT AS upper_scrap_limit
FROM HACKATON.SNO_MEASUREMENT_DATA m
WHERE m.STATION_NUMBER COLLATE BINARY = :station_number
  AND m.SERIAL_NUMBER COLLATE BINARY = :serial_number
  AND ROWIDTOCHAR(m.ROWID) = :source_rowid
ORDER BY m.BOOK_STAMP DESC NULLS LAST, m.ROWID ASC
FETCH FIRST :row_limit ROWS ONLY
*/
