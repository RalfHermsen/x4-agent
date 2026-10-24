"""Standing rules (4.3, 4.4, 4.5, 4.7, 4.10 to 4.13, 4.15) and game events (4.8)."""

import copy

import memory
import sitrep
import standing


def _station(state):
    return next(a for a in state["assets"] if a["code"] == "KYV-745")


def _add_ship(state, code, macro, **extra):
    base = copy.deepcopy(next(a for a in state["assets"] if a["code"] == "ASO-629"))
    base.update(code=code, macro=macro, docked_at=None, connection="space",
                orders=[{"order": "Wait", "state": "started", "default": True}], assignment={})
    base.update(extra)
    state["assets"].append(base)
    return base


def test_sell_limit_keeps_what_the_station_eats(small_state):
    state = copy.deepcopy(small_state)
    st = _station(state)
    st["production_queue"] = ["sunriseflowers", "energycells"]
    st["offers"] = [{"ware": "energycells", "side": "buy", "price": 16, "amount": 0, "desired": 1485},
                    {"ware": "energycells", "side": "sell", "price": 18, "amount": 300, "desired": 0}]
    assert standing.sell_limits(state, {}) == ["limit KYV-745 energycells sell 1000 raise"]


def test_revisit_sends_one_idle_scout_once(small_state):
    state = copy.deepcopy(small_state)
    _station(state)["offers"] = [{"ware": "sunriseflowers", "side": "sell", "price": 100,
                                  "amount": 10, "desired": 0}]
    state["known_stations"] = []
    _add_ship(state, "SCT-001", "ship_tel_s_scout_01_a_macro")
    data = {}
    assert standing.revisit(state, data) == ["revisit SCT-001 KYV-745"]
    assert standing.revisit(state, data) == []


def test_satellite_goes_where_we_have_no_eyes(small_state):
    state = copy.deepcopy(small_state)
    _station(state)["offers"] = [{"ware": "sunriseflowers", "side": "sell", "price": 100,
                                  "amount": 10, "desired": 0}]
    state["known_stations"] = [{"code": "BUY-001", "owner": "argon", "place": {"sector": "s2"},
                                "offers": [{"ware": "sunriseflowers", "side": "buy"}]}]
    state["eyes"] = []
    _add_ship(state, "SCT-001", "ship_tel_s_scout_01_a_macro")
    data = {}
    assert standing.satellites(state, data) == ["satellite SCT-001 BUY-001 argon"]
    state["eyes"] = ["s2"]
    assert standing.satellites(state, {}) == []


def test_ledger_every_tenth_cycle():
    data = {}
    sent = [standing.ledger({}, data) for _ in range(12)]
    assert sent[0] == ["ledger 2"] and sent[10] == ["ledger 2"]
    assert all(s == [] for i, s in enumerate(sent) if i not in (0, 10))


def test_once_settings_go_out_once(small_state):
    data = {}
    first = standing.once(small_state, data)
    assert first == ["resupply medium", "avoid hostile on", "respond foundabandonedship claim",
                     "respond foundlockbox collect", "turrets KYV-745 attackenemies"]
    assert standing.once(small_state, data) == []


def test_patrol_only_with_a_threat_at_home(small_state):
    state = copy.deepcopy(small_state)
    _add_ship(state, "FTR-001", "ship_arg_s_fighter_01_a_macro")
    assert standing.patrols(state, {}) == []
    sector = _station(state)["place"]["sector"]
    state["hostiles"] = {sector: {"xenon": {"ship_s": 2}}}
    assert standing.patrols(state, {}) == ["patrol FTR-001 KYV-745"]


def test_own_builder_finds_a_waiting_build(small_state):
    state = copy.deepcopy(small_state)
    _add_ship(state, "BLD-001", "ship_arg_xl_builder_01_a_macro", owner="player")
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {}}
    assert standing.find_builds(state, {}) == ["deploy BLD-001 KYV-745"]
    bs["build"]["builders"] = ["[0x1]"]
    assert standing.find_builds(state, {}) == []


def test_game_events_and_ledger_read_from_the_logbook(small_state):
    state = copy.deepcopy(small_state)
    t = state["meta"]["playtime_s"]
    state["logbook"] = [
        [t - 3, "[x4-agent] ATTACKED: ASO-629 by XEN-001 (Xenon)"],
        [t - 2, "[x4-agent lua] LEDGER KYV-745 2h paid_to_npcs=48000 energycells=40000 water=8000"],
    ]
    data = {}
    assert memory.game_refusals(data, state) == ["the game reports: ATTACKED: ASO-629 by XEN-001 (Xenon)"]
    assert data["ledger"]["KYV-745"]["paid"] == 48000
    assert data["ledger"]["KYV-745"]["wares"] == {"energycells": "40000", "water": "8000"}


