"""Cross-station error patterns and one action plan for all affected stations (decision D42).

An "event" is one test (station, part, timestamp) with values outside their recorded limits. Events
with the same signature (direction, several quantities at once, same fail codes) on two or more
stations form a pattern. The pattern is described with facts (stations, lines, times, intervals,
overshoot), read with fixed rules, and turned into one fleet action plan: find and fix the common
cause once, centrally, then verify every station.

TRACE is read-only: it cannot change machines or settings. "Fix on all stations at once" therefore
means one incident and one plan covering every station, not a remote command.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Request

from backend.app import schemas as s

from . import guidance

CACHE_SECONDS = 60
DISCLAIMER = ("Note: rule-based analysis of the recorded data (D42), not a MAGNA-approved procedure; the common cause "
              "is not confirmed. TRACE cannot change machines: the plan is carried out by maintenance under plant "
              "safety rules (lockout before touching a station).")


@dataclass
class Event:
    station: str
    serial: str | None
    stamp: str
    tests_at_station: int
    rows: list[dict] = field(default_factory=list)  # out-of-range rows of this test

    @property
    def direction(self) -> str:
        return "/".join(sorted({r["status"] for r in self.rows}))

    @property
    def codes(self) -> str:
        return ",".join(sorted({r["code"] for r in self.rows if r["code"]})) or "none"

    @property
    def signature(self) -> tuple:
        return (self.direction, "multi" if len(self.rows) >= 3 else "single", self.codes)


def _time(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp.replace(" ", "T"))
    except (ValueError, AttributeError):
        return None


def _overshoot(row: dict) -> float | None:
    try:
        band = Decimal(row["upper"]) - Decimal(row["lower"])
        return float(Decimal(row["deviation"]) / band * 100) if band > 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def collect_events(source, row_limit: int) -> list[Event]:
    events: list[Event] = []
    for station in source.list_stations(None, 100).stations:
        batch = source.fetch_measurements(s.OpenCaseRequest(station_number=station.station_number), limit=row_limit)
        tests: dict[tuple, list] = defaultdict(list)
        for row in batch.rows:
            raw = row.raw_fields
            tests[(raw.serial_number, raw.BOOK_STAMP)].append(row)
        for (serial, stamp), rows in tests.items():
            out = [r for r in rows if r.calculation.range_status in ("ABOVE", "BELOW")]
            if not out:
                continue
            events.append(Event(station.station_number, serial, str(stamp), len(tests), [{
                "measurement": r.measurement, "status": r.calculation.range_status,
                "value": r.raw_fields.MEASURE_VALUE, "lower": r.raw_fields.LOWER_LIMIT, "upper": r.raw_fields.UPPER_LIMIT,
                "unit": r.raw_fields.UNIT, "deviation": None if r.calculation.deviation is None else str(r.calculation.deviation),
                "code": None if r.raw_fields.MEASURE_FAIL_CODE is None else str(r.raw_fields.MEASURE_FAIL_CODE),
            } for r in out]))
    return sorted(events, key=lambda e: e.stamp)


def find_patterns(events: list[Event]) -> list[dict]:
    groups: dict[tuple, list[Event]] = defaultdict(list)
    for event in events:
        groups[event.signature].append(event)
    patterns = []
    for signature, group in groups.items():
        stations = sorted({e.station for e in group})
        if len(stations) < 2:
            continue
        times = [t for t in (_time(e.stamp) for e in group) if t]
        gaps = [round((b - a).total_seconds() / 60, 1) for a, b in zip(times, times[1:])]
        overs = [o for e in group for o in (_overshoot(r) for r in e.rows) if o is not None]
        lines = sorted({st[:3] for st in stations})
        patterns.append({
            "signature": {"direction": signature[0], "shape": signature[1], "fail_codes": signature[2]},
            "stations": stations, "lines": lines, "events": group, "gaps_min": gaps,
            "overshoot_pct": (round(min(overs), 1), round(max(overs), 1)) if overs else None,
            "simultaneous": bool(gaps) and min(gaps) <= 2,
            "regular": len(gaps) >= 2 and statistics.median(gaps) > 0 and
                       statistics.pstdev(gaps) / statistics.median(gaps) < 0.6,
            "single_test_each": all(sum(1 for x in group if x.station == st) == 1 for st in stations),
        })
    return sorted(patterns, key=lambda p: -len(p["stations"]))


def waves(p: dict) -> list[dict]:
    """Consecutive events split where a gap is over three times the median gap (a pause between bursts)."""
    events, gaps = p["events"], p["gaps_min"]
    if not gaps:
        return [{"events": events, "gaps": []}]
    cut = 3 * statistics.median(gaps)
    out, current, current_gaps = [], [events[0]], []
    for event, gap in zip(events[1:], gaps):
        if gap > cut:
            out.append({"events": current, "gaps": current_gaps})
            current, current_gaps = [event], []
        else:
            current.append(event)
            current_gaps.append(gap)
    out.append({"events": current, "gaps": current_gaps})
    return out


def wave_text(w: dict) -> str:
    first, last = w["events"][0].stamp[11:16], w["events"][-1].stamp[11:16]
    route = " → ".join(e.station for e in w["events"])
    lo, hi = (min(w["gaps"]), max(w["gaps"])) if w["gaps"] else (0, 0)
    rhythm = "" if not w["gaps"] else f", every {lo:g} min" if lo == hi else f", every {lo:g}–{hi:g} min"
    return f"{first}–{last}: {route}{rhythm}"


def reading(p: dict) -> list[str]:
    quantities = {r["measurement"] for e in p["events"] for r in e.rows}
    out = [f"The same error signature appears on {len(p['stations'])} stations on {len(p['lines'])} lines: "
           f"each time {'several quantities of one test' if p['signature']['shape'] == 'multi' else 'one quantity'} "
           f"went {p['signature']['direction'].lower()} together, with fail code {p['signature']['fail_codes']}."]
    if p["single_test_each"]:
        out.append("On every station it hit exactly one test while the tests before and after were in limits, "
                   "so it is not wear of each station (wear would repeat on following parts).")
    bursts = waves(p)
    if len(bursts) > 1:
        out.append(f"It came in {len(bursts)} waves, each moving from station to station: "
                   + "; ".join(wave_text(w) for w in bursts) + ". A repeating rhythm points to something that "
                   "runs on a schedule or travels with the material, not to random faults.")
    elif p["regular"]:
        gaps = p["gaps_min"]
        out.append(f"The events follow each other at a regular rhythm (every {min(gaps):g}–{max(gaps):g} min), "
                   "moving from station to station.")
    elif p["simultaneous"]:
        out.append("Some events happened within two minutes of each other on different stations.")
    out.append(f"{len(quantities)} unrelated physical quantities (for example "
               f"{', '.join(sorted(quantities)[:4])}) left their limits in the same way "
               + (f"by {p['overshoot_pct'][0]:g}–{p['overshoot_pct'][1]:g} % of their tolerance band. " if p["overshoot_pct"] else ". ")
               + "Welding, cameras, robots and sewing do not share mechanics, so the most likely common cause sits in "
                 "what they do share: the test/measurement data path (data acquisition, MES or PLC test program, "
                 "scaling or recipe rollout), a shared supply (power, compressed air, cooling water) or a shared "
                 "part/material batch moving down the lines.")
    return out


def fleet_plan(p: dict) -> list[str]:
    stations = ", ".join(p["stations"])
    serials = ", ".join(sorted({e.serial or "?" for e in p["events"]}))
    first, last = p["events"][0].stamp, p["events"][-1].stamp
    steps = [
        f"Open ONE incident for all affected stations ({stations}) instead of {len(p['stations'])} separate repairs.",
        f"Quarantine and re-test the affected parts ({serials}). If they pass on re-test, the fault is in the measurement/data path, not in the parts.",
        f"Check shared systems for the window {first} – {last}: MES/PLC change log (test program, recipe or scaling rollout), "
        "data-acquisition gateway errors, time sync, and events of shared power, compressed air and cooling water.",
        "Fix the common cause once, centrally (for example roll back or correct the program/scaling, or repair the shared supply), "
        "then roll the corrected configuration out to every station listed above.",
        "Verify on all stations at once: run one reference part per station and watch the next cycles; TRACE will flag the "
        "signature again if it returns.",
        "Only if no common cause is found: use the per-station checks below.",
    ]
    return steps


def per_station(p: dict) -> list[str]:
    lines = []
    for e in p["events"]:
        first = e.rows[0]
        rule = guidance.rule_for(first["measurement"])
        fixes = rule.fix_above if first["status"] == "ABOVE" else rule.fix_below
        fixes = (fixes,) if isinstance(fixes, str) else fixes
        names = ", ".join(r["measurement"] for r in e.rows)
        lines.append(f"- **{e.station}** (part {e.serial}, {e.stamp}): {names}. Check: {fixes[0]}.")
    return lines


def render(patterns: list[dict]) -> str:
    if not patterns:
        return ("**Cross-station analysis:** no error signature repeats on more than one station in the recorded data. "
                "Each out-of-range event is local to its station.")
    p = patterns[0]
    lines = [f"**Cross-station pattern — {len(p['stations'])} stations, {len(p['events'])} events**", "",
             "| Time | Station | Part | Values out of limits | Fail code |", "|---|---|---|---|---|"]
    for e in p["events"]:
        tests = f" (1 of {e.tests_at_station} tests)" if e.tests_at_station else ""
        lines.append(f"| {e.stamp} | {e.station} | {e.serial} | {len(e.rows)}: "
                     f"{', '.join(r['measurement'] for r in e.rows)}{tests} | {e.codes} |")
    if p["gaps_min"]:
        lines += ["", "Minutes between consecutive events: " + ", ".join(f"{g:g}" for g in p["gaps_min"]) + "."]
    lines += ["", "**Why it probably happens:**"] + [f"- {r}" for r in reading(p)]
    lines += ["", "**Fix it on all stations at once — fleet action plan:**"]
    lines += [f"{i}. {step}" for i, step in enumerate(fleet_plan(p), 1)]
    lines += ["", "**Per-station fallback checks:**"] + per_station(p)
    if len(patterns) > 1:
        lines += ["", f"{len(patterns) - 1} smaller pattern(s) also found; ask again after fixing this one."]
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


class PatternAnalyzer:
    """Shared, cached analysis for the chat tool, the dashboard route and the case hint."""

    def __init__(self, row_limit: int) -> None:
        self.row_limit = row_limit
        self._lock = threading.Lock()
        self._at = 0.0
        self._patterns: list[dict] = []

    def patterns(self, source) -> list[dict]:
        with self._lock:
            if time.monotonic() - self._at > CACHE_SECONDS:
                self._patterns = find_patterns(collect_events(source, self.row_limit))
                self._at = time.monotonic()
            return self._patterns

    def hint_for(self, source, station: str) -> str:
        try:
            pattern = next((p for p in self.patterns(source) if station in p["stations"]), None)
        except Exception:
            return ""
        if pattern is None:
            return ""
        others = [st for st in pattern["stations"] if st != station]
        return (f"\n\n**Same error on other stations:** this signature also appears on {', '.join(others)}. "
                f"Ask \"Analyze error patterns across all stations\" for the common cause and one plan for all of them.")


def summary(p: dict) -> dict:
    """JSON-safe summary for the dashboard."""
    return {"stations": p["stations"], "lines": p["lines"], "events": len(p["events"]),
            "first": p["events"][0].stamp, "last": p["events"][-1].stamp, "gaps_min": p["gaps_min"],
            "signature": p["signature"], "regular": p["regular"], "single_test_each": p["single_test_each"],
            "waves": [wave_text(w) for w in waves(p)]}


def make_patterns_router(authenticate):
    # Request must be a module-level name: annotations are strings here (__future__).
    from backend.app.cases import utc_now
    from backend.app.source import Failure, translate_source_exception

    router = APIRouter(prefix="/api/v1")

    @router.get("/analysis/patterns", operation_id="analysis_patterns")
    def analysis(request: Request):
        authenticate(request)
        try:
            found = request.app.state.patterns.patterns(request.app.state.source)
        except Failure:
            raise
        except Exception as error:
            raise translate_source_exception(error) from None
        return {"request_id": request.scope["b_request_id"], "retrieved_at": utc_now().isoformat(),
                "status": "ok", "case_id": None, "error": None,
                "data": {"patterns": [summary(p) for p in found], "note": DISCLAIMER}}

    return router
