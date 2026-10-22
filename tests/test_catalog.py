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


def _with_a_yard_and_money(state):
    state["player"]["money"] = 50_000_000
    home = next(a for a in state["assets"] if a["code"] == "KYV-745")
    state["known_stations"].append({"code": "YRD-001", "owner": "argon", "builds": ["m"],
                                    "place": dict(home["place"])})
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["orders"] = [{"order": "TradeRoutine", "default": False}]
    return home


def test_an_idle_ship_holds_a_purchase_of_its_own_kind(small_state):
    state = copy.deepcopy(small_state)
    _with_a_yard_and_money(state)
    freighter = (("container freighter", "ship_{race}_m_trans_container_01_a_macro"),)
    miner = (("liquid miner", "ship_{race}_m_miner_liquid_01_a_macro"),)
    assert catalog._buy_options(state, freighter)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")   # a container freighter
    ship["orders"] = []
    assert catalog._idle_ship(state, "container freighter") == "ASO-629"
    assert catalog._buy_options(state, freighter) == []
    assert catalog._buy_options(state, miner)                            # not its kind


def test_no_purchase_for_money_alone(small_state):
    state = copy.deepcopy(small_state)
    _with_a_yard_and_money(state)
    assert not any(s.key == "capital" or any(o.command.startswith("buyship") for o in s.options)
                   for s in catalog.situations(state))


