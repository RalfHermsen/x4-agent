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


def test_no_hire_while_a_vessel_is_deployed(small_state):
    """ship7d-camp hired a vessel for KYV-745 every two hours while NAW-754
    lay there waiting for resources; the game sent each one away."""
    state = copy.deepcopy(small_state)
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 0, "in_progress": 1, "builders": [], "deployed": True,
                   "processor": {"state": "waitingforresources", "vessel_required": True}}
    sector = _station(state)["place"]["sector"]
    state["builders"] = [{"code": "CZK-784", "owner": "antigone", "sector": sector}]
    data = {}
    standing.hire_builders(state, data)
    state["meta"]["playtime_s"] += 3 * 3600
    assert standing.hire_builders(state, data) == []
    bs["build"]["deployed"] = False                                   # it left
    assert standing.hire_builders(state, data) == []                  # the wait starts again
    state["meta"]["playtime_s"] += 700
    assert standing.hire_builders(state, data) == ["hire CZK-784 antigone KYV-745"]


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


XEN_SECTOR = "cluster_18_sector001_macro"


def _raid_ready(state, destroyers=3):
    """KYV-745 with this many whole destroyers defending it, a plan for 3 and a Xenon base next door."""
    state = copy.deepcopy(state)
    home = _station(state)
    home["assignment"] = {"groups": {3: "defence"}}
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"] += [dict(copy.deepcopy(aso), code=f"DES-00{i}", cls="ship_l", hull=None, assignment={"group": 3},
                             macro="ship_tel_l_destroyer_01_a_macro", place=dict(home["place"]))
                        for i in range(destroyers)]
    state["hostiles"] = {XEN_SECTOR: {"xenon": {"station": 1, "ship_m": 5}}}
    data = {"strategy": {"plan": {"stations": {"KYV-745": {"build": {}, "miners": {}, "traders": 0, "defenders": 0,
                                                           "destroyers": 3, "raid_sector": XEN_SECTOR}}}}}
    return state, data


def test_a_raid_goes_when_every_destroyer_stands(small_state):
    state, data = _raid_ready(small_state, destroyers=2)
    assert standing.raids(state, data) == []
    state, data = _raid_ready(small_state)
    assert standing.raids(state, data) == ["command DES-001 DES-000 attack", "command DES-002 DES-000 attack",
                                           f"raid DES-000 {XEN_SECTOR}"]
    assert data["standing"]["raid"]["phase"] == "out"
    assert standing.raids(state, data) == []                      # once


def test_no_raid_without_a_xenon_station_seen_there(small_state):
    state, data = _raid_ready(small_state)
    state["hostiles"] = {XEN_SECTOR: {"xenon": {"ship_m": 5}}}
    assert standing.raids(state, data) == []


def test_no_raid_on_more_xl_than_the_fleet_can_take(small_state):
    state, data = _raid_ready(small_state)
    state["hostiles"][XEN_SECTOR]["xenon"]["ship_xl"] = 1
    assert standing.raids(state, data) == []                      # 3 destroyers, one XL takes 6


def test_a_hurt_fleet_comes_back_and_defends_again(small_state):
    import gamedata
    state, data = _raid_ready(small_state)
    standing.raids(state, data)
    top = gamedata.ships()["ship_tel_l_destroyer_01_a_macro"]["hull"]
    for ship in state["assets"]:
        if ship["code"].startswith("DES-"):
            ship["hull"] = top * 0.6
            ship["place"] = {"sector": XEN_SECTOR}
    assert standing.raids(state, data) == ["patrol DES-000 KYV-745"]
    assert data["standing"]["raid"]["phase"] == "back"
    assert standing.raids(state, data) == []                      # still on the way
    for ship in state["assets"]:
        if ship["code"].startswith("DES-"):
            ship["place"] = dict(_station(state)["place"])
    assert standing.raids(state, data) == [f"assign DES-00{i} KYV-745 defend" for i in range(3)]
    assert "raid" not in data["standing"]


