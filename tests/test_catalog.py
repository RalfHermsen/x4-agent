"""The action catalog (5.3): situations, options that pass, answers read exactly."""

import copy

import action_lines
import agent
import catalog
from catalog import Option, Situation


def test_decisions_are_read_in_every_form_and_the_rest_is_reported():
    analysis = ("Thinking...\n\nDECISIONS:\nS1: 2 storage is the bottleneck\n"
                "**S2: none** not worth it\nS3 - 1: bring it home\n"
                "maybe later for S4\n\nOTHER:\n- build a storage module\n\n"
                "STANDING GOALS:\n- clear the storage\n")
    answers, unreadable = action_lines.decisions(analysis)
    assert [(n, k) for n, k, _ in answers] == [(1, 2), (2, None), (3, 1)]
    assert unreadable == ["maybe later for S4"]
    assert action_lines.other_lines(analysis) == ["build a storage module"]
    assert action_lines.goals_from(analysis) == ["clear the storage"]


def test_decide_takes_only_options_that_exist():
    found = [Situation("a", "first", [Option("x", "cmd one"), Option("y", "cmd two")]),
             Situation("b", "second", [Option("z", "cmd three")]),
             Situation("c", "third", [Option("w", "cmd four")])]
    commands, notes, counts = catalog.decide(
        found, "DECISIONS:\nS1: 2 yes\nS2: 5 too far\nS7: 1 what\n")
    assert commands == ["cmd two"]
    assert "S2 has no option 5" in notes and "S7 is not a situation in this report" in notes
    assert counts["chosen"] == 1 and counts["unanswered"] == 1


def test_render_numbers_situations_and_options():
    lines = catalog.render([Situation("a", "KYV-745 has no budget.", [Option("low", "budget KYV-745 low")])])
    assert lines[1].startswith("# SITUATIONS") and lines[2] == "S1 KYV-745 has no budget."
    assert lines[3] == "   1. low"
    assert catalog.render([]) == []


def test_the_small_start_has_a_budget_and_an_idle_freighter(small_state):
    found = {s.key: s for s in catalog.situations(small_state)}
    assert "budget:KYV-745" in found
    assert [o.command for o in found["budget:KYV-745"].options] == [
        "budget KYV-745 low", "budget KYV-745 mid", "budget KYV-745 high"]
    assert "assign ASO-629 KYV-745 trade" in [o.command for o in found["idle:ASO-629"].options]
    # The ship the player sits in is never a situation.
    assert not any("TJL-171" in s.key for s in found.values())


def test_an_explorer_on_covered_ground_is_offered_a_new_sector(small_state):
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    sector = ship["place"]["sector"]
    ship["orders"] = [{"order": "Explore", "target_sector": sector, "default": False}]
    found = {s.key: s for s in catalog.situations(state)}
    assert [o.command for o in found["explore:ASO-629"].options] == ["explore ASO-629"]


def test_a_defender_under_fire_is_left_to_its_job(small_state):
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    now = state["meta"]["playtime_s"]
    ship["attack"] = {"method": "lowattentionattack", "time": now - 60}
    ship["orders"] = [{"order": "ProtectStation", "default": False}]
    assert not any(s.key == "fire:ASO-629" for s in catalog.situations(state))


def test_a_cycle_with_the_catalog_sends_the_chosen_option(run_cycle, fake_planner, monkeypatch):
    monkeypatch.setattr(agent, "CATALOG", True)
    monkeypatch.setattr(agent.executor, "repricing", lambda state: [])
    monkeypatch.setattr(agent.executor, "focus_fleet", lambda state: [])
    fake_planner.analysis = "Little to do.\n\nDECISIONS:\nS1: 2 a mid budget\nS2: none\n"
    result = run_cycle()
    assert "budget KYV-745 mid" in result["commands"]
    assert "# SITUATIONS" in result["sitrep"]


def test_decisions_without_their_heading_still_count():
    """The local model's own answer on the 73-hour save, shortened."""
    analysis = ("The solid storage at KYV-745 is at 99% capacity, which is critical.\n\n"
                "S1: 1 KGZ-352 is in a moderate threat sector.\n"
                "S2: 2 expanding refinedmetals production will consume the ore.\n"
                "S5: none GWH-145 needs no action.\n\nOTHER\nAssign a scout.\n\n"
                "STANDING GOALS\n1. Expand KYV-745.\n")
    answers, unreadable = action_lines.decisions(analysis)
    assert [(n, k) for n, k, _ in answers] == [(1, 1), (2, 2), (5, None)]
    assert unreadable == []