def test_a_miner_is_bought_only_with_room_for_what_it_brings(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    home = _with_a_yard_and_money(state)
    home["offers"].append({"ware": "methane", "side": "buy", "desired": 10000, "amount": 10000})
    home.setdefault("cargo", {})["methane"] = 100
    monkeypatch.setattr(catalog.executor, "storage_fill", lambda st, table: {"liquid": 0.5})
    short = next(s for s in catalog.situations(state) if s.key == "short:KYV-745:methane")
    assert any("liquid_01_a_macro" in o.command for o in short.options)
    monkeypatch.setattr(catalog.executor, "storage_fill", lambda st, table: {"liquid": 0.95})
    assert not any(s.key == "short:KYV-745:methane" for s in catalog.situations(state))


def test_a_freighter_is_bought_when_products_pile_up_and_none_is_free(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    home = _with_a_yard_and_money(state)
    home["offers"].append({"ware": "energycells", "side": "sell", "amount": 5000, "price": 16})
    home.setdefault("cargo", {})["energycells"] = 50000
    monkeypatch.setattr(catalog.executor, "storage_fill", lambda st, table: {"container": 0.95})
    for a in state["assets"]:
        if catalog.sitrep.ship_type(a.get("macro")) in catalog.executor.FREIGHTERS:
            a["assignment"] = {"group": 1}
    full = next(s for s in catalog.situations(state) if s.key == "storage:KYV-745:container")
    assert any("trans_container_01_a_macro" in o.command for o in full.options)



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


def test_a_second_answer_to_one_situation_is_reported_not_sent():
    found = [Situation("a", "full", [Option("x", "automine A"), Option("y", "automine B")])]
    commands, notes, counts = catalog.decide(found, "DECISIONS:\nS1: 1\nS1: 2\n")
    assert commands == ["automine A"] and counts["chosen"] == 1
    assert "S1 answered more than once; only the first answer counts" in notes


def test_a_scout_we_just_sent_is_left_to_sweep(small_state):
    import executor
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["orders"] = [{"order": "Explore", "target_sector": ship["place"]["sector"], "default": False}]
    now = state["meta"]["playtime_s"]
    assert executor._exploring_nothing(ship, state)
    state["logbook"] = [[now - 900, "[x4-agent] ORDER: ASO-629 exploring Black Hole Sun IV"]]
    assert not executor._exploring_nothing(ship, state)
    assert not any(s.key == "explore:ASO-629" for s in catalog.situations(state))
    state["logbook"] = [[now - 4000, "[x4-agent] ORDER: ASO-629 exploring Black Hole Sun IV"]]
    assert executor._exploring_nothing(ship, state)


def test_a_scout_held_by_its_own_order_is_cleared_first(small_state):
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["macro"] = "ship_par_s_scout_01_a_macro"
    ship["orders"] = [{"order": "MoveWait", "default": False, "state": "started"},
                      {"order": "Explore", "default": True}]
    now = state["meta"]["playtime_s"]
    ship["attack"] = {"method": "lowattentionattack", "time": now - 60}
    found = {s.key: s for s in catalog.situations(state)}
    option = found["fire:ASO-629"].options[0]
    assert (option.before, option.command) == (["clear ASO-629"], "explore ASO-629")
    commands, _, _ = catalog.decide([found["fire:ASO-629"]], "DECISIONS:\nS1: 1\n")
    assert commands == ["clear ASO-629", "explore ASO-629"]


def test_a_paid_repair_is_not_cleared(small_state):
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["orders"] = [{"order": "Repair", "default": False, "state": "started"}]
    assert catalog._holding("ASO-629", state) is None
    ship["orders"] = [{"order": "MoveWait", "default": False, "state": "started"}]
    assert catalog._holding("ASO-629", state) == "MoveWait"


def test_rules_only_never_asks_the_model_and_still_acts(run_cycle, fake_planner, monkeypatch):
    monkeypatch.setattr(agent, "RULES_ONLY", True)
    monkeypatch.setattr(agent.executor, "repricing", lambda state: ["price KYV-745 energycells sell 15"])
    result = run_cycle()
    assert fake_planner.calls == 0
    assert "price KYV-745 energycells sell 15" in result["commands"]


def test_no_pricing_leaves_the_prices_to_the_game(run_cycle, monkeypatch):
    monkeypatch.setattr(agent, "RULES_ONLY", True)
    monkeypatch.setattr(agent, "NO_PRICING", True)
    monkeypatch.setattr(agent.executor, "repricing", lambda state: ["price KYV-745 energycells sell 15"])
    result = run_cycle()
    assert not any(c.startswith("price ") for c in result["commands"])


def test_a_ship_fighting_back_is_left_alone(small_state):
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["macro"] = "ship_par_s_fighter_01_a_macro"
    ship["assignment"] = {"group": 3}
    ship["orders"] = [{"order": "Attack", "default": False, "state": "started"}]
    ship["attack"] = {"method": "lowattentionattack", "time": state["meta"]["playtime_s"] - 30}
    assert catalog._holding("ASO-629", state) is None
    assert not any(s.key == "fire:ASO-629" for s in catalog.situations(state))


def test_an_explore_order_we_sent_counts_before_the_logbook_shows_it(small_state):
    import executor
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["orders"] = [{"order": "Explore", "target_sector": ship["place"]["sector"], "default": False}]
    assert executor._exploring_nothing(ship, state)
    state["sent_at"] = {"explore ASO-629": state["meta"]["playtime_s"] - 300}
    assert not executor._exploring_nothing(ship, state)


def test_a_fighter_on_covered_ground_is_offered_home(small_state):
    state = copy.deepcopy(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["macro"] = "ship_par_s_fighter_01_a_macro"
    ship["assignment"] = {}
    ship["orders"] = [{"order": "Explore", "target_sector": ship["place"]["sector"], "default": True}]
    found = {s.key: s for s in catalog.situations(state)}
    commands = [o.command for o in found["explore:ASO-629"].options]
    assert commands and all(c.startswith("assign ASO-629") and c.endswith("defend") for c in commands)


def test_expansions_are_ranked_by_margin_at_known_prices(small_state):
    state = copy.deepcopy(small_state)
    state["known_stations"] = [{"code": "BUY-001", "owner": "argon", "place": {},
                                    "offers": [{"ware": "microchips", "side": "buy", "price": 1000, "amount": 500},
                                               {"ware": "energycells", "side": "buy", "price": 16, "amount": 500},
                                               {"ware": "siliconwafers", "side": "buy", "price": 300, "amount": 500}]}]
    margins = dict(catalog.expansion_margins(state))
    # 72 chips at 1000 against 50 cells at 16 and 200 wafers at 300, every 600 s
    assert round(margins["microchips"]) == round((72 * 1000 - 50 * 16 - 200 * 300) * 6)
    assert "spices" not in margins          # nobody we know buys spices here


def test_a_station_that_could_grow_is_offered_its_best_expansions(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    monkeypatch.setattr(catalog, "expansion_margins", lambda state: [("microchips", 40000.0), ("water", -5.0)])
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: (f"expand {action['station_id']} {action['ware']}"
                                               if action.get("type") == "expand_station" else None))
    grow = next(s for s in catalog.situations(state) if s.key == "grow:KYV-745")
    assert [o.command for o in grow.options] == ["expand KYV-745 microchips"]


def test_a_ware_we_already_hold_more_of_than_anyone_wants_is_not_offered(small_state):
    state = copy.deepcopy(small_state)
    state["known_stations"] = [{"code": "BUY-001", "owner": "argon", "place": {},
                                "offers": [{"ware": "energycells", "side": "buy", "price": 20, "amount": 5000}]}]
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["cargo"] = {"energycells": 1000}
    assert "energycells" in dict(catalog.expansion_margins(state))
    station["cargo"] = {"energycells": 6000}
    assert "energycells" not in dict(catalog.expansion_margins(state))


def test_a_ware_piling_up_for_ten_module_hours_is_not_expanded(small_state):
    state = copy.deepcopy(small_state)
    state["known_stations"] = [{"code": "BUY-001", "owner": "argon", "place": {},
                                "offers": [{"ware": "energycells", "side": "buy", "price": 20, "amount": 10_000_000}]}]
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["cargo"] = {"energycells": 50_000}          # under ten hours of 10,500 an hour
    assert "energycells" in dict(catalog.expansion_margins(state))
    station["cargo"] = {"energycells": 120_000}         # over ten hours
    assert "energycells" not in dict(catalog.expansion_margins(state))


def test_a_full_store_is_offered_a_larger_store_first(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["cargo"] = {"ore": 90000}
    monkeypatch.setattr(catalog.executor, "storage_fill", lambda st, table: {"solid": 0.99})
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: (f"expand {action['station_id']} {action['ware']}"
                                               if action.get("type") == "expand_station" else None))
    full = next(s for s in catalog.situations(state) if s.key == "storage:KYV-745:solid")
    assert full.options[0].command == "expand KYV-745 storage_solid"


def test_an_empty_station_starts_with_a_ware_it_can_make_alone(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    assert catalog.first_module_ok("energycells") and catalog.first_module_ok("water")
    assert not catalog.first_module_ok("microchips")
    station["modules"] = []
    assert catalog._growth_wares(station, ["microchips", "water"]) == ["water"]
    station["modules"] = ["prod_gen_water_macro"]
    assert catalog._growth_wares(station, ["microchips", "water"]) == ["microchips", "water"]
