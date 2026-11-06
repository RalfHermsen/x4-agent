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


def test_sellware_sent_only_when_the_ware_changes():
    data = {}
    fresh, repeats = memory.drop_repeats(data, ["sellware KTK-861 water"])
    memory.record(data, fresh)
    assert memory.drop_repeats(data, ["sellware KTK-861 water"]) == ([], ["sellware KTK-861 water"])
    assert memory.drop_repeats(data, ["sellware KTK-861 microchips"])[0] == ["sellware KTK-861 microchips"]


def test_orders_go_before_settings_each_in_its_own_order():
    """start9g's first cycle sent 129 commands two seconds apart, settings first."""
    import agent
    commands = ["tradeware ZLR-942 water sell on", "release FIG-001", "limit ZLR-942 water sell 2000",
                "command FIG-001 FIG-000 attack", "shiprespond TRA-001 attacked flee", "raid FIG-000 X stay"]
    assert agent.orders_first(commands) == ["release FIG-001", "command FIG-001 FIG-000 attack", "raid FIG-000 X stay",
                                            "tradeware ZLR-942 water sell on", "limit ZLR-942 water sell 2000",
                                            "shiprespond TRA-001 attacked flee"]


def test_a_new_run_takes_what_the_save_cannot_tell_from_the_run_before(tmp_path):
    """tasks/plan-2026-11.md 0.2: not what the save shows, nor the marks of things done once a run."""
    before = tmp_path / "before.json"
    before.write_text(json.dumps({
        "sent_at": {"buyship": 5.0}, "logbook_seen": 9.0, "pending": [{"command": "x"}],
        "standing": {"where": {"FIG-000": ["S1", "fighter"]}, "swept": ["S1"], "raid": {"leader": "D"},
                     "once": ["turrets ZLR-942"], "sector_patrol": {"F": "S1"}}}), encoding="utf-8")
    store = tmp_path / "memory.json"
    carried = memory.carry(before, store)
    data = memory.load(store)
    assert data["sent_at"] == {"buyship": 5.0} and data["logbook_seen"] == 9.0 and data["pending"] == []
    assert data["standing"] == {"where": {"FIG-000": ["S1", "fighter"]}, "swept": ["S1"], "sector_patrol": {"F": "S1"}}
    assert set(carried) == {"sent_at", "logbook_seen", "standing.where", "standing.swept", "standing.sector_patrol"}
    assert memory.carry(tmp_path / "missing.json", store) == []


def test_a_hand_command_goes_out_and_on_record(tmp_path):
    """tasks/plan-2026-11.md 0.5: a hand command left no trace in the run's folder."""
    import hand
    runs = tmp_path / "runs"
    (runs / "20261106-100000-execute-a").mkdir(parents=True)
    (runs / "20261106-110000-execute-b").mkdir()
    outbox = tmp_path / "outbox.txt"
    log = hand.send(["release X", " raid X S go khaak "], "a test", outbox=outbox, runs=runs)
    assert outbox.read_text(encoding="utf-8") == "release X\nraid X S go khaak\n"
    assert log == runs / "20261106-110000-execute-b" / "hand.log"
    assert log.read_text(encoding="utf-8").count("# a test") == 2


def test_a_changed_rule_module_reloads_and_a_broken_one_is_kept(tmp_path, monkeypatch):
    """tasks/plan-2026-11.md 0.4: five restarts in one morning were for rule fixes."""
    import importlib
    import os
    import sys
    import agent
    path = tmp_path / "x4hot.py"
    path.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("x4hot")
    try:
        assert agent.reload_rules(("x4hot",)) == []                    # first seen
        path.write_text("VALUE = 2\n", encoding="utf-8")
        os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))
        assert agent.reload_rules(("x4hot",)) == ["reloaded x4hot.py"] and module.VALUE == 2
        path.write_text("VALUE = = 3\n", encoding="utf-8")
        os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 10))
        notes = agent.reload_rules(("x4hot",))
        assert notes[0].startswith("kept the old x4hot.py: SyntaxError") and module.VALUE == 2
    finally:
        sys.modules.pop("x4hot", None)
        agent._loaded_at.pop("x4hot", None)
