"""The strategist: a model that sets the plan the rules carry out (strategist.py)."""

import copy
import types

import strategist
import strategy

ANSWER = strategist.StrategistPlan(
    rationale="GKL-870 has nothing working for it.", horizon_hours=4,
    stations=[strategist.StationPlan(station="GKL-870",
                                     build=[strategist.BuildTarget(ware="storage_container", modules=1)],
                                     miners=[strategist.MinerTarget(kind="solid", count=3)], traders=1)])


def test_the_models_lists_become_the_plans_maps():
    plan = strategist.to_strategy(ANSWER)
    assert plan["stations"]["GKL-870"] == {"build": {"storage_container": 1}, "miners": {"solid": 3}, "traders": 1}
    assert plan["horizon_hours"] == 4 and plan["rationale"].startswith("GKL-870")


def test_a_plan_is_due_without_one_and_when_its_horizon_has_passed(small_state):
    now = small_state["meta"]["playtime_s"]
    plan = strategist.to_strategy(ANSWER)
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
