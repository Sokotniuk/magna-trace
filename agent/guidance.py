"""Troubleshooting guidance for out-of-range findings: likely causes and what to do (decision D41).

Two parts, both deterministic (no model text):
1. Facts from the case itself: how many parts and measurements are affected, whether it is a single
   test or a repeated pattern. Computed from the captured evidence of the case.
2. A fixed troubleshooting table: typical causes and actions per kind of measurement, written by the
   team from general production-engineering knowledge. It is NOT a MAGNA-approved procedure; every
   block says so, and safety rules (lockout before touching the station) come first.

D41 deliberately relaxes the original product rule "no causes, no repair advice" for the hackathon
demo, at the team's request. The backend assessment label itself stays as returned.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable

DISCLAIMER = ("Note: TRACE troubleshooting rules (general engineering knowledge, not a MAGNA-approved procedure). "
              "The cause is not confirmed. Follow plant safety rules — lock out the station before touching it — "
              "and confirm the fix with the maintenance procedure.")


@dataclass(frozen=True)
class Rule:
    pattern: str          # regex on the lower-case measurement name
    above: tuple[str, ...]  # likely causes when the value is above the upper limit
    below: tuple[str, ...]  # likely causes when the value is below the lower limit
    fix_above: tuple[str, ...]
    fix_below: tuple[str, ...]


# Specific measurements first, generic physical quantities last. First match wins.
RULES: tuple[Rule, ...] = (
    # --- resistance spot welding (ST1002/ST1003) ---
    Rule(r"weld voltage",
         ("worn, mushroomed or contaminated electrode tips raise the contact resistance",
          "loose or damaged secondary cable, shunt or clamp connection",
          "wrong weld program for this part, or a coated/thicker sheet"),
         ("electrode tips misaligned or shunting through a neighbouring weld", "secondary circuit partly short-circuited"),
         ("dress the electrode tips (replace them if dressing does not restore the contact face)",
          "check and tighten the secondary cables and connections; look for heat discoloration",
          "verify that the weld program number matches the part variant"),
         ("check tip alignment and the distance to the previous weld", "inspect the secondary circuit for shunts")),
    Rule(r"weld time",
         ("the adaptive controller extended the weld because current did not build up (tip wear, poor contact)",
          "wrong weld program or stepper count", "low weld current"),
         ("program with a shorter schedule selected", "weld interrupted (part moved, low force)"),
         ("read the weld controller log for this weld: program, stepper count and adaptive correction",
          "dress or replace the tips, then check that weld current reaches its setpoint"),
         ("verify the program number", "check electrode force and part clamping")),
    Rule(r"weld current",
         ("program set too high or stepper over-compensating worn tips", "lower resistance path (shunt)"),
         ("worn tips or high resistance in the secondary circuit", "transformer or controller fault"),
         ("verify the program setpoint and stepper status; reset the stepper after tip dressing",),
         ("dress tips and check the secondary circuit; check the controller fault log",)),
    Rule(r"weld energy|cycle energy|^energy",
         ("more heat or work than needed: higher current or longer time, extra friction or a jam",),
         ("not enough heat or work: low current, short time, missing part"),
         ("check the parameters that make up the energy (current, voltage, time or force) and fix the one that is high",),
         ("check that the part is present and the program is complete",)),
    Rule(r"cooling flow",
         ("flow regulator opened or adjusted", "flow sensor out of calibration", "leak after the sensor (burst hose, worn cap)"),
         ("clogged filter or hose, kinked hose", "cooling pump or chiller problem", "worn or missing water tube in the electrode cap"),
         ("check the regulator setting and the flow sensor", "inspect hoses and electrode caps for leaks"),
         ("clean the filter, check hoses for kinks, check the chiller", "check the water tubes in the electrode holders")),
    Rule(r"^resistance$|contact resistance",
         ("worn or contaminated electrode tips / contacts", "too low electrode force", "oxide, oil or coating on the part surface",
          "poor fit-up between the sheets"),
         ("tips freshly dressed with a larger face", "electrode force too high"),
         ("dress or replace the tips/contacts", "check electrode force and the air pressure of the cylinder",
          "check part cleanliness and fit-up"),
         ("check electrode force setting", "verify tip geometry")),
    Rule(r"penetration",
         ("too much heat input (high current or long time)", "thinner material than specified", "small worn tip face concentrates current"),
         ("not enough heat input", "worn tips with a large face", "thicker or coated material"),
         ("check current and weld time against the program; dress the tips", "verify sheet thickness of the part"),
         ("check current, time and tip condition", "verify material")),
    Rule(r"electrode force",
         ("pressure regulator set too high", "servo gun calibration"),
         ("low air pressure, leaking cylinder, sticky guide", "servo gun calibration"),
         ("check the regulator and gun calibration",), ("check air supply, cylinder and guides",)),
    Rule(r"tip temp",
         ("insufficient cooling (flow low, blocked water tube)", "high weld rate or current"),
         ("sensor fault",), ("check cooling flow and electrode water tubes",), ("check the sensor",)),
    # --- vision / inspection (ST1004, ST2004, ST3005, ST4005) ---
    Rule(r"brightness|contrast|display brightness",
         ("lighting intensity too high or ambient light entering the cell", "camera exposure/gain changed", "shiny part surface"),
         ("lamp ageing or failure, dirty lens or light cover", "exposure too short"),
         ("check the illumination controller and shield the cell from ambient light", "verify the camera exposure in the inspection program",
          "clean the lens and the light cover"),
         ("check and replace the lamp if needed; clean optics", "verify exposure settings")),
    Rule(r"gap|flush|alignment|offset|position|contour",
         ("part not seated correctly in the fixture (dirt, worn locator pins, clamp not closed)",
          "part geometry deviates from an upstream station", "camera/robot calibration shifted"),
         ("part not seated correctly in the fixture", "part geometry deviates from an upstream station", "calibration shifted"),
         ("check the fixture: locator pins, clamps, dirt; re-run the part", "measure the part manually to confirm",
          "check the calibration with the reference part"),
         ("check the fixture and re-run the part", "measure the part manually", "check calibration")),
    Rule(r"defect|contamination|pressure mark|wrinkle",
         ("real defects on the part", "dirty optics or light creating false defects", "detection threshold too sensitive",
          "for covers: uneven tension or misplaced material"),
         ("—",),
         ("inspect the part by eye and compare with the saved image", "clean the optics", "review the threshold only with quality approval"),
         ("—",)),
    Rule(r"score|match|rating|quality|grade|verification|accuracy|consistency|presence",
         ("a percentage above 100 % is impossible: the measuring system or its software reported a wrong value",),
         ("poor part quality, dirty optics, wrong reference image or program",),
         ("treat it as a measuring-system fault: restart/verify the inspection software and re-test the part",),
         ("inspect the part, clean optics, check the reference/program")),
    # --- robot assembly and screwing (ST2003, ST3003) ---
    Rule(r"motor speed",
         ("tightening tool ran with less load than expected: screw not engaged, stripped or cross-threaded",
          "wrong tightening program or speed step", "worn bit slipping"),
         ("tool overloaded: thread too tight, burr, wrong screw", "low supply"),
         ("inspect the screw and the thread on the part", "verify the tightening program and its speed steps", "replace a worn bit"),
         ("check thread and screw part number", "check tool supply")),
    Rule(r"^angle|screw depth",
         ("screw turned further than expected: stripped thread, soft joint, missing component, wrong screw length",
          "for robots: part rotated in the fixture or encoder offset"),
         ("joint stopped early: cross-threading, burr, wrong screw",),
         ("inspect the joint and the screw part number; re-tighten on a new part", "check part orientation in the fixture"),
         ("inspect thread and screw",)),
    Rule(r"torque|assembly force|insertion force|clip force|pull force|button force|unload force|clamp force|stretch force",
         ("parts too tight (tolerance from upstream), misalignment causing a jam", "worn or dry tooling", "pressure/force setting too high"),
         ("missing or loose part, low supply pressure", "tool slipping"),
         ("check part alignment and dimensions", "inspect and lubricate the tooling", "verify the force/pressure setting"),
         ("check part presence and supply pressure", "inspect the tool")),
    Rule(r"vibration",
         ("worn bearing, loose mounting bolts, imbalance or misalignment of the spindle/tool",),
         ("sensor loose or faulty",),
         ("check mounting bolts and the tool holder; listen for bearing noise; plan a vibration check",),
         ("check sensor mounting",)),
    # --- seat covers and sewing (ST4003, ST4004) ---
    Rule(r"tension",
         ("tension device set too high", "thread/cover catching on a burr or guide", "stiffer or thicker material batch"),
         ("tension set too low, worn spring or disc", "thread slipping"),
         ("check the thread/material path for snags and burrs", "set the tension to the specification", "verify the material batch"),
         ("check tension discs/springs", "re-thread correctly")),
    Rule(r"needle temp",
         ("stitching speed too high, thick material, dull needle, needle cooler off",),
         ("sensor fault",),
         ("replace the needle, check the needle cooler and the speed setting",), ("check the sensor",)),
    Rule(r"stitch",
         ("stitch length set too short or encoder error",), ("stitch length set too long, skipped stitches",),
         ("verify the stitch-length setting and the encoder",), ("check needle, hook timing and thread",)),
    Rule(r"seat|width|length|height|thickness",
         ("part dimension from upstream too large (frame, foam, cover size)", "wrong part variant"),
         ("part dimension from upstream too small", "wrong part variant"),
         ("measure the part manually; check the upstream station and the part variant",),
         ("measure the part manually; check the upstream station and the part variant",)),
    # --- generic physical quantities ---
    Rule(r"pressure|vacuum",
         ("regulator set too high", "sensor drift"), ("air leak, clogged filter, low supply", "worn seal / suction cup"),
         ("check the regulator and the sensor",), ("check for leaks, filters and seals",)),
    Rule(r"temp", ("cooling insufficient, high load or ambient", "sensor drift"), ("heater fault", "sensor fault"),
         ("check cooling and load",), ("check heater and sensor",)),
    Rule(r"speed", ("setpoint changed or control fault",), ("drag, friction, overload or low supply",),
         ("verify the speed setpoint in the program",), ("check mechanics for friction and the drive",)),
    Rule(r"current|voltage", ("overload or setting too high",), ("supply problem or open circuit",),
         ("check the load and the setpoint",), ("check supply and connections",)),
    Rule(r"time|delay|latency|response", ("slow actuator or sensor, waiting for a signal",), ("step skipped",),
         ("check actuator, sensor and the sequence log",), ("check the sequence",)),
    Rule(r"count|level|queue", ("extra parts or a counting fault",), ("missing parts or feeding problem",),
         ("check the feeder and the counter",), ("check the feeder",)),
    Rule(r"flow|consumption", ("leak or regulator opened",), ("blockage or low supply",),
         ("check for leaks and the regulator",), ("check filters and supply",)),
    Rule(r"weight", ("extra material or wrong part variant",), ("missing component or wrong variant",),
         ("check part variant and components",), ("check part completeness",)),
)

GENERIC = Rule(r".*", ("process setting changed, part deviation or measuring fault",),
               ("process setting changed, part deviation or measuring fault",),
               ("re-test the part, verify the program, check the measuring device",),
               ("re-test the part, verify the program, check the measuring device",))


def rule_for(measurement: str) -> Rule:
    name = " ".join(measurement.lower().split())
    for rule in RULES:
        if re.search(rule.pattern, name):
            return rule
    return GENERIC


@dataclass(frozen=True)
class Row:
    measurement: str
    serial: str | None
    stamp: str | None
    status: str
    value: str | None
    lower: str | None
    upper: str | None
    unit: str | None
    deviation: str | None
    code: str | None


def case_rows(cases, case_id: str) -> list[Row]:
    """Pairs every captured observation with its calculation, from the stored case evidence."""
    try:
        with cases.locked(case_id) as case:
            items = list(case.evidence._items.values())
    except Exception:
        return []
    observed = {i.evidence_id: i for i in items if i.classification == "OBSERVED"}
    rows = []
    for calc in (i for i in items if i.classification == "CALCULATED"):
        obs = observed.get(calc.input_evidence_ids[0]) if calc.input_evidence_ids else None
        if obs is None:
            continue
        raw = obs.raw_fields
        rows.append(Row(obs.measurement, raw.serial_number, raw.BOOK_STAMP, calc.result.range_status,
                        raw.MEASURE_VALUE, raw.LOWER_LIMIT, raw.UPPER_LIMIT, raw.UNIT,
                        None if calc.result.deviation is None else str(calc.result.deviation),
                        None if raw.MEASURE_FAIL_CODE is None else str(raw.MEASURE_FAIL_CODE)))
    return rows


def _pct(value: str | None, unit: str | None) -> bool:
    try:
        return unit == "%" and value is not None and float(value) > 100
    except ValueError:
        return False


def _tuple(value: tuple[str, ...] | str) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else value


def _causes(row: Row) -> tuple[tuple[str, ...], tuple[str, ...]]:
    rule = rule_for(row.measurement)
    if _pct(row.value, row.unit):
        rule = next(r for r in RULES if r.pattern.startswith("score"))
    above = row.status == "ABOVE"
    return _tuple(rule.above if above else rule.below), _tuple(rule.fix_above if above else rule.fix_below)


def pattern(rows: list[Row]) -> tuple[list[str], list[str]]:
    """Facts about the out-of-range rows of the case and a rule-based reading of them."""
    out = [r for r in rows if r.status in ("ABOVE", "BELOW")]
    if not out:
        return [], []
    serials = {r.serial for r in rows if r.serial}
    bad_serials = Counter(r.serial for r in out)
    tests = Counter((r.serial, r.stamp) for r in out)
    measurements = {r.measurement for r in out}
    facts = [f"{len(out)} of {len(rows)} captured values are outside their limits, "
             f"on {len(bad_serials)} of {len(serials)} parts, in {len(tests)} test(s)."]
    worst_test, worst_n = tests.most_common(1)[0]
    in_test = [r for r in rows if (r.serial, r.stamp) == worst_test]
    codes = {r.code for r in in_test if r.code}
    facts.append(f"Part {worst_test[0]} at {worst_test[1]}: {worst_n} of {len(in_test)} measurements out of limits"
                 + (f"; the station recorded fail code {', '.join(sorted(codes))} on this test." if codes else "."))
    repeated = [m for m in measurements if sum(1 for r in out if r.measurement == m) > 1]
    if repeated:
        facts.append("Repeated on several parts: " + ", ".join(sorted(repeated)) + ".")

    reading = []
    if len(tests) == 1 and worst_n >= 3 and len(serials) > 1:
        reading.append(f"Several different quantities left their limits in the same test at the same moment, while the other "
                       f"{len(serials) - 1} parts were in limits. That points to a one-off event in this cycle — a defective or "
                       f"wrong part variant, a wrong program loaded, or a measuring-system glitch — rather than gradual wear "
                       f"(wear shows on several parts in a row).")
        reading.append(f"First: quarantine part {worst_test[0]} and re-test it; check which program/part variant ran at "
                       f"{worst_test[1]} and the station event log for that minute.")
    elif repeated:
        reading.append("The same measurement is out on several parts: that points to the station (setting drift, wear "
                       "or a fixture problem) rather than to single parts.")
        reading.append("First: compare the station settings with the reference and inspect the tooling named below.")
    else:
        reading.append("A single measurement is out on a single part: check that part and the related device first.")
    return facts, reading


def diagnosis_block(rows: list[Row], findings: list[dict]) -> str:
    out_findings = [f for f in findings if f.get("range_status") in ("ABOVE", "BELOW")]
    if not out_findings:
        return ""
    facts, reading = pattern(rows)
    lines = ["", "**Why it probably happened and what to do**", "", "**What the data shows:**"]
    lines += [f"- {fact}" for fact in facts]
    lines += ["", "**Most likely:**"] + [f"- {r}" for r in reading]
    lines += ["", "**Per measurement:**"]
    for f in out_findings:
        row = Row(f["measurement"], None, None, f["range_status"], f.get("raw_value"), f.get("raw_lower"),
                  f.get("raw_upper"), f.get("unit"), f.get("deviation"), f.get("raw_fail_code"))
        causes, fixes = _causes(row)
        unit = f" {row.unit}" if row.unit else ""
        side = f"above {row.upper}" if row.status == "ABOVE" else f"below {row.lower}"
        lines.append(f"- **{row.measurement}** {row.value}{unit} ({side}, by {row.deviation}{unit}) — "
                     f"possible causes: {'; '.join(causes)}. **What to do:** {'; '.join(fixes)}.")
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def measurement_block(rows: list[Row], measurement: str, status: str, value: str | None, unit: str | None,
                      lower: str | None, upper: str | None, deviation: str | None) -> str:
    if status not in ("ABOVE", "BELOW"):
        return ""
    row = Row(measurement, None, None, status, value, lower, upper, unit, deviation, None)
    causes, fixes = _causes(row)
    same = [r for r in rows if r.measurement == measurement]
    bad = [r for r in same if r.status in ("ABOVE", "BELOW")]
    lines = ["", f"**Why {measurement} is out and what to do**"]
    if same:
        lines.append(f"- Data: out of limits on {len({r.serial for r in bad})} of {len({r.serial for r in same})} parts at this station.")
    lines.append("- Possible causes: " + "; ".join(causes) + ".")
    lines.append("- **What to do:** " + "; ".join(f"{i}. {fix}" for i, fix in enumerate(fixes, 1)) + ".")
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


RowsFor = Callable[[str], list[Row]]
