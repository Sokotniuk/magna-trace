"""Regression checks for contention, expiry during I/O and atomic capture."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event, RLock

import pytest

from backend.app import schemas as s
from student_b.cases import CaseStore
from student_b.source import Failure
from .test_cases_api import assert_error


class SignallingLock:
    """Signals immediately before a contender attempts to acquire the lock."""

    def __init__(self):
        self.inner = RLock()
        self.attempted = Event()

    def acquire(self, blocking=True):
        self.attempted.set()
        return self.inner.acquire(blocking=blocking)

    def release(self):
        self.inner.release()


def test_busy_case_does_not_block_another_case_or_creation(clock):
    store = CaseStore(3, 7200, clock)
    scope = s.OpenCaseRequest(station_number="SYNTHETIC-STATION")
    first, second = store.create(scope), store.create(scope)
    lock = SignallingLock()
    first.lock = lock

    def visit(case_id):
        with store.locked(case_id):
            return True

    def unrelated():
        visit(second.case_id)
        store.create(scope)
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        lock.inner.acquire()
        try:
            waiting = pool.submit(visit, first.case_id)
            assert lock.attempted.wait(2)
            independent = pool.submit(unrelated)
            assert independent.result(timeout=2)
            assert not waiting.done()
        finally:
            lock.inner.release()
        assert waiting.result(timeout=2)


def test_waiter_cannot_reuse_case_removed_after_expiry(clock):
    store = CaseStore(1, 1, clock)
    scope = s.OpenCaseRequest(station_number="SYNTHETIC-STATION")
    first = store.create(scope)
    lock = SignallingLock()
    first.lock = lock

    def visit():
        with store.locked(first.case_id):
            pytest.fail("Expired case was revived")

    with ThreadPoolExecutor(max_workers=1) as pool:
        lock.inner.acquire()
        try:
            pending = pool.submit(visit)
            assert lock.attempted.wait(2)
            clock.now = 2
            # Cleanup can acquire this thread's RLock but the waiting thread
            # still holds a reference to the removed object.
            replacement = store.create(scope)
            assert replacement.case_id != first.case_id
        finally:
            lock.inner.release()
        with pytest.raises(Failure) as error:
            pending.result(timeout=2)
        assert error.value.code == "CASE_NOT_FOUND_OR_EXPIRED"


@pytest.mark.parametrize("code,status", [("SOURCE_UNAVAILABLE", 503), ("TIMEOUT", 504)])
def test_expiry_during_failed_read_preserves_original_error(client, headers, source, clock, monkeypatch, code, status):
    def fail(scope, *, limit):
        clock.now = 7201
        raise Failure(code, "Synthetic source failure", status)

    monkeypatch.setattr(source, "fetch_measurements", fail)
    result = assert_error(client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers), code, status)
    assert_error(client.get(f"/api/v1/cases/{result['case_id']}/handover", headers=headers), "CASE_NOT_FOUND_OR_EXPIRED", 404)


def test_bad_second_row_does_not_publish_partial_evidence(app, client, headers, source):
    source.rows[1] = replace(source.rows[1], rule=None)
    result = assert_error(client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers), "SOURCE_UNAVAILABLE", 500)
    case_id = result["case_id"]
    with app.state.cases.locked(case_id) as case:
        assert case.state == "SOURCE_ERROR"
        assert case.snapshot is None and case.question_id is None
    assert_error(client.get(f"/api/v1/cases/{case_id}/evidence/E-{case_id}-1", headers=headers), "EVIDENCE_NOT_FOUND", 404)


def test_expiry_during_successful_read_does_not_resurrect_case(client, headers, source, clock, monkeypatch):
    fetch = source.fetch_measurements

    def delayed(scope, *, limit):
        batch = fetch(scope, limit=limit)
        clock.now = 7201
        return batch

    monkeypatch.setattr(source, "fetch_measurements", delayed)
    assert_error(client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers), "CASE_NOT_FOUND_OR_EXPIRED", 404)
