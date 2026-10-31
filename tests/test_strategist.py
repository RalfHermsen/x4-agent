"""The strategist: a model that sets the plan the rules carry out (strategist.py)."""

import copy
import types

import strategist
import strategy

ANSWER = strategist.StrategistPlan(
    rationale="GKL-870 has nothing working for it.", horizon_hours=4,
    stations=[strategist.StationPlan(station="GKL-870",
                                     build=[strategist.BuildTarget(ware="storage_container", add=1)],
                                     miners=[strategist.MinerTarget(kind="solid", add=3)], traders_add=1)])


def _one_station() -> dict:
    return {"meta": {"playtime_s": 0.0}, "player": {},
            "assets": [{"cls": "station", "code": "GKL-870", "modules": ["storage_arg_m_container_01_macro"]}]}


def test_the_models_additions_become_the_plans_totals_from_what_stands():
    plan = strategist.to_strategy(ANSWER, _one_station())
    # One container store stands, one is added; three miners asked, one allowed.
    assert plan["stations"]["GKL-870"] == {"build": {"storage_container": 2}, "miners": {"solid": 1}, "traders": 1,
                                               "defenders": 0, "destroyers": 0}
    assert plan["horizon_hours"] == 4 and plan["rationale"].startswith("GKL-870")


def test_a_plan_adds_at_most_two_of_a_ware_and_four_at_a_station():
    answer = strategist.StrategistPlan(rationale="grow", horizon_hours=3, stations=[strategist.StationPlan(
        station="GKL-870", miners=[], traders_add=0,
        build=[strategist.BuildTarget(ware="refinedmetals", add=3), strategist.BuildTarget(ware="water", add=3),
               strategist.BuildTarget(ware="siliconwafers", add=2)])])
    plan = strategist.to_strategy(answer, _one_station())
    assert plan["stations"]["GKL-870"]["build"] == {"refinedmetals": 2, "water": 2, "siliconwafers": 0}
    assert plan["stations"]["GKL-870"]["traders"] == 0


def test_what_changed_hands_is_shown_per_game_hour_at_the_average_price():
    state = {"trades": {"since": 0.0, "until": 7200.0, "stations": {"KYV-745": {
        "water": {"sold": 1000, "sold_cr": 51000.0, "bought": 0, "bought_cr": 0.0},
        "ice": {"sold": 0, "sold_cr": 0.0, "bought": 4000, "bought_cr": 104000.0}}}}}
    lines = strategist._changed_hands(state)
    assert "over the last 2 game hours" in lines[0]
    assert "  KYV-745 ice: bought 2,000/h at 26" in lines and "  KYV-745 water: sold 500/h at 51" in lines
    assert strategist._changed_hands({}) == []


def test_a_plan_is_due_without_one_and_when_its_horizon_has_passed(small_state):
    now = small_state["meta"]["playtime_s"]
    plan = strategist.to_strategy(ANSWER, small_state)
    assert strategist.due({}, small_state)
    assert not strategist.due({"strategy": {"plan": plan, "since": now - 3600}}, small_state)
    assert strategist.due({"strategy": {"plan": plan, "since": now - 4 * 3600}}, small_state)


def test_the_report_names_stations_economics_and_blueprints(small_state):
    text = strategist.report(copy.deepcopy(small_state), {})
    assert "KYV-745" in text and "ONE MORE MODULE" in text and "BUILDABLE" in text


def test_update_stores_the_models_plan_and_a_failure_keeps_the_old(small_state, monkeypatch):
    import anthropic
    calls = []

    class Messages:
        def parse(self, **kwargs):
            calls.append(kwargs)
            usage = types.SimpleNamespace(input_tokens=1, output_tokens=2)
            return types.SimpleNamespace(parsed_output=ANSWER, stop_reason="end_turn", usage=usage)

    monkeypatch.setattr(anthropic, "Anthropic", lambda timeout: types.SimpleNamespace(messages=Messages()))
    monkeypatch.setattr(strategist, "STRATEGIST_MODEL", "claude-opus-5-5")
    monkeypatch.setattr(strategy, "STRATEGY_FILE", None)
    data = {}
    assert strategist.update(copy.deepcopy(small_state), data) == []
    assert data["strategy"]["plan"]["stations"]["GKL-870"]["traders"] == 1
    assert calls[0]["model"] == "claude-opus-5-5" and calls[0]["output_format"] is strategist.StrategistPlan
    assert strategist.update(copy.deepcopy(small_state), data) == [] and len(calls) == 1   # not due again
    assert "YOUR EARLIER PLANS" not in calls[0]["messages"][0]["content"]

    # When the horizon has passed, the plan that ends is shown with what followed it.
    due = {"strategy": {**data["strategy"], "since": -1e9}}
    assert strategist.update(copy.deepcopy(small_state), due) == [] and len(calls) == 2
    assert "YOUR EARLIER PLANS" in calls[1]["messages"][0]["content"]
    assert len(due["strategy_history"]) == 1 and "net_worth_cost" in due["strategy_history"][0]["end"]

    def fail(**kwargs):
        raise RuntimeError("down")
    monkeypatch.setattr(anthropic, "Anthropic", lambda timeout: types.SimpleNamespace(
        messages=types.SimpleNamespace(parse=fail)))
    stale = {"strategy": {**data["strategy"], "since": -1e9}}
    lines = strategist.update(copy.deepcopy(small_state), stale)
    assert lines[0].startswith("strategist call failed") and stale["strategy"]["plan"] == data["strategy"]["plan"]


def test_a_plan_file_wins_over_the_model(small_state, monkeypatch):
    monkeypatch.setattr(strategist, "STRATEGIST_MODEL", "claude-opus-5-5")
    monkeypatch.setattr(strategy, "STRATEGY_FILE", "plan.json")
    assert strategist.update(copy.deepcopy(small_state), {}) == []
