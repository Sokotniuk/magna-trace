-- Creates or resets the read-only runtime user TRACE_RO for MAGNA TRACE (architecture §4, AGENTS.md I-2).
-- Run as SYSDBA inside the Oracle container. Safe to run again: if TRACE_RO exists,
-- its password is reset and the account unlocked. The password is typed at the prompt,
-- never stored in this file. Use Latin letters and digits only, starting with a letter.

SET VERIFY OFF
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE

ALTER SESSION SET CONTAINER = FREEPDB1;

ACCEPT ro_password CHAR PROMPT 'Password for TRACE_RO: ' HIDE

DECLARE
  n NUMBER;
BEGIN
  SELECT COUNT(*) INTO n FROM dba_users WHERE username = 'TRACE_RO';
  IF n = 0 THEN
    EXECUTE IMMEDIATE 'CREATE USER trace_ro IDENTIFIED BY "&ro_password"';
    DBMS_OUTPUT.PUT_LINE('TRACE_RO created');
  ELSE
    EXECUTE IMMEDIATE 'ALTER USER trace_ro IDENTIFIED BY "&ro_password" ACCOUNT UNLOCK';
    DBMS_OUTPUT.PUT_LINE('TRACE_RO already existed: password reset, account unlocked');
  END IF;
END;
/

GRANT CREATE SESSION TO trace_ro;
GRANT SELECT ON HACKATON.MACHINE_LINES        TO trace_ro;
GRANT SELECT ON HACKATON.SNO_BOOKINGS_WP      TO trace_ro;
GRANT SELECT ON HACKATON.SNO_MEASUREMENT_DATA TO trace_ro;
GRANT SELECT ON HACKATON.WORKORDERS           TO trace_ro;

-- Log in as TRACE_RO the same way the backend does, to prove the password works.
PROMPT Logging in as TRACE_RO via localhost:1521/FREEPDB1 ...
CONNECT trace_ro/"&ro_password"@//localhost:1521/FREEPDB1

SELECT USER AS connected_as, COUNT(*) AS measurement_rows FROM HACKATON.SNO_MEASUREMENT_DATA;

EXIT
