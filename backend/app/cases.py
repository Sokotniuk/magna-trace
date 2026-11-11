"""Bounded RAM cases with absolute TTL and one lock per case; use one worker."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, RLock
from time import monotonic
from uuid import uuid4

from backend.app import schemas as s
from .evidence import EvidenceStore
from .source import Failure


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


TRANSITIONS = {
    "OPENED": {"EVIDENCE_LOADED", "NO_DATA", "SOURCE_ERROR"},
    "EVIDENCE_LOADED": {"AWAITING_CLARIFICATION"},
    "AWAITING_CLARIFICATION": {"ANSWER_RECORDED"},
    "ANSWER_RECORDED": {"NEXT_CHECK_OR_ESCALATE"},
    "NEXT_CHECK_OR_ESCALATE": {"HANDOVER_READY"},
}


@dataclass
class Case:
    case_id: str
    scope: s.OpenCaseRequest
    expires_at: float
    evidence: EvidenceStore
    state: str = "OPENED"
    snapshot: s.Snapshot | None = None
    question_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    history: list[str] = field(default_factory=lambda: ["OPENED"])
    source_capture: object | None = field(default=None, repr=False)
    lock: RLock = field(default_factory=RLock, repr=False)

    def transition(self, target: str) -> None:
        if target not in TRANSITIONS.get(self.state, set()):
            raise RuntimeError("Invalid internal case transition")
        self.state = target
        self.updated_at = utc_now()
        self.history.append(target)


class CaseStore:
    def __init__(self, capacity: int, ttl_seconds: int, clock: Callable[[], float] = monotonic) -> None:
        self.capacity, self.ttl_seconds, self.clock = capacity, ttl_seconds, clock
        self._items: dict[str, Case] = {}
        self._guard = Lock()

    def create(self, scope: s.OpenCaseRequest) -> Case:
        with self._guard:
            for key, item in tuple(self._items.items()):
                if item.expires_at <= self.clock() and item.lock.acquire(blocking=False):
                    try:
                        del self._items[key]
                    finally:
                        item.lock.release()
            if len(self._items) >= self.capacity:
                raise Failure("INVALID_SCOPE", "Active case capacity reached; retry after expiry", 503)
            key = uuid4().hex
            item = Case(key, scope, self.clock() + self.ttl_seconds, EvidenceStore(key))
            self._items[key] = item
            return item

    @contextmanager
    def locked(self, case_id: str) -> Iterator[Case]:
        with self._guard:
            item = self._items.get(case_id)
            if item is None:
                raise Failure("CASE_NOT_FOUND_OR_EXPIRED", "Case is unavailable; open a new case", 404)
        # A busy case must not hold the registry lock and block unrelated cases.
        item.lock.acquire()
        try:
            with self._guard:
                # Expiry cleanup may have removed this object while we waited.
                if self._items.get(case_id) is not item or item.expires_at <= self.clock():
                    if self._items.get(case_id) is item:
                        del self._items[case_id]
                    raise Failure("CASE_NOT_FOUND_OR_EXPIRED", "Case is unavailable; open a new case", 404)
            yield item
        finally:
            item.lock.release()

    def mark_failed(self, case_id: str, *, no_data: bool) -> None:
        """Retain terminal state if still live; never mask the original source error."""
        try:
            with self.locked(case_id) as case:
                if case.state == "OPENED":
                    case.transition("NO_DATA" if no_data else "SOURCE_ERROR")
        except Failure as error:
            if error.code != "CASE_NOT_FOUND_OR_EXPIRED":
                raise
