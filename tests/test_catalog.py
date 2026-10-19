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


def test_a_station_short_of_methane_is_offered_a_liquid_miner(small_state):
    state = copy.deepcopy(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["offers"].append({"ware": "methane", "side": "buy", "desired": 10000, "amount": 10000})
    station.setdefault("cargo", {})["methane"] = 100
    miner = next(a for a in state["assets"] if a["code"] == "ASO-629")
    miner["macro"] = "ship_arg_m_miner_liquid_01_a_macro"
    miner["assignment"] = {}
    found = {s.key: s for s in catalog.situations(state)}
    assert "assign ASO-629 KYV-745 mine" in [o.command for o in found["short:KYV-745:methane"].options]
    assert "0 of our 1 liquid miner(s)" in found["short:KYV-745:methane"].text


def test_a_shortage_of_a_bought_ware_is_not_a_mining_situation(small_state):
    state = copy.deepcopy(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["offers"].append({"ware": "microchips", "side": "buy", "desired": 10000, "amount": 10000})
    assert not any(s.key.startswith("short:") for s in catalog.situations(state))


def test_the_same_purchase_chosen_twice_is_sent_once():
    found = [Situation("a", "first", [Option("x", "buyship A")]),
             Situation("b", "second", [Option("y", "buyship A")])]
    commands, _, counts = catalog.decide(found, "DECISIONS:\nS1: 1\nS2: 1\n")
    assert commands == ["buyship A"] and counts["chosen"] == 2 and counts["none"] == 0


def test_a_purchase_in_the_last_game_hour_holds_the_next(small_state):
    state = copy.deepcopy(small_state)
    now = state["meta"]["playtime_s"]
    assert not catalog._bought_recently(state)
    state["logbook"] = [[now - 600, catalog.BOUGHT + " ship_arg_m_trans_container_01_a_macro at X"]]
    assert catalog._bought_recently(state)
    state["player"]["money"] = 50_000_000
    assert catalog._buy_options(state, (("container freighter", "ship_{race}_m_trans_container_01_a_macro"),)) == []
    state["logbook"] = [[now - 4000, catalog.BOUGHT + " ship_arg_m_trans_container_01_a_macro at X"]]
    assert not catalog._bought_recently(state)


def test_idle_capital_waits_while_a_ship_waits_for_work(small_state):
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    home = next(a for a in state["assets"] if a["code"] == "KYV-745")
    state["known_stations"].append({"code": "YRD-001", "owner": "argon", "builds": ["m"],
                                    "place": dict(home["place"])})
    assert catalog.idle_ships(state)          # ASO-629 has no orders
    assert catalog.idle_capital(state) == []
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["orders"] = [{"order": "TradeRoutine", "default": False}]
    assert not catalog.idle_ships(state)
    assert catalog.idle_capital(state)        # with everyone at work, it is offered


def test_one_ship_purchase_per_cycle():
    found = [Situation("a", "money", [Option("x", "buyship A freighter")]),
             Situation("b", "short", [Option("y", "buyship A miner")])]
    commands, notes, _ = catalog.decide(found, "DECISIONS:\nS1: 1\nS2: 1\n")
    assert commands == ["buyship A freighter"]
    assert any("one ship purchase per cycle" in n for n in notes)


def test_resends_that_change_nothing_are_not_offered(small_state):
    import executor
    from schemas import PlannerResponse
    state = copy.deepcopy(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    station.setdefault("assignment", {})["groups"] = {3: "defence"}
    ship["assignment"] = {"group": 3}
    state["assets"].append({"cls": "buildstorage", "station": "KYV-745", "code": "BST-001",
                            "build": {"queued": 0, "in_progress": 1}})

    def sent(action):
        plan = PlannerResponse.model_validate({"assessment": "", "updated_goals": [],
                                               "actions": [{**action, "rationale": "t"}]})
        commands, skipped = executor.to_commands(plan.actions, state, allow_busy=True)
        return commands, [reason for _, reason in skipped]

    assert sent({"type": "assign_ship", "ship_ref": "ASO-629", "station_id": "KYV-745",
                 "role": "defend"}) == ([], ["already in effect, not re-sent"])
    assert sent({"type": "assign_ship", "ship_ref": "ASO-629", "station_id": "KYV-745",
                 "role": "trade"})[0] == ["assign ASO-629 KYV-745 trade"]
    # The small save has no expansion blueprints, so the gate itself is asked.
    from types import SimpleNamespace
    expand = SimpleNamespace(station_id="KYV-745")
    assert executor._expansion_planned(expand, state)
    state["assets"][-1]["build"] = {"queued": 0, "in_progress": 0}
    assert not executor._expansion_planned(expand, state)


def test_a_station_without_modules_gets_no_budget_situation(small_state):
    state = copy.deepcopy(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["modules"] = []
    assert not any(s.key == "budget:KYV-745" for s in catalog.no_budget(state))