def test_a_lost_ship_names_its_killer(small_state):
    state = copy.deepcopy(small_state)
    data = {"fleet": {"ASO-629": "container freighter", "TJL-171": "scout"}}
    state["assets"] = [a for a in state["assets"] if a["code"] != "ASO-629"]
    state["logbook"] = [[1.0, "[x4-agent] DESTROYED: ASO-629 by XEN-001 (Xenon)"]]
    (line,) = memory.check_fleet(data, state, sitrep.ship_type)
    assert line == ("ASO-629 (container freighter) was in the fleet last cycle and is not "
                    "there now: destroyed, by XEN-001 (Xenon).")


def test_hire_after_the_build_waited(small_state):
    state = copy.deepcopy(small_state)
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {}}
    sector = _station(state)["place"]["sector"]
    state["builders"] = [{"code": "CZK-784", "owner": "antigone", "sector": sector}]
    data = {}
    assert standing.hire_builders(state, data) == []                 # just started waiting
    later = copy.deepcopy(state)
    later["meta"]["playtime_s"] += 700
    assert standing.hire_builders(later, data) == ["hire CZK-784 antigone KYV-745"]
    assert standing.hire_builders(later, data) == []                 # one hire per build


def test_damaged_ship_goes_to_the_nearest_yard(small_state):
    import gamedata
    state = copy.deepcopy(small_state)
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    top = gamedata.ships()[aso["macro"]]["hull"]
    aso["hull"] = top * 0.5
    sector = aso["place"]["sector"]
    state["known_stations"] = [{"code": "YRD-001", "owner": "teladi", "builds": ["m"],
                                "place": {"sector": sector}, "offers": []}]
    data = {}
    assert standing.repairs(state, data) == ["repair ASO-629 YRD-001 teladi"]
    assert standing.repairs(state, data) == []                       # once
    aso["hull"] = top
    standing.repairs(state, data)
    assert data["standing"]["repairing"] == {}                      # repaired


def test_hull_read_from_the_save(large_state):
    damaged = [a for a in large_state["assets"] if a.get("hull") is not None]
    assert damaged and all(a["hull"] > 0 for a in damaged)


def test_seminar_for_a_low_manager_when_held(small_state):
    state = copy.deepcopy(small_state)
    station = _station(state)
    station["manager"] = {"code": "YVA-122", "management_raw": 1, "management_stars": 0}
    state["player"]["inventory"] = {}
    assert standing.seminars(state, {}) == []
    state["player"]["inventory"] = {"inv_seminar_management_0": 1}
    data = {}
    assert standing.seminars(state, data) == ["seminar KYV-745"]
    assert standing.seminars(state, data) == []                    # same save, not twice


def test_inventory_read_from_the_save(large_state):
    # The 105-hour player carries a spacesuit repair laser and an object
    # scanner, and no seminars: the seminars in that save sit in data vaults
    # and traders' stock, which is not the player's to spend.
    inventory = large_state["player"]["inventory"]
    assert inventory.get("weapon_gen_spacesuit_repairlaser_01_mk1") == 1
    assert not any(w.startswith("inv_seminar") for w in inventory)


def test_no_repair_where_the_ship_cannot_dock(small_state):
    import gamedata
    state = copy.deepcopy(small_state)
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")    # an M freighter
    aso["hull"] = gamedata.ships()[aso["macro"]]["hull"] * 0.5
    sector = aso["place"]["sector"]
    state["known_stations"] = [{"code": "BIG-001", "owner": "argon", "builds": ["l", "xl"],
                                "place": {"sector": sector}, "offers": []}]
    assert standing.repairs(state, {}) == []


def test_a_build_that_is_building_gets_no_second_builder(small_state):
    state = copy.deepcopy(small_state)
    _add_ship(state, "BLD-001", "ship_arg_xl_builder_01_a_macro", owner="player")
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 0, "in_progress": 1, "builders": [],
                   "processor": {"state": "building", "vessel_required": True, "step": 4, "steps": 10}}
    assert standing.find_builds(state, {}) == []
    bs["build"]["processor"]["state"] = "awaitconstructionvessel_build"
    assert standing.find_builds(state, {}) == ["deploy BLD-001 KYV-745"]