def test_a_raid_ends_when_the_station_is_gone_or_the_leader_is(small_state):
    state, data = _raid_ready(small_state)
    standing.raids(state, data)
    state["hostiles"] = {}
    assert standing.raids(state, data) == ["patrol DES-000 KYV-745"]
    state, data = _raid_ready(small_state)
    standing.raids(state, data)
    state["assets"] = [a for a in state["assets"] if a["code"] != "DES-000"]
    assert standing.raids(state, data) == ["assign DES-001 KYV-745 defend", "assign DES-002 KYV-745 defend"]


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


def test_a_wharf_of_ours_with_no_ship_trader_is_sent_one_once(small_state):
    """ship7-camp: our first own ship sat in KYV-745's queue for ten game hours;
    nobody held the ship trader post, whose holder works the queue."""
    import copy
    import executor
    state = copy.deepcopy(small_state)
    assert standing.shiptraders(state, {}) == []                    # no wharf yet
    _station(state)["modules"] = _station(state)["modules"] + [executor.EXPANSION_MODULES["wharf"][0]]
    assert standing.shiptraders(state, {}) == ["shiptrader KYV-745"]
    now = state["meta"]["playtime_s"]
    assert standing.shiptraders(state, {"sent_at": {"shiptrader KYV-745": now - 600}}) == []
    assert standing.shiptraders(state, {"sent_at": {"shiptrader KYV-745": now - 4000}}) == ["shiptrader KYV-745"]
    _station(state)["shiptrader"] = True
    assert standing.shiptraders(state, {}) == []


def test_a_station_that_keeps_no_cargo_drones_is_told_to_keep_ten(small_state):
    """GKL-870 had no supply order for drones, and the game asked for cargo
    drones there from game hour 77 on; KYV-745 kept 10."""
    import copy
    state = copy.deepcopy(small_state)
    _station(state)["supplies"] = {}
    assert standing.cargo_drones(state, {}) == ["cargodrones KYV-745 10"]
    now = state["meta"]["playtime_s"]
    assert standing.cargo_drones(state, {"sent_at": {"cargodrones KYV-745": now - 600}}) == []
    _station(state)["supplies"] = {"ship_gen_xs_cargodrone_empty_01_a": 10}
    assert standing.cargo_drones(state, {}) == []
    _station(state)["supplies"], _station(state)["manager"] = {}, None
    assert standing.cargo_drones(state, {}) == []                   # nobody to buy the parts


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


def test_an_overfull_account_is_set_back_to_the_estimate(small_state):
    # The ceremony series ended with 70 to 78 million on station accounts.
    state = copy.deepcopy(small_state)
    _station(state)["account"] = {"id": "[0x1]", "own": "1", "min": "3821640", "max": "5732460",
                                  "amount": "26036332"}
    assert standing.accounts(state, {}) == ["account KYV-745"]
    _station(state)["account"]["amount"] = "9000000"               # above the max, not twice it
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


def test_a_running_build_with_every_module_standing_is_reported_as_stuck_after_hours(small_state):
    # The game will not cancel it (ship6-camp), so the report says what holds
    # the station: KYV-745 waited 54 game hours for 270 shields.
    import executor
    state = copy.deepcopy(small_state)
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    modules = list(_station(state)["modules"])
    now = state["meta"]["playtime_s"]
    bs["build"] = {"queued": 0, "in_progress": 1, "builders": [], "processor": {}, "queue": [],
                   "running": [{"since": now - executor.STUCK_BUILD_AFTER - 60, "sequence": modules}]}
    assert executor._waits_for_equipment(bs, state)
    assert any("waited for equipment since game hour" in line for line in sitrep.build_lines(state))
    bs["build"]["running"][0]["sequence"] = modules + ["prod_gen_water_macro"]   # a module to come
    assert not executor._waits_for_equipment(bs, state)
    bs["build"]["running"][0] = {"since": now - 3600, "sequence": modules}       # not for long yet
    assert not executor._waits_for_equipment(bs, state)
    bs["build"]["running"] = []
    assert not executor._waits_for_equipment(bs, state)


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
        data.setdefault("purchases", {})[w] = {"ship": "ASO-629", "stage": "docking"}
        return "dockat ASO-629 STN-001 argon", None
    monkeypatch.setattr(purchases, "start", start)
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    aso["orders"] = [{"order": "MoveWait", "state": "started", "default": False}]
    assert standing.connectors(state, {}) == ["clear ASO-629", "dockat ASO-629 STN-001 argon"]
    aso["orders"] = [{"order": "Explore", "state": "started", "default": True}]
    assert standing.connectors(state, {}) == ["dockat ASO-629 STN-001 argon"]


