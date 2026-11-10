"""Case-local evidence ledger (architecture §5, AGENTS.md §7.3).

Evidence is an immutable captured snapshot. get() never re-queries Oracle.
IDs look like E-<case short id>-<sequence>, e.g. E-7F2A9C-003, and are issued only here.
"""

import json
import re
from dataclasses import dataclass

from .schemas import normalize_id

EVIDENCE_CLASSES = {"OBSERVED", "CALCULATED", "TECHNICIAN_REPORTED", "HYPOTHESIS", "UNKNOWN"}
_ID = re.compile(r"^E-([0-9A-F]{6})-(\d{3,})$")


class EvidenceNotFound(Exception):
    pass


class EvidenceNotInCase(Exception):
    pass


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    evidence_class: str
    content_json: str  # frozen copy; decoded on read so callers cannot mutate stored evidence

    def as_dict(self) -> dict:
        return {"evidence_id": self.evidence_id, "evidence_class": self.evidence_class,
                **json.loads(self.content_json)}


class EvidenceLedger:
    def __init__(self, case_short: str):
        self._short = case_short
        self._seq = 0
        self._items: dict[str, Evidence] = {}

    def add(self, evidence_class: str, content: dict) -> str:
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"Unknown evidence class {evidence_class}")
        self._seq += 1
        evidence_id = f"E-{self._short}-{self._seq:03d}"
        self._items[evidence_id] = Evidence(evidence_id, evidence_class,
                                            json.dumps(content, ensure_ascii=False, sort_keys=True))
        return evidence_id

    def get(self, evidence_id: str) -> dict:
        key = normalize_id(evidence_id)
        item = self._items.get(key)
        if item:
            return item.as_dict()
        match = _ID.match(key)
        if match and match.group(1) != self._short:
            raise EvidenceNotInCase(evidence_id)
        raise EvidenceNotFound(evidence_id)

    def __len__(self) -> int:
        return len(self._items)
