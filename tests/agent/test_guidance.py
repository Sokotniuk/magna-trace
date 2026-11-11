"""D41: likely causes and actions for out-of-range findings (deterministic table + case facts)."""

from agent import guidance
from agent.guidance import Row
from tests.agent.test_agent import FakeModel, make, say


def rows_single_event():
    # One part, one test: five different quantities above their limits; seven other parts in limits.
    bad = [Row(m, "P-1", "T1", "ABOVE", "9", "1", "8", "V", "1", "1001")
           for m in ("Weld Voltage", "Weld Time", "Cooling Flow", "Resistance", "Penetration")]
    good = [Row("Weld Voltage", f"P-{i}", f"T{i}", "WITHIN_RECORDED_BOUNDS", "5", "1", "8", "V", None, None)
            for i in range(2, 9)]
    return bad + good


def test_single_test_event_is_read_as_one_off_not_wear():
    facts, reading = guidance.pattern(rows_single_event())
    assert facts[0] == "5 of 12 captured values are outside their limits, on 1 of 8 parts, in 1 test(s)."
    assert "fail code 1001" in facts[1]
    assert "one-off event in this cycle" in reading[0] and "quarantine part P-1" in reading[1]


def test_repeated_measurement_points_to_the_station():
    rows = [Row("Clamp Force", f"P-{i}", f"T{i}", "ABOVE", "600", "450", "550", "N", "50", None) for i in range(3)]
    _, reading = guidance.pattern(rows)
    assert "points to the station" in reading[0]


def test_rules_match_by_measurement_kind_and_impossible_percentages():
    assert "electrode tips" in guidance.rule_for("Weld Voltage").above[0]
    assert "stripped" in guidance.rule_for("Motor Speed").above[0]
    row = Row("Pattern Accuracy", None, None, "ABOVE", "100.52", "97", "100", "%", "0.52", None)
    causes, fixes = guidance._causes(row)
    assert "impossible" in causes[0] and "measuring-system fault" in fixes[0]
    assert guidance.rule_for("Something Unknown") is guidance.GENERIC


def test_chat_snapshot_and_deviation_explain_cause_and_action(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "synthetic-station"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        first = say(client, headers, "open")["data"]["reply"]
        block = first.index("**Why it probably happened and what to do**")
        assert block < first.index("**Question for you:**")  # the question stays last
        assert "**SYNTHETIC Torque** 10.5 Nm (above 10.0, by 0.5 Nm)" in first and "**What to do:**" in first
        assert "not a MAGNA-approved procedure" in first and "lock out the station" in first
        assert "UNDETERMINED" in first  # the backend label is still shown as returned


def test_deviation_answer_has_cause_and_action(monkeypatch):
    model = FakeModel(("open_case", {"station_number": "synthetic-station"}),
                      ("get_evidence", {"measurement": "SYNTHETIC Torque"}))
    with make(model, monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        conv = say(client, headers, "open")["data"]["conversation_id"]
        reply = say(client, headers, "where does the torque deviation come from?", conv)["data"]["reply"]
        assert "**(CALCULATED)**" in reply and "**Why SYNTHETIC Torque is out and what to do**" in reply
        assert "Possible causes:" in reply and "**What to do:** 1." in reply
        assert "Data: out of limits on 1 of 1 parts at this station." in reply
