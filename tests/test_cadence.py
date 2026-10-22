"""No model call when nothing changed; arithmetic every cycle regardless."""

import agent


def test_second_cycle_on_same_state_skips_the_model(run_cycle, fake_planner):
    first = run_cycle()
    assert first["model_ran"] is True

    second = run_cycle()
    assert second["model_ran"] is False
    assert second["seconds"] == 0
    assert fake_planner.calls == 1
    assert "nothing the planner looks at changed" in second["quiet_reason"]


def test_repricing_still_runs_when_quiet(run_cycle, monkeypatch):
    # The small save has nothing to reprice, so stand in for the arithmetic and
    # check that a silent cycle still calls it and still sends what it returns.
    # Repricing is off by default since 6.8; this is the behaviour when it is on.
    monkeypatch.setattr(agent, "RULES_OFF", {"sell_limits"})
    monkeypatch.setattr(agent.executor, "repricing",
                        lambda state: ["price KYV-745 sunriseflowers sell 110"])
    run_cycle()
    second = run_cycle()
    assert second["model_ran"] is False
    assert "price KYV-745 sunriseflowers sell 110" in second["commands"] + second["repeats"]


def test_model_forced_after_max_quiet(run_cycle, fake_planner, monkeypatch):
    run_cycle()
    monkeypatch.setattr(agent, "MAX_QUIET", 0.0)
    second = run_cycle()
    assert second["model_ran"] is True
    assert fake_planner.calls == 2


def test_change_in_state_wakes_the_model(run_cycle, fake_planner, small_state):
    run_cycle()
    small_state["player"]["money"] = 400_000
    second = run_cycle(small_state)
    assert second["model_ran"] is True


def test_a_refusal_wakes_the_model_once(run_cycle, fake_planner):
    fake_planner.plan["actions"] = [{"type": "assign_ship", "ship_ref": "ASO-629",
                                     "station_id": "KYV-745", "role": "mine",
                                     "rationale": "test"}]
    run_cycle()                       # proposes, refused
    second = run_cycle()              # the refusal is news
    third = run_cycle()               # same refusal again: nothing new
    assert second["model_ran"] is True
    assert third["model_ran"] is False
    assert "(refused 2 cycles running)" in third["sitrep"]
