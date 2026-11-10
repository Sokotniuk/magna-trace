"""In-memory diagnostic cases (architecture §5, AGENTS.md §7.4).

One backend worker only. After a restart every old case_id returns CASE_NOT_FOUND_OR_EXPIRED:
the server cannot know whether an ID ever existed, so it does not pretend to.
"""

import secrets
import threading
import time
from dataclasses import dataclass, field

from .evidence import EvidenceLedger
from .schemas import normalize_id

STATES = ("OPENED", "EVIDENCE_LOADED", "NO_DATA", "SOURCE_ERROR", "AWAITING_CLARIFICATION",
          "ANSWER_RECORDED", "NEXT_CHECK_OR_ESCALATE", "HANDOVER_READY")


class CaseNotFound(Exception):
    pass


@dataclass
class Case:
    case_id: str
    short: str
    scope: dict
    created_at: str
    ledger: EvidenceLedger
    state: str = "OPENED"
    snapshot: dict | None = None
    open_question: dict | None = None
    answers: list = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    last_access: float = field(default_factory=time.monotonic, repr=False)


class CaseStore:
    def __init__(self, max_cases: int = 200, ttl_seconds: int = 8 * 3600):
        self._cases: dict[str, Case] = {}
        self._lock = threading.Lock()
        self._max = max_cases
        self._ttl = ttl_seconds

    def create(self, scope: dict, created_at: str) -> Case:
        with self._lock:
            self._purge()
            if len(self._cases) >= self._max:  # drop the least recently used case
                oldest = min(self._cases.values(), key=lambda c: c.last_access)
                del self._cases[oldest.case_id]
            token = secrets.token_hex(8).upper()  # 64 random bits, unguessable
            case = Case(case_id=f"C-{token}", short=token[:6], scope=scope,
                        created_at=created_at, ledger=EvidenceLedger(token[:6]))
            self._cases[case.case_id] = case
            return case

    def get(self, case_id: str) -> Case:
        with self._lock:
            self._purge()
            case = self._cases.get(normalize_id(case_id))
            if case is None:
                raise CaseNotFound(case_id)
            case.last_access = time.monotonic()
            return case

    def _purge(self) -> None:
        now = time.monotonic()
        for cid in [cid for cid, c in self._cases.items() if now - c.last_access > self._ttl]:
            del self._cases[cid]


CASES = CaseStore()
