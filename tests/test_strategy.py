"""A strategist's plan, carried out by the rules (strategy.py)."""

import copy
import json

import catalog
import executor
import purchases
import standing
import strategy

PLAN = {"horizon_hours": 3, "rationale": "hull parts for the yards",
        "stations": {"KYV-745": {"build": {"hullparts": 2, "storage_container": 1},
                                 "miners": {"solid": 2}, "traders": 1}},
        "blueprints": []}


def _station(state):
    return next(a for a in state["assets"] if a["code"] == "KYV-745")


def _workable(state):
    st = _station(state)
    st["modules"] = list(st.get("modules") or []) + ["dockarea_arg_m_station_01_lowtech_macro"]
    st["manager"] = st.get("manager") or {"name": "M"}
    return st


def _ship(state, code, macro, group=None, orders=None):
    ship = dict(copy.deepcopy(next(a for a in state["assets"] if a["code"] == "ASO-629")),
                code=code, macro=macro, assignment={} if group is None else {"group": group},
                orders=orders if orders is not None else [])
    state["assets"].append(ship)
    return ship


def test_a_plan_is_read_from_its_file_into_memory(small_state, tmp_path, monkeypatch):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(PLAN), encoding="utf-8")
    monkeypatch.setattr(strategy, "STRATEGY_FILE", str(path))
    data = {}
    assert strategy.load(data, small_state) == []
    assert data["strategy"]["plan"]["stations"]["KYV-745"]["build"] == {"hullparts": 2, "storage_container": 1}
    path.write_text('{"stations": {}}', encoding="utf-8")                 # no horizon, no rationale
    assert strategy.load(data, small_state)[0].startswith("strategy file not used")
    assert data["strategy"]["plan"]["horizon_hours"] == 3                 # the last good plan stays


def test_modules_count_by_what_they_are(small_state):
    st = copy.deepcopy(_station(small_state))
    st["modules"] = ["prod_gen_hullparts_macro", "prod_tel_hullparts_macro", "storage_tel_l_container_01_macro",
                     "storage_arg_m_solid_01_macro", "dockarea_arg_m_station_01_lowtech_macro", "hab_tel_s_01_macro"]
    assert strategy.built(st, "hullparts") == 2
    assert strategy.built(st, "storage_container") == 1 and strategy.built(st, "storage_solid") == 1
    assert strategy.built(st, "dock") == 1 and strategy.built(st, "habitation_tel") == 1
    assert strategy.built(st, "habitation_arg") == 0


def test_the_plan_says_what_a_station_is_still_short_of(small_state):
    st = copy.deepcopy(_station(small_state))
    st["modules"] = ["prod_gen_hullparts_macro"]
    data = {"strategy": {"plan": PLAN}}
    assert strategy.next_builds(st, data) == ["hullparts", "storage_container"]
    st["modules"] += ["prod_gen_hullparts_macro", "storage_tel_l_container_01_macro"]
    assert strategy.next_builds(st, data) == []                           # every target stands
    assert strategy.next_builds(st, {}) is None                           # no plan: margins decide


def test_grow_builds_what_the_plan_asks_before_what_pays(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    _workable(state)
    monkeypatch.setattr(catalog, "expansion_margins", lambda state: [("water", 9000.0)])
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: f"expand {action['station_id']} {action['ware']}")
    assert standing.grow(state, {"strategy": {"plan": PLAN}}) == ["expand KYV-745 hullparts"]
    assert standing.grow(state, {}) == ["expand KYV-745 water"]


