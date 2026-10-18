"""The whole loop runs without a model and without touching the game."""

import json

import memory


def test_small_save_parses(small_state):
    codes = {a["code"] for a in small_state["assets"]}
    assert {"KYV-745", "ASO-629", "TJL-171"} <= codes
    assert small_state["meta"]["build"] == "611726"


def test_cycle_runs_with_fake_planner(run_cycle, fake_planner):
    result = run_cycle()
    assert fake_planner.calls == 1
    assert "KYV-745" in result["sitrep"]
    assert isinstance(result["commands"], list)


def test_memory_goes_to_the_temp_store(run_cycle, fake_planner, isolated_memory):
    fake_planner.plan["updated_goals"] = ["keep KYV-745 supplied"]
    run_cycle()
    assert memory.STORE == isolated_memory
    stored = json.loads(isolated_memory.read_text(encoding="utf-8"))
    assert stored["goals"] == ["keep KYV-745 supplied"]
