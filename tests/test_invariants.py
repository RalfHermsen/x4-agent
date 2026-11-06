"""Checks over one cycle's commands (invariants.py, tasks/plan-2026-11.md 0.1)."""

import copy

import executor
import invariants
import standing


def _with_ships(state, prefix, macro, n):
    base = next(a for a in state["assets"] if a["code"] == "ASO-629")
    for i in range(n):
        state["assets"].append(dict(copy.deepcopy(base), code=f"{prefix}-00{i}", macro=macro))


def test_many_destroyers_sent_home_at_once_are_named(small_state):
    """start9k: the guard of 30 assigned home in its first cycle."""
    state = copy.deepcopy(small_state)
    _with_ships(state, "DES", "ship_tel_l_destroyer_01_a_macro", 7)
    home = [f"assign DES-00{i} KYV-745 defend" for i in range(7)]
    found = invariants.check(state, home, [("raids", home)])
    assert len(found) == 1 and "7 destroyers sent home" in found[0]
    assert invariants.check(state, home[:5], [("raids", home[:5])]) == []


def test_one_ship_with_orders_from_two_rules_is_named(small_state):
    state = copy.deepcopy(small_state)
    _with_ships(state, "FIG", "ship_tel_s_fighter_01_a_macro", 1)
    by_rule = [("fighter_posts", ["release FIG-000", "command FIG-000 TRA-001 defence"]),
               ("fleet", ["assign FIG-000 KYV-745 defend"])]
    commands = [c for _, given in by_rule for c in given]
    assert invariants.check(state, commands, by_rule) == [
        "INVARIANT: FIG-000 has orders from fighter_posts, fleet in one cycle"]
    # One rule's own sequence is not, nor that with a setting from elsewhere.
    assert invariants.check(state, commands[:2], by_rule[:1]) == []
    assert invariants.check(state, ["shiprespond FIG-000 attacked flee", *commands[:2]], by_rule[:1]) == []


def test_a_module_asked_for_while_a_build_has_it_is_named(small_state):
    """start9f and start9g: four piers for ZXX-974."""
    state = copy.deepcopy(small_state)
    pier = executor.EXPANSION_MODULES["pier"][0]
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queue": [], "running": [{"since": 0.0, "sequence": [*station["modules"], pier]}]}
    found = invariants.check(state, ["expand KYV-745 pier"], [("docks", ["expand KYV-745 pier"])])
    assert found == [f"INVARIANT: expand KYV-745 pier while a build of KYV-745 has {pier} in it already"]
    station["modules"] = [*station["modules"], pier]
    assert invariants.check(state, ["expand KYV-745 pier"], []) == []


def test_the_standing_rules_say_which_gave_what(small_state):
    standing.commands(copy.deepcopy(small_state), {})
    assert [name for name, _ in standing.LAST_BY_RULE] == [r.__name__ for r in standing.RULES]


def test_a_cycle_names_what_the_checks_find(run_cycle, fake_planner, monkeypatch):
    monkeypatch.setattr(invariants, "check", lambda state, commands, by_rule: ["INVARIANT: test"])
    assert "INVARIANT: test" in run_cycle()["failures"]