def test_a_planned_modules_blueprint_is_bought(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    state["player"]["blueprints"] = []
    seen = []
    monkeypatch.setattr(purchases, "start", lambda data, ware, state: (seen.append(ware) or "dockat SHP-001 STN-001 argon", None))
    assert strategy.blueprints(state, {"strategy": {"plan": PLAN}}) == ["dockat SHP-001 STN-001 argon"]
    assert seen == ["module_gen_prod_hullparts_01"]
    assert strategy.blueprints(state, {"strategy": {"plan": PLAN}, "purchases": {"x": {}}}) == []  # one errand at a time


def test_the_ship_and_equipment_blueprints_a_plan_names_are_bought(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    state["player"]["blueprints"] = ["ship_tel_m_miner_solid_01_a"]
    seen = []
    monkeypatch.setattr(purchases, "start", lambda data, ware, state: (seen.append(ware) or "dockat SHP-001 STN-001 teladi", None))
    plan = dict(PLAN, stations={}, blueprints=["ship_tel_m_miner_solid_01_a", "engine_tel_m_allround_01_mk1"])
    assert strategy.blueprints(state, {"strategy": {"plan": plan}}) == ["dockat SHP-001 STN-001 teladi"]
    assert seen == ["engine_tel_m_allround_01_mk1"]              # the one we hold is skipped


def test_what_the_sellers_of_a_named_blueprint_list_is_asked_once(small_state):
    state = copy.deepcopy(small_state)
    state["known_stations"] = [{"code": "ZIR-755", "owner": "teladi"}]
    data = {"strategy": {"plan": dict(PLAN, blueprints=["ship_tel_m_miner_solid_01_a"])}}
    assert strategy.offers(state, data) == ["offers teladi ship", "offers teladi thruster"]
    assert strategy.offers(state, data) == []                   # once


def test_a_ship_whose_blueprint_we_hold_is_built_at_our_wharf(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    state["assets"] = [a for a in state["assets"] if a.get("cls") == "station"]
    _station(state)["modules"] = list(_station(state)["modules"]) + [executor.EXPANSION_MODULES["wharf"][0]]
    state["player"]["blueprints"] = ["ship_tel_m_miner_solid_01_a", "engine_tel_m_allround_01_mk1"]
    monkeypatch.setattr(catalog, "_buy_options", lambda state, roles: [catalog.Option("buy", f"buyship {roles[0][0]}")])
    plan = {"strategy": {"plan": PLAN}}
    assert strategy.fleet(state, plan) == ["buildship KYV-745 ship_tel_m_miner_solid_01_a_macro x4-agent-m"]
    # Without an engine blueprint, or within the hour of the last one, it is bought as before.
    state["player"]["blueprints"] = ["ship_tel_m_miner_solid_01_a"]
    assert strategy.fleet(state, plan) == ["buyship solid miner"]
    # Unless the plan is buying the blueprints for it: then it waits for them.
    waiting = {"strategy": {"plan": dict(PLAN, blueprints=["ship_tel_m_miner_solid_01_a",
                                                           "engine_tel_m_allround_01_mk1"])}}
    assert strategy.fleet(state, waiting) == ["buyship container freighter"]   # the trader is not
    state["player"]["blueprints"].append("engine_tel_m_allround_01_mk1")
    state["sent_at"] = {"buyship": state["meta"]["playtime_s"] - 60}
    assert strategy.own_build(state, "ship_{race}_m_miner_solid_01_a_macro") is None
    # One on order at our wharf holds the next.
    state["sent_at"] = {}
    state["ships_on_order"] = [{"wharf": "KYV-745", "macro": "ship_tel_m_miner_solid_01_a_macro",
                                "since": state["meta"]["playtime_s"] - 60, "paid": 0, "missing": []}]
    assert strategy.own_build(state, "ship_{race}_m_miner_solid_01_a_macro") is None


def test_fleet_assigns_a_free_ship_before_it_buys_one(small_state, monkeypatch):
    state = copy.deepcopy(small_state)
    state["assets"] = [a for a in state["assets"] if a.get("cls") == "station" or a["code"] == "ASO-629"]
    _ship(state, "MNR-001", "ship_arg_m_miner_solid_01_a_macro")
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: f"assign {action['ship_ref']} {action['station_id']} {action['role']}")
    bought = []
    monkeypatch.setattr(catalog, "_buy_options",
                        lambda state, roles: [catalog.Option("buy", f"buyship {roles[0][0]}")] if not bought.append(1) else [])
    plan = {"strategy": {"plan": PLAN}}
    # Free ships are put to work, one per target a cycle: the next cycle sees it.
    assert strategy.fleet(state, plan) == ["assign MNR-001 KYV-745 mine", "assign ASO-629 KYV-745 trade"]
    # With none free, one purchase a cycle, for the first target still short.
    for code in ("MNR-001", "ASO-629"):
        next(a for a in state["assets"] if a["code"] == code)["orders"] = [{"order": "MiningRoutine", "default": True}]
    assert strategy.fleet(state, plan) == ["buyship solid miner"]


def test_the_report_shows_how_far_each_station_is(small_state):
    state = copy.deepcopy(small_state)
    _station(state)["modules"] = ["prod_gen_hullparts_macro"]
    text = "\n".join(strategy.lines(state, {"strategy": {"plan": PLAN, "since": 7200, "source": "plan.json"}}))
    assert "hull parts for the yards" in text and "hullparts 1/2" in text and "storage_container 0/1" in text
    assert "traders" in text and "solid miners" in text