def test_a_lost_scout_is_replaced_at_once(small_state):
    import copy
    import catalog
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    home = _station(state)
    state["known_stations"].append({"code": "YRD-001", "owner": "argon", "builds": ["m"],
                                    "place": dict(home["place"])})
    _add_ship(state, "SCT-001", "ship_arg_s_scout_01_a_macro", owner="player")
    scout = next(a for a in state["assets"] if a["code"] == "SCT-001")
    scout["orders"] = [{"order": "Explore", "default": True, "state": "started"}]
    data = {}
    assert standing.scouts(state, data) == []                 # one scout, the most so far
    state["assets"].remove(scout)                             # lost exploring
    commands = standing.scouts(state, data)
    assert len(commands) == 1 and commands[0].startswith("buyship YRD-001 argon ship_arg_s_scout_01_a_macro")
    assert standing.scouts(state, data) == []                 # one at a time while it comes


def test_an_idle_scout_is_sent_exploring(small_state):
    import copy
    state = copy.deepcopy(small_state)
    _add_ship(state, "SCT-002", "ship_arg_s_scout_01_a_macro", owner="player")
    next(a for a in state["assets"] if a["code"] == "SCT-002")["orders"] = []
    assert "explore SCT-002" in standing.scouts(state, {})


def test_grow_expands_with_the_top_ranked_ware(small_state, monkeypatch):
    import copy
    import catalog
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    monkeypatch.setattr(catalog, "expansion_margins", lambda state: [("microchips", 40000.0), ("water", 9000.0)])
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: (None if action["ware"] == "microchips"
                                               else f"expand {action['station_id']} {action['ware']}"))
    assert standing.grow(state, {}) == ["expand KYV-745 water"]   # the first that passes its gates
    state["player"]["money"] = 1_000_000
    assert standing.grow(state, {}) == []                          # below the capital floor


def test_rules_named_off_are_not_run(small_state):
    import copy
    state = copy.deepcopy(small_state)
    everything = standing.commands(state, {})
    assert any(c.startswith("resupply") for c in everything)
    assert not any(c.startswith("resupply") for c in standing.commands(state, {}, off={"once"}))


def test_an_explore_order_is_not_resent_to_a_scout_still_at_the_wharf(small_state):
    import copy
    state = copy.deepcopy(small_state)
    _add_ship(state, "SCT-003", "ship_arg_s_scout_01_a_macro", owner="player")
    next(a for a in state["assets"] if a["code"] == "SCT-003")["orders"] = []
    now = state["meta"]["playtime_s"]
    assert "explore SCT-003" not in standing.scouts(state, {"sent_at": {"explore SCT-003": now - 300}})
    assert "explore SCT-003" in standing.scouts(state, {"sent_at": {"explore SCT-003": now - 4000}})


def test_a_station_with_modules_and_no_manager_is_sent_one_once(small_state):
    import copy
    state = copy.deepcopy(small_state)
    assert standing.managers(state, {}) == []                       # KYV-745 has one
    _station(state)["manager"] = None
    assert standing.managers(state, {}) == ["manager KYV-745"]
    now = state["meta"]["playtime_s"]
    assert standing.managers(state, {"sent_at": {"manager KYV-745": now - 600}}) == []
    assert standing.managers(state, {"sent_at": {"manager KYV-745": now - 4000}}) == ["manager KYV-745"]
    _station(state)["modules"] = []                                 # nothing to run yet
    assert standing.managers(state, {}) == []


def test_a_station_without_a_dock_gets_one(small_state, monkeypatch):
    import copy
    import catalog
    state = copy.deepcopy(small_state)
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: f"expand {action['station_id']} {action['ware']}")
    assert standing.docks(state, {}) == []                          # KYV-745 has a dock and a pier
    _station(state)["modules"] = ["prod_gen_water_macro", "storage_tel_m_solid_01_macro"]
    _station(state)["manager"] = None
    assert standing.docks(state, {}) == ["expand KYV-745 dock"]
    assert standing.managers(state, {}) == []                       # nobody would trade with it
    assert catalog._growth_wares(_station(state), ["water"]) == []
    _station(state)["modules"] = []                                 # an empty plot: its dock first
    assert standing.docks(state, {}) == ["expand KYV-745 dock"]
    assert standing.managers(state, {}) == []