def _waiting_on_turrets(small_state, held=4087, wanted=836):
    """KYV-745 holds turret components for its wharf; its build waits on some."""
    state = copy.deepcopy(small_state)
    st = _station(state)
    st["cargo"] = dict(st.get("cargo") or {}, turretcomponents=held)
    st["offers"] = [{"ware": "turretcomponents", "side": "buy", "price": 361, "amount": 12101,
                     "desired": 12101}]
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["offers"] = [{"ware": "turretcomponents", "side": "buy", "price": 383, "amount": wanted,
                     "desired": wanted}] if wanted else []
    return state


def test_own_stock_goes_to_the_build_for_our_ships_only(small_state):
    """ship7e: the build waited on 836 turret components, KYV-745 held 4,087
    and offered none, and no other expansion of KYV-745 could start."""
    data = {}
    assert standing.own_stock(_waiting_on_turrets(small_state), data) == [
        "traderule KYV-745 turretcomponents sell own",
        "limit KYV-745 turretcomponents sell 3251",
        "tradeware KYV-745 turretcomponents sell on"]
    assert standing.own_stock(_waiting_on_turrets(small_state), data) == []
    # The wharf used some: the limit follows, so 836 stay on offer.
    assert standing.own_stock(_waiting_on_turrets(small_state, held=3500), data) == [
        "limit KYV-745 turretcomponents sell 2664",
        "tradeware KYV-745 turretcomponents sell on"]
    assert standing.own_stock(_waiting_on_turrets(small_state, wanted=0), data) == [
        "tradeware KYV-745 turretcomponents sell off",
        "limit KYV-745 turretcomponents sell clear",
        "traderule KYV-745 turretcomponents sell default"]
    assert data["standing"]["own_stock"] == {}


def test_own_stock_leaves_a_ware_sold_already_or_held_short(small_state):
    assert standing.own_stock(_waiting_on_turrets(small_state, held=500), {}) == []
    state = _waiting_on_turrets(small_state)
    _station(state)["offers"].append({"ware": "turretcomponents", "side": "sell", "price": 300,
                                      "amount": 100, "desired": 0})
    assert standing.own_stock(state, {}) == []


def test_a_large_station_without_discs_gets_one_before_anything_else(small_state, monkeypatch):
    """GKL-870 fell at 187 modules with 8 turrets and no disc (ship7e3-camp)."""
    import copy
    import catalog
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    st = next(a for a in state["assets"] if a["code"] == "KYV-745")
    st["modules"] = ["dockarea_arg_m_station_01_lowtech_macro"] + ["prod_gen_water_macro"] * 59
    st["manager"] = {"name": "M"}
    monkeypatch.setattr(catalog, "expansion_margins", lambda state: [("water", 9000.0)])
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: f"expand {action['station_id']} {action['ware']}")
    assert standing.grow(state, {}) == ["expand KYV-745 defence"]
    st["modules"].append("defence_tel_disc_01_macro")              # 61 modules, 1 disc
    assert standing.grow(state, {}) == ["expand KYV-745 water"]
