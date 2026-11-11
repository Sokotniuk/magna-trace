"""D42: the same error signature on several stations → common cause and one plan for all stations."""

from agent import patterns
from agent.patterns import Event
from tests.agent.test_agent import FakeModel, make, say


def event(station, minute, names=("A", "B", "C", "D"), status="ABOVE", code="1001"):
    rows = [{"measurement": n, "status": status, "value": "12", "lower": "0", "upper": "10", "unit": "mm",
             "deviation": "2", "code": code} for n in names]
    return Event(station, f"P-{station}", f"2026-11-09T11:{minute:02d}:00", 8, rows)


def test_same_signature_on_several_stations_is_one_pattern_with_a_rhythm():
    events = [event("ST1003", 0), event("ST2003", 20), event("ST3003", 41), event("ST4004", 59, names=("X", "Y", "Z"))]
    found = patterns.find_patterns(events)
    assert len(found) == 1
    p = found[0]
    assert p["stations"] == ["ST1003", "ST2003", "ST3003", "ST4004"] and p["lines"] == ["ST1", "ST2", "ST3", "ST4"]
    assert p["gaps_min"] == [20.0, 21.0, 18.0] and p["regular"] and p["single_test_each"]
    assert p["overshoot_pct"] == (20.0, 20.0)  # deviation 2 of a 10-wide band, by hand


def test_local_or_different_signatures_are_not_a_pattern():
    assert patterns.find_patterns([event("ST1003", 0), event("ST1003", 10)]) == []
    assert patterns.find_patterns([event("ST1003", 0), event("ST2003", 5, status="BELOW")]) == []
    assert patterns.find_patterns([event("ST1003", 0, code="1001"), event("ST2003", 5, code="2002")]) == []


def test_rendered_plan_fixes_once_for_all_stations():
    text = patterns.render(patterns.find_patterns([event("ST1003", 0), event("ST2003", 20), event("ST3003", 41)]))
    assert "**Cross-station pattern — 3 stations, 3 events**" in text
    assert "| 2026-11-09T11:00:00 | ST1003 | P-ST1003 | 4: A, B, C, D (1 of 8 tests) | 1001 |" in text
    assert "Minutes between consecutive events: 20, 21." in text
    assert "it is not wear of each station" in text and "shared supply" in text
    assert "1. Open ONE incident for all affected stations (ST1003, ST2003, ST3003)" in text
    assert "Fix the common cause once, centrally" in text and "Verify on all stations at once" in text
    assert "TRACE cannot change machines" in text
    assert "no error signature repeats" in patterns.render([])


def test_chat_tool_runs_on_the_synthetic_source(monkeypatch):
    with make(FakeModel(("analyze_patterns", {})), monkeypatch)[0] as client:
        headers = {"X-API-Key": client.app.state.settings.api_key}
        data = say(client, headers, "Does this error happen on other stations?")["data"]
        assert data["tool_calls"][0] == {"name": "analyze_patterns", "status": "ok", "code": None, "request_id": None}
        assert "no error signature repeats on more than one station" in data["reply"]  # one synthetic station
        route = client.get("/api/v1/analysis/patterns", headers=headers).json()
        assert route["status"] == "ok" and route["data"]["patterns"] == []


def test_a_long_pause_splits_the_pattern_into_waves():
    # 0, 20, 41 min on lines 1-3, then a 2-hour pause, then 160 and 184 min on line 4 (as in the live data).
    evs = [event("ST1003", 0), event("ST2003", 20), event("ST3003", 41)]
    evs += [Event("ST4004", "P-4", "2026-11-09T13:40:00", 8, evs[0].rows), Event("ST4003", "P-5", "2026-11-09T14:04:00", 8, evs[0].rows)]
    p = patterns.find_patterns(evs)[0]
    bursts = patterns.waves(p)
    assert [len(w["events"]) for w in bursts] == [3, 2]
    assert patterns.wave_text(bursts[0]) == "11:00–11:41: ST1003 → ST2003 → ST3003, every 20–21 min"
    assert patterns.wave_text(bursts[1]) == "13:40–14:04: ST4004 → ST4003, every 24 min"
    assert "It came in 2 waves" in patterns.render([p])