def test_a_managed_station_with_an_empty_account_gets_the_estimate_once(small_state):
    import copy
    state = copy.deepcopy(small_state)
    _station(state)["account"] = {"id": "[0x1]", "own": "1", "amount": "930744"}
    assert standing.accounts(state, {}) == []
    _station(state)["account"] = {"id": "[0x1]", "own": "1", "min": "4877115"}   # a min, no money
    assert standing.accounts(state, {}) == ["account KYV-745"]
    # Spent down after one filling: GKL-870, 4,232 of a 624,000 minimum.
    _station(state)["account"] = {"id": "[0x1]", "own": "1", "min": "624000", "amount": "4232"}
    assert standing.accounts(state, {}) == ["account KYV-745"]
    _station(state)["account"] = {"id": "[0x1]", "own": "1", "min": "624000", "amount": "400000"}
    assert standing.accounts(state, {}) == []
    _station(state)["account"] = {"id": "[0x1]", "own": "1", "min": "4877115"}
    now = state["meta"]["playtime_s"]
    assert standing.accounts(state, {"sent_at": {"account KYV-745": now - 600}}) == []
    _station(state)["manager"] = None
    assert standing.accounts(state, {}) == []


def test_a_build_still_waiting_long_after_a_hire_hires_again(small_state):
    state = copy.deepcopy(small_state)
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {}}
    sector = _station(state)["place"]["sector"]
    state["builders"] = [{"code": "CZK-784", "owner": "antigone", "sector": sector},
                         {"code": "DLM-221", "owner": "argon", "sector": sector}]
    data = {}
    standing.hire_builders(state, data)
    state["meta"]["playtime_s"] += 700
    first = standing.hire_builders(state, data)
    state["meta"]["playtime_s"] += 3600
    assert standing.hire_builders(state, data) == []                  # still its own
    state["meta"]["playtime_s"] += 2 * 3600
    second = standing.hire_builders(state, data)
    assert len(first) == len(second) == 1 and first != second         # the first one left


def test_a_queued_build_of_standing_modules_is_cancelled_and_not_asked_again(small_state):
    import copy
    import executor
    state = copy.deepcopy(small_state)
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    modules = list(_station(state)["modules"])
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {}, "queue": [modules]}
    assert executor._adds_nothing(bs, state)
    now = state["meta"]["playtime_s"]
    data = {"sent_at": {"expand KYV-745 refinedmetals": now - 7200}}
    assert standing.empty_builds(state, data) == ["cancelbuild KYV-745 refinedmetals"]
    assert standing.empty_builds(state, {"sent_at": {"cancelbuild KYV-745": now - 60}}) == []
    bs["build"]["queue"] = [modules + ["prod_gen_water_macro"]]       # adds a module: a real build
    assert not executor._adds_nothing(bs, state)
    assert standing.empty_builds(state, data) == []


def test_a_build_that_adds_nothing_gets_no_builder_and_no_money(small_state):
    import copy
    import executor
    state = copy.deepcopy(small_state)
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {},
                   "queue": [list(_station(state)["modules"])]}
    state["builders"] = [{"code": "CZK-784", "owner": "antigone", "sector": _station(state)["place"]["sector"]}]
    data = {}
    standing.hire_builders(state, data)
    state["meta"]["playtime_s"] += 700
    assert standing.hire_builders(state, data) == []
    assert executor.funding(state, {}) == []


def test_the_connector_blueprint_is_bought_when_missing(small_state, monkeypatch):
    import copy
    import gamedata
    import executor
    import purchases
    state = copy.deepcopy(small_state)
    ware = gamedata.modules()[executor.CONNECTOR]["ware"]
    monkeypatch.setattr(purchases, "start", lambda data, w, state: (f"dockat SHP-001 STN-001 argon", None))
    state["player"]["blueprints"] = []
    assert standing.connectors(state, {}) == ["dockat SHP-001 STN-001 argon"]
    assert standing.connectors(state, {"purchases": {ware: {}}}) == []     # under way already
    state["player"]["blueprints"] = [ware]
    assert standing.connectors(state, {}) == []


def test_a_ship_on_an_order_of_its_own_is_cleared_before_it_docks_to_buy(small_state, monkeypatch):
    import copy
    import gamedata
    import executor
    import purchases
    state = copy.deepcopy(small_state)
    state["player"]["blueprints"] = []
    ware = gamedata.modules()[executor.CONNECTOR]["ware"]

    def start(data, w, state):
        data.setdefault("purchases", {})[w] = {"ship": "ASO-629"}
        return "dockat ASO-629 STN-001 argon", None
    monkeypatch.setattr(purchases, "start", start)
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    aso["orders"] = [{"order": "MoveWait", "state": "started", "default": False}]
    assert standing.connectors(state, {}) == ["clear ASO-629", "dockat ASO-629 STN-001 argon"]
    aso["orders"] = [{"order": "Explore", "state": "started", "default": True}]
    assert standing.connectors(state, {}) == ["dockat ASO-629 STN-001 argon"]
