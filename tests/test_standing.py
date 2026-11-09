"""Standing rules (4.3, 4.4, 4.5, 4.7, 4.10 to 4.13, 4.15) and game events (4.8)."""

import copy
from pathlib import Path

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


def test_a_station_with_a_ship_bay_sells_what_it_makes_above_a_keep(small_state):
    """From 191 game hours ZLR-942's S/M bay held all its field coils, none on offer."""
    import executor
    state = copy.deepcopy(small_state)
    st = _station(state)
    st["production_queue"] = ["fieldcoils", "hullparts", "water"]
    st["offers"] = [{"ware": "hullparts", "side": "buy", "price": 150, "amount": 6462, "desired": 6462}]
    state["player"]["blueprints"] = ["ship_tel_l_destroyer_01_a", "shield_tel_m_standard_01_mk2"]
    data = {}
    assert standing.wharf_sales(state, data) == []                    # no bay, nothing held
    st["modules"] = list(st["modules"]) + [executor.EXPANSION_MODULES["wharf"][0]]
    out = standing.wharf_sales(state, data)
    assert "limit KYV-745 hullparts sell 6462" in out                 # its own lines want more
    assert "tradeware KYV-745 hullparts sell on" in out
    assert "limit KYV-745 fieldcoils sell 2000" in out                # our mk2 shield takes 32 each
    assert not any("water" in c for c in out)                         # no ship of ours is built from it
    assert standing.wharf_sales(state, data) == []                    # once


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
    _add_ship(state, "SCT-001", "ship_tel_s_scout_01_a_macro", satellites_aboard=1)
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
    _add_ship(state, "SCT-001", "ship_tel_s_scout_01_a_macro", satellites_aboard=1)
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


def test_own_builder_is_called_again_for_the_next_build(small_state):
    """start5: the vessel served the chain, then the discs waited 8.9 h beside it."""
    state = copy.deepcopy(small_state)
    _add_ship(state, "BLD-001", "ship_arg_xl_builder_01_a_macro", owner="player")
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {}}
    data = {}
    assert standing.find_builds(state, data) == ["deploy BLD-001 KYV-745"]
    assert standing.find_builds(state, data) == []                    # on its way
    bs["build"]["builders"] = ["[0x1]"]
    assert standing.find_builds(state, data) == []                    # served
    bs["build"]["builders"] = []
    assert standing.find_builds(state, data) == ["deploy BLD-001 KYV-745"]


def test_own_builder_at_work_on_one_build_is_not_taken_for_another(small_state):
    """A pier queued at ZLR-942 would have taken our one vessel from GZI-064's station."""
    state = copy.deepcopy(small_state)
    _add_ship(state, "BLD-001", "ship_arg_xl_builder_01_a_macro", owner="player",
              orders=[{"order": "DeployToStation"}])
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {}}
    assert standing.find_builds(state, {}) == []


def test_each_station_gets_the_default_build_method_once(small_state):
    data = {}
    assert standing.build_method(small_state, data) == ["buildmethod KYV-745 default"]
    assert standing.build_method(small_state, data) == []


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


def test_a_kill_of_ours_is_reported(small_state):
    state = copy.deepcopy(small_state)
    state["logbook"] = [[1.0, "[x4-agent] KILLED: XEN-001 ship_xen_s_fighter_01_a_macro (Xenon) by FIG-000"]]
    assert memory.game_refusals({}, state) == [
        "the game reports: KILLED: XEN-001 ship_xen_s_fighter_01_a_macro (Xenon) by FIG-000"]


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


def _sent_home(*codes):
    return [f"release {c}" for c in codes] + [f"assign {c} KYV-745 defend" for c in codes]


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


def test_a_parked_destroyer_leaves_unless_it_waits_for_a_repair(small_state):
    state, data = _raid_ready(small_state, destroyers=1)
    ship = next(a for a in state["assets"] if a["code"] == "DES-000")
    ship["orders"] = [{"order": "Patrol", "default": True}, {"order": "DockAndWait"}]
    ship["connection"] = "space"
    assert standing.undock_fleet(state, data) == []            # in space: on its way in
    ship["connection"] = "dock"
    assert standing.undock_fleet(state, data) == ["undock DES-000"]
    ship["orders"].append({"order": "Repair"})
    assert standing.undock_fleet(state, data) == []


def test_a_frigate_or_fighter_parked_at_our_station_leaves_one_in_its_carrier_stays(small_state):
    """start8s: five of the route patrol and six of the carrier's fighters lay at ZLR-942."""
    state, data = _raid_ready(small_state, destroyers=0)
    parked = [{"order": "DockAndWait"}, {"order": "Escort", "default": True}]
    _add_ship(state, "FRI-000", "ship_tel_m_frigate_01_a_macro", connection="dock", docked_at="KYV-745", orders=parked)
    _add_ship(state, "FIG-000", "ship_tel_s_fighter_02_a_macro", connection="dock", docked_at="KYV-745", orders=parked)
    _add_ship(state, "FIG-001", "ship_tel_s_fighter_02_a_macro", connection="dock", docked_at="CAR-000", orders=parked)
    assert standing.undock_fleet(state, data) == ["undock FRI-000", "undock FIG-000"]


def _falcon(state, zone):
    state["player"]["occupied_ship"] = "FAL-000"
    _station(state)["place"] = {"sector": "S", "zone": "by_the_station"}
    return _add_ship(state, "FAL-000", "ship_tel_s_fighter_01_a_macro", place={"sector": "S", "zone": zone})


def test_the_players_ship_flies_back_to_the_station(small_state):
    state, data = _raid_ready(small_state, destroyers=1)
    ship = _falcon(state, "by_the_station")
    state["meta"]["playtime_s"] = 5000
    # Clears the old queue once, also when it stands close by.
    assert standing.shelter(state, data) == ["undock FAL-000", "autopilot KYV-745 player"]
    state["meta"]["playtime_s"] = 5000 + standing.SHELTER_AGAIN
    assert standing.shelter(state, data) == []
    ship["place"] = {"sector": "S", "zone": "by_the_gate"}
    state["meta"]["playtime_s"] = 5000 + 2 * standing.SHELTER_AGAIN - 1
    assert standing.shelter(state, data) == ["autopilot KYV-745 player"]
    state["meta"]["playtime_s"] += standing.SHELTER_AGAIN - 1
    assert standing.shelter(state, data) == []                 # on its way


def test_the_players_ship_docked_is_left_alone(small_state):
    state, data = _raid_ready(small_state, destroyers=1)
    _falcon(state, "by_the_gate").update(connection="dock", docked_at="HOW-875")
    state["meta"]["playtime_s"] = 5000
    assert standing.shelter(state, data) == []


def test_no_player_ship_no_order(small_state):
    state, data = _raid_ready(small_state, destroyers=1)
    state["player"]["occupied_ship"] = None
    assert standing.shelter(state, data) == []


def test_undock_takes_a_ship_not_a_station():
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    bare = lua.split("local BARE_HANDLERS = {", 1)[1].split("}", 1)[0]
    assert "undock = undock_ship" in bare


def test_scouts_freighters_and_miners_flee_when_attacked_warships_do_not(small_state):
    import copy
    state = copy.deepcopy(small_state)
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    for code, macro in (("SCO-001", "ship_arg_s_scout_01_a_macro"), ("TRA-001", "ship_arg_m_trans_container_01_a_macro"),
                        ("MIN-001", "ship_arg_m_miner_liquid_01_a_macro"), ("DES-001", "ship_arg_l_destroyer_02_a_macro"),
                        ("FRI-001", "ship_arg_m_frigate_01_a_macro")):
        state["assets"].append(dict(copy.deepcopy(aso), code=code, macro=macro))
    state["assets"] = [a for a in state["assets"] if a["code"].endswith("-001") and a["code"][:3] in
                       ("SCO", "TRA", "MIN", "DES", "FRI")]
    data = {}
    out = standing.civilians_flee(state, data)
    assert sorted(c.split()[1] for c in out) == ["MIN-001", "SCO-001", "TRA-001"]
    assert all(c.endswith(" attacked flee") for c in out)
    assert standing.civilians_flee(state, data) == []


def test_shiprespond_is_a_bare_verb_of_the_bridge():
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    bare = lua.split("local BARE_HANDLERS = {", 1)[1].split("}", 1)[0]
    assert "shiprespond = set_ship_response" in bare
    assert "SetDefaultResponseToSignalForControllable(const char* newresponse" in lua


def test_the_bridge_puts_an_auxiliary_under_a_fleet_and_sends_it_for_supplies():
    root = Path(__file__).parent.parent / "bridge/x4_agent_bridge"
    lua = (root / "ui/x4agent.lua").read_text(encoding="utf-8")
    md = (root / "md/x4_agent_bridge.xml").read_text(encoding="utf-8")
    assert "supplyfleet = true" in lua.split("local ROLE_GROUP = {", 1)[1].split("}", 1)[0]
    bare = lua.split("local BARE_HANDLERS = {", 1)[1].split("}", 1)[0]
    assert "getsupplies = get_supplies" in bare and "collect = collect" in bare
    # `collect` finds its sector by `sector_by_macro`, a local declared before it.
    assert lua.index("local function sector_by_macro") < lua.index("local function collect(")
    assert "event.param2 == 'command_supplyfleet'" in md and 'exact="assignment.supplyfleet"' in md


def test_the_bridge_moves_a_ship_to_another_factions_station():
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    bare = lua.split("local BARE_HANDLERS = {", 1)[1].split("}", 1)[0]
    assert "moveto = move_to" in bare
    # It finds the station by `faction_station` and its sector by `station_sector`, locals before it.
    assert lua.index("local function faction_station") < lua.index("local function move_to(")
    assert lua.index("local function station_sector") < lua.index("local function move_to(")
    move = lua.split("local function move_to(args)", 1)[1].split("\nend\n", 1)[0]
    assert '"MoveWait"' in move and "false, false, true)" in move


def test_the_bridge_hunts_a_ship_of_another_faction():
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    bare = lua.split("local BARE_HANDLERS = {", 1)[1].split("}", 1)[0]
    assert "hunt = hunt" in bare
    # It finds the target by `faction_ship`, a local before it.
    assert lua.index("local function faction_ship") < lua.index("local function hunt(")
    hunt = lua.split("local function hunt(args)", 1)[1].split("\nend\n", 1)[0]
    assert '"Attack"' in hunt and "primarytarget" in hunt and "false, false, true)" in hunt


def test_a_raid_goes_for_kha_ak_weapon_platforms_before_the_hive():
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    raid = lua.split("local function raid(args)", 1)[1].split("\nend\n", 1)[0]
    assert 'string.find(macro, "weaponplatform", 1, true) then return 1' in raid
    assert "rank(macro) < best" in raid


def test_the_plans_sectors_to_avoid_are_listed_once_each(small_state):
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["avoid_sectors"] = ["cluster_29_sector001_macro"]
    assert standing.avoid_sectors(state, data) == ["avoid sector cluster_29_sector001_macro on"]
    assert standing.avoid_sectors(state, data) == []


def test_avoid_sector_is_a_global_verb_of_the_bridge():
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    table = lua.split("local GLOBAL_HANDLERS = {", 1)[1].split("}", 1)[0]
    assert "sector = set_avoid_sector" in table and "UpdateBlacklist2(BlacklistInfo2 info)" in lua


def test_a_guard_leader_left_on_its_post_by_an_earlier_run_is_called_off(small_state):
    """start8c: NQB-447 patrolled Hatikvah's Choice I alone for six game hours."""
    state, data = _raid_ready(small_state)
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader["orders"] = [{"order": "Patrol"}, {"order": "ProtectStation", "default": True}]
    assert standing.raids(state, data) == ["undock DES-000"]
    leader["orders"] = [{"order": "ProtectStation", "default": True}]
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"


def test_a_guard_left_on_its_post_by_an_earlier_run_is_taken_over(small_state):
    """start8n called the guard of six home and left Hatikvah's Choice I empty for 1.3 game hours."""
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_guard"] = True
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader.update(orders=[{"order": "Patrol"}, {"order": "ProtectStation", "default": True}],
                  place={"sector": XEN_SECTOR}, assignment={"group": 3, "groups": {2: "attack"}})
    next(a for a in state["assets"] if a["code"] == "DES-001")["assignment"] = {"group": 2}
    state["assigned_to"] = {"DES-001": "DES-000"}
    assert standing.raids(state, data) == []
    raid = data["standing"]["raid"]
    assert raid["leader"] == "DES-000" and raid["ships"] == ["DES-000", "DES-001"] and raid["arrived"] and raid["guard"]
    # Also with an Attack where its Patrol was: start9k sent RGM-519's 30 home from the Kha'ak nest.
    leader["orders"] = [{"order": "Attack"}, {"order": "ProtectStation", "default": True}]
    data.pop("standing")
    assert standing.raids(state, data) == []
    assert data["standing"]["raid"]["leader"] == "DES-000"


def test_a_raid_on_the_pacts_stations_counts_the_stations_we_know(small_state):
    """start8p: the Pact at -0.032 is not in the save's hostiles; its stations are known."""
    state, data = _raid_ready(small_state)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal["raid_faction"] = "scaleplate"
    state["hostiles"] = {}
    assert standing.raids(state, data) == []                    # nothing of theirs known there
    state["all_stations"] = [{"code": "PAC-001", "owner": "scaleplate", "sector": XEN_SECTOR}]
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR} go scaleplate"
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(raid_faction="scaleplate", raid_guard=True)
    state["hostiles"] = {}
    state["all_stations"] = [{"code": "PAC-001", "owner": "scaleplate", "sector": XEN_SECTOR}]
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR} stay scaleplate"


def test_a_guard_goes_on_until_the_build_storages_are_gone_too(small_state):
    """start8q: the Pact built again from the storage beside AQQ-834's wreck."""
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(raid_guard=True, raid_faction="scaleplate")
    state["hostiles"] = {}
    state["all_stations"] = [{"code": "PAC-001", "owner": "scaleplate", "sector": XEN_SECTOR}]
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR} stay scaleplate"
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader.update(place={"sector": XEN_SECTOR}, orders=[{"order": "Patrol"}])
    state["all_stations"] = []                                  # the station fell
    state["build_storages"] = [{"code": "BST-001", "owner": "scaleplate", "sector": XEN_SECTOR}]
    state["meta"]["playtime_s"] = data["standing"]["raid"]["since"] + standing.RAID_ASK_AGAIN + 1
    # Its patrol goes again behind the attack: in start8y the attack took the queued one with it.
    assert standing.raids(state, data) == [f"raid DES-000 {XEN_SECTOR} stay scaleplate"]
    state["build_storages"] = []
    state["meta"]["playtime_s"] += standing.RAID_ASK_AGAIN + 1
    assert standing.raids(state, data) == []                    # only the patrol stays


def test_a_sector_patrols_leader_on_the_way_is_not_taken_for_the_guards(small_state):
    """start9w: MLX-818, leading Hatikvah's Choice I's patrol on the way to Heretic's End, was
    taken for the guard's leader; the 30 went under it and it fell to a Pact station."""
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_guard"] = True
    patrol = next(a for a in state["assets"] if a["code"] == "DES-000")
    patrol.update(place={"sector": XEN_SECTOR}, orders=[{"order": "Patrol"}])
    data["standing"] = {"sector_patrol": {"DES-000": XEN_SECTOR}}
    out = standing.raids(state, data)
    assert (data["standing"].get("raid") or {}).get("leader") != "DES-000"
    assert f"raid DES-000 {XEN_SECTOR} stay xenon" not in out
    # Not on a patrol, the same ship is the guard taken over.
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_guard"] = True
    next(a for a in state["assets"] if a["code"] == "DES-000").update(place={"sector": XEN_SECTOR},
                                                                      orders=[{"order": "Patrol"}])
    standing.raids(state, data)
    assert data["standing"]["raid"]["leader"] == "DES-000"


def test_a_guard_hunts_a_ship_that_attacked_a_freighter_on_its_way_once(small_state):
    """start9a: the Pact's scout QRJ-271 shot five freighters in Silent Witness XI past the guard."""
    state, data = _raid_ready(small_state)
    for code in ("DES-000", "DES-001", "DES-002"):
        next(a for a in state["assets"] if a["code"] == code)["place"] = {"sector": XEN_SECTOR}
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"].append(dict(copy.deepcopy(aso), code="TRA-001", macro="ship_tel_m_trans_container_01_a_macro",
                                place={"sector": XEN_SECTOR}))
    state["assets"].append(dict(copy.deepcopy(aso), code="TRA-002", macro="ship_tel_m_trans_container_01_a_macro",
                                place=dict(_station(state)["place"])))
    data["standing"] = {"raid": {"sector": XEN_SECTOR, "home": "KYV-745", "home_sector": _station(state)["place"]["sector"],
                                 "leader": "DES-000", "ships": ["DES-000", "DES-001", "DES-002"], "phase": "out",
                                 "since": 0, "arrived": True, "guard": True, "faction": "scaleplate"}}
    state["meta"]["playtime_s"] = 1000
    state["logbook"] = [[900.0, "[x4-agent] ATTACKED: TRA-001 by OLD-001 (Scale Plate Pact) [scaleplate]"]]
    assert standing.hunts(state, data) == []                    # before this run: history
    # Not the Xenon or the Kha'ak; and the guard's own only in its sector, with no reserve to send.
    state["logbook"] += [[1010.0, "[x4-agent] ATTACKED: TRA-001 by XEN-001 (Xenon) [xenon]"],
                         [1010.5, "[x4-agent] ATTACKED: TRA-001 by KHA-001 (Kha'ak) [khaak]"],
                         [1010.7, "[x4-agent] ATTACKED: TRA-002 by PAC-007 (Scale Plate Pact) [scaleplate]"],
                         [1011.0, "[x4-agent] ATTACKED: DES-001 by PAC-008 (Scale Plate Pact) [scaleplate]"],
                         [1012.0, "[x4-agent] ATTACKED: TRA-001 by PAC-009 (Scale Plate Pact) [scaleplate]"]]
    state["meta"]["playtime_s"] = 1020
    assert standing.hunts(state, data) == ["hunt DES-001 PAC-009 scaleplate", "hunt DES-002 PAC-009 scaleplate"]
    assert standing.hunts(state, data) == []                    # once
    # Shot down, it is gone from the save, and where it was last cycle still counts.
    state["assets"] = [a for a in state["assets"] if a["code"] != "TRA-001"]
    state["logbook"].append([1030.0, "[x4-agent] DESTROYED: TRA-001 by PAC-010 (Scale Plate Pact) [scaleplate]"])
    assert standing.hunts(state, data) == ["hunt DES-001 PAC-010 scaleplate", "hunt DES-002 PAC-010 scaleplate"]


def test_the_home_reserve_above_its_floor_hunts_before_the_guard(small_state):
    """start9j: six of the guard went after the Pact's KET-043 one sector away and were back
    on Escort while it shot two more freighters; three of the reserve killed it."""
    state, data = _raid_ready(small_state, destroyers=5)
    home = _station(state)["place"]["sector"]
    for code in ("DES-000", "DES-001"):
        next(a for a in state["assets"] if a["code"] == code)["place"] = {"sector": XEN_SECTOR}
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"].append(dict(copy.deepcopy(aso), code="TRA-002", macro="ship_tel_m_trans_container_01_a_macro",
                                place={"sector": home}))
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_home"] = 2
    data["standing"] = {"raid": {"sector": XEN_SECTOR, "home": "KYV-745", "home_sector": home,
                                 "leader": "DES-000", "ships": ["DES-000", "DES-001"], "phase": "out",
                                 "since": 0, "arrived": True, "guard": True, "faction": "scaleplate"},
                        "hunt_seen": 900.0}
    state["meta"]["playtime_s"] = 1020
    state["logbook"] = [[1010.0, "[x4-agent] ATTACKED: TRA-002 by PAC-007 (Scale Plate Pact) [scaleplate]"]]
    # Three at home, two of them the floor: one goes, at home too.
    assert standing.hunts(state, data) == ["hunt DES-002 PAC-007 scaleplate"]


def test_a_ship_that_attacked_a_freighter_next_to_home_is_hunted(small_state):
    """start9r: the Pact's SHH-527 shot DZK-868 in Silent Witness I, one jump from home and off
    the guard's way, and no hunt went."""
    from purchases import _graph
    state, data = _raid_ready(small_state, destroyers=5)
    home = _station(state)["place"]["sector"]
    beside = next(s for s in _graph()[home] if s != XEN_SECTOR)
    for code in ("DES-000", "DES-001"):
        next(a for a in state["assets"] if a["code"] == code)["place"] = {"sector": XEN_SECTOR}
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"].append(dict(copy.deepcopy(aso), code="TRA-003", macro="ship_tel_m_trans_container_01_a_macro",
                                place={"sector": beside}))
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_home"] = 2
    data["standing"] = {"raid": {"sector": XEN_SECTOR, "home": "KYV-745", "home_sector": home,
                                 "leader": "DES-000", "ships": ["DES-000", "DES-001"], "phase": "out",
                                 "since": 0, "arrived": True, "guard": True, "faction": "scaleplate"},
                        "hunt_seen": 900.0}
    state["meta"]["playtime_s"] = 1020
    state["logbook"] = [[1010.0, "[x4-agent] DESTROYED: TRA-003 by PAC-011 (Scale Plate Pact) [scaleplate]"]]
    assert standing.hunts(state, data) == ["hunt DES-002 PAC-011 scaleplate"]
    # One shot down before the hunt goes is no prey (start9y: ZXR-504).
    data["standing"].update(hunt=[], prey={}, hunt_seen=900.0)
    state["logbook"].append([1012.0, "[x4-agent] KILLED: PAC-011 ship_arg_m_bomber_02_a_macro (Scale Plate Pact) by ESC-001"])
    assert standing.hunts(state, data) == []


def test_with_no_guard_out_a_sector_patrol_hunts_in_its_sector(small_state):
    """start10d: the guard lost to ZTU-930, the Pact's LCV-670 shot three freighters in Silent
    Witness XII past its patrol of five, and no hunt went."""
    state, data = _raid_ready(small_state)
    for code, order in (("DES-000", "Patrol"), ("DES-001", "Escort"), ("DES-002", "Escort")):
        next(a for a in state["assets"] if a["code"] == code).update(place={"sector": XEN_SECTOR},
                                                                      orders=[{"order": order}])
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"].append(dict(copy.deepcopy(aso), code="TRA-001", macro="ship_tel_m_trans_container_01_a_macro",
                                place={"sector": XEN_SECTOR}))
    data["standing"] = {"sector_patrol": {c: XEN_SECTOR for c in ("DES-000", "DES-001", "DES-002")},
                        "hunt_seen": 900.0}
    state["meta"]["playtime_s"] = 1020
    state["logbook"] = [[1010.0, "[x4-agent] DESTROYED: TRA-001 by PAC-012 (Scale Plate Pact) [scaleplate]"]]
    assert standing.hunts(state, data) == []                    # no station keeps a guard
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_guard"] = True
    data["standing"].update(hunt_seen=900.0, prey={})
    # The leader keeps its Patrol; the two under it go.
    assert standing.hunts(state, data) == ["hunt DES-001 PAC-012 scaleplate", "hunt DES-002 PAC-012 scaleplate"]


def _fighters_ready(small_state, fighters=4):
    """KYV-745 with one trader of its own and this many free fighters."""
    state, data = _raid_ready(small_state, destroyers=0)
    home = _station(state)
    home["assignment"] = {"groups": {1: "trade"}}
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"].append(dict(copy.deepcopy(aso), code="TRA-001", macro="ship_tel_m_trans_container_01_a_macro",
                                assignment={"group": 1}, place=dict(home["place"])))
    state["assigned_to"] = {"TRA-001": "KYV-745"}
    state["assets"] += [dict(copy.deepcopy(aso), code=f"FIG-00{i}", cls="ship_s", macro="ship_tel_s_fighter_01_a_macro",
                             assignment=None, orders=[], place=dict(home["place"])) for i in range(fighters)]
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal.update(patrol_sectors={XEN_SECTOR: 2}, escorts_per_trader=2, traders=1)
    state["meta"]["playtime_s"] = 1000
    return state, data


def test_free_fighters_patrol_a_sector_first_then_escort_the_traders(small_state):
    """The player's call at 362 game hours: miners lost to the Kha'ak in Second Contact II
    Flashpoint, freighters to the Pact."""
    state, data = _fighters_ready(small_state, fighters=3)
    assert standing.fighter_posts(state, data) == [f"raid FIG-000 {XEN_SECTOR} stay", "command FIG-001 FIG-000 attack",
                                                   "command FIG-002 TRA-001 defence"]
    assert standing.fighter_posts(state, data) == []            # each once
    # wings and patrols leave them alone.
    data["strategy"]["plan"]["stations"]["KYV-745"]["fighters_per_carrier"] = 40
    assert not any("FIG-" in c for c in standing.wings(state, data))
    # A leader whose Patrol went is told again, not at once; the escort, under its trader now, stays.
    next(a for a in state["assets"] if a["code"] == "FIG-001")["assignment"] = {"group": 4}
    next(a for a in state["assets"] if a["code"] == "FIG-000")["assignment"] = {"groups": {4: "attack"}}
    state["assigned_to"]["FIG-001"] = "FIG-000"
    next(a for a in state["assets"] if a["code"] == "FIG-002")["assignment"] = {"group": 5}
    state["meta"]["playtime_s"] += standing.PATROL_AGAIN
    assert standing.fighter_posts(state, data) == [f"raid FIG-000 {XEN_SECTOR} stay"]
    # With the leader lost, the other leads.
    state["assets"] = [a for a in state["assets"] if a["code"] != "FIG-000"]
    next(a for a in state["assets"] if a["code"] == "FIG-001")["assignment"] = None
    assert standing.fighter_posts(state, data) == [f"raid FIG-001 {XEN_SECTOR} stay"]


def test_with_no_carrier_to_fill_its_fighters_join_patrols_and_escorts(small_state):
    """start9h: SAP-470 kept 36 fighters docked while the Kha'ak shot freighters beside it."""
    state, data = _fighters_ready(small_state, fighters=1)
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"].append(dict(copy.deepcopy(aso), code="CAR-001", cls="ship_xl", macro="ship_arg_xl_carrier_01_a_macro",
                                assignment={"groups": {7: "interception"}}))
    state["assets"] += [dict(copy.deepcopy(aso), code=f"CFT-00{i}", cls="ship_s", macro="ship_tel_s_fighter_01_a_macro",
                             assignment={"group": 7}, orders=[{"order": "Escort", "default": True}]) for i in range(3)]
    for i in range(3):
        state["assigned_to"][f"CFT-00{i}"] = "CAR-001"
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal["fighters_per_carrier"] = 40
    # The plan fills the carrier: only the free one goes, as the patrol's leader.
    assert standing.fighter_posts(state, data) == [f"raid FIG-000 {XEN_SECTOR} stay"]
    state, data = _fighters_ready(small_state, fighters=1)
    state["assets"].append(dict(copy.deepcopy(aso), code="CAR-001", cls="ship_xl", macro="ship_arg_xl_carrier_01_a_macro",
                                assignment={"groups": {7: "interception"}}))
    state["assets"] += [dict(copy.deepcopy(aso), code=f"CFT-00{i}", cls="ship_s", macro="ship_tel_s_fighter_01_a_macro",
                             assignment={"group": 7}, orders=[{"order": "Escort", "default": True}]) for i in range(3)]
    for i in range(3):
        state["assigned_to"][f"CFT-00{i}"] = "CAR-001"
    # No carrier to fill: the free one leads, the carrier's join it and escort.
    assert standing.fighter_posts(state, data) == [f"raid FIG-000 {XEN_SECTOR} stay", "command CFT-000 FIG-000 attack",
                                                   "command CFT-001 TRA-001 defence", "command CFT-002 TRA-001 defence"]


def _frigates_home(state, n):
    home = _station(state)
    home["assignment"]["groups"][3] = "defence"
    for i in range(n):
        _add_ship(state, f"FRI-00{i}", "ship_tel_m_frigate_01_a_macro", cls="ship_m", assignment={"group": 3},
                  place=dict(home["place"]), orders=[{"order": "ProtectStation", "default": True}])


def test_a_frigate_from_home_leads_the_sector_patrol_and_the_route_keeps_its_own(small_state):
    """The player's choice at 410 game hours: 32 light fighters lost to the Kha'ak in a night."""
    state, data = _fighters_ready(small_state, fighters=2)
    assert standing.fighter_posts(state, data) == [f"raid FIG-000 {XEN_SECTOR} stay", "command FIG-001 FIG-000 attack"]
    _frigates_home(state, 2)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(patrol_frigates={XEN_SECTOR: 2}, route_sectors=["S1"],
                                                           route_frigates=1)
    # The route is home and keeps one; the other leads, and the fighters go under it at once.
    assert standing.fighter_posts(state, data) == [f"raid FRI-001 {XEN_SECTOR} stay",
                                                   "release FIG-000", "command FIG-000 FRI-001 attack",
                                                   "release FIG-001", "command FIG-001 FRI-001 attack"]
    # The route patrol does not take the one posted.
    assert standing.route_patrol(state, data) == ["raid FRI-000 S1 ships"]
    # With the route out, the patrol has the other too.
    data["standing"].pop("route")
    data["standing"]["route"] = {"ships": ["XXX-000"]}
    assert standing.fighter_posts(state, data) == ["release FRI-000", "command FRI-000 FRI-001 attack"]


def test_a_frigate_leading_fighters_is_known_again_from_the_save(small_state):
    state, data = _fighters_ready(small_state, fighters=2)
    _frigates_home(state, 1)
    data["strategy"]["plan"]["stations"]["KYV-745"]["patrol_frigates"] = {XEN_SECTOR: 1}
    next(a for a in state["assets"] if a["code"] == "FRI-000").update(
        place={"sector": XEN_SECTOR}, orders=[{"order": "Patrol"}], assignment={"group": 3, "groups": {6: "attack"}})
    next(a for a in state["assets"] if a["code"] == "FIG-000")["assignment"] = {"group": 6}
    state["assigned_to"]["FIG-000"] = "FRI-000"
    assert standing.fighter_posts(state, data) == ["command FIG-001 FRI-000 attack"]
    assert data["standing"]["sector_leader"] == {XEN_SECTOR: "FRI-000"}


def test_fleet_builds_frigates_for_the_patrols_and_leaves_a_posted_one_free(small_state):
    import strategy
    state, data = _fighters_ready(small_state, fighters=0)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal.update(destroyers=0, patrol_frigates={XEN_SECTOR: 2}, patrol_sectors={}, escorts_per_trader=0)
    calls = []
    real = strategy.own_build
    strategy.own_build = lambda state, pattern, size="m", brake=True: calls.append(pattern) or f"build {pattern}"
    try:
        assert strategy.fleet(state, data) == ["build ship_{race}_m_frigate_01_a_macro"]
        _add_ship(state, "FRI-000", "ship_tel_m_frigate_01_a_macro", cls="ship_m")
        assert any("FRI-000" in c for c in strategy.fleet(state, data))
        data["standing"] = {"sector_patrol": {"FRI-000": XEN_SECTOR}}
        assert not any("FRI-000" in c for c in strategy.fleet(state, data))
    finally:
        strategy.own_build = real


def _destroyers_home(state, n):
    home = _station(state)
    home["assignment"]["groups"][3] = "defence"
    for i in range(n):
        _add_ship(state, f"DES-00{i}", "ship_tel_l_destroyer_01_a_macro", cls="ship_l", assignment={"group": 3},
                  place=dict(home["place"]), orders=[{"order": "ProtectStation", "default": True}])


def test_destroyers_above_the_floor_lead_a_sector_patrol(small_state):
    """tasks/plan-2026-11.md 1.2: no destroyer lost to the Kha'ak, nine frigates were."""
    state, data = _fighters_ready(small_state, fighters=2)
    _destroyers_home(state, 4)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(raid_home=2, patrol_destroyers={XEN_SECTOR: 2},
                                                           destroyers=0, raid_sector="")
    assert standing.fighter_posts(state, data) == [f"raid DES-002 {XEN_SECTOR} stay",
                                                   "release DES-003", "command DES-003 DES-002 attack",
                                                   "command FIG-000 DES-002 attack", "command FIG-001 DES-002 attack"]
    # The guard and the raid rule leave them alone.
    next(a for a in state["assets"] if a["code"] == "DES-003")["assignment"] = {"group": 6}
    next(a for a in state["assets"] if a["code"] == "DES-002").update(
        orders=[{"order": "Patrol"}], place={"sector": XEN_SECTOR}, assignment={"group": 3, "groups": {6: "attack"}})
    state["assigned_to"]["DES-003"] = "DES-002"
    data["strategy"]["plan"]["stations"]["KYV-745"].update(destroyers=4, raid_sector="S9")
    assert not any("DES-002" in c or "DES-003" in c for c in standing.raids(state, data))


def test_no_destroyer_patrol_in_a_sector_a_guard_holds(small_state):
    state, data = _fighters_ready(small_state, fighters=0)
    _destroyers_home(state, 4)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(raid_home=2, patrol_destroyers={XEN_SECTOR: 2},
                                                           raid_sector=XEN_SECTOR, patrol_sectors={})
    assert standing.fighter_posts(state, data) == []


def test_a_station_gets_its_own_guard_of_fighters_after_the_patrols(small_state):
    """The player asked for fifteen at ZLR-942 once the fleet's home moved to Silent Witness XI."""
    state, data = _fighters_ready(small_state, fighters=5)
    data["strategy"]["plan"]["stations"]["KYV-745"]["defence_fighters"] = 2
    assert standing.fighter_posts(state, data) == [f"raid FIG-000 {XEN_SECTOR} stay", "command FIG-001 FIG-000 attack",
                                                   "assign FIG-002 KYV-745 defend", "assign FIG-003 KYV-745 defend",
                                                   "command FIG-004 TRA-001 defence"]
    assert standing.fighter_posts(state, data) == []            # each once
    # Once there they count by their commander.
    for code in ("FIG-002", "FIG-003"):
        next(a for a in state["assets"] if a["code"] == code)["assignment"] = {"group": 3}
    _station(state)["assignment"]["groups"][3] = "defence"
    assert standing.fighter_posts(state, data) == []


def test_a_station_without_a_raid_leaves_the_guard_alone(small_state):
    """From 418 game hours ZLR-942 keeps its own destroyers and ZXX-974 has the guard."""
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_sector"] = ""
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader.update(orders=[{"order": "Patrol"}], assignment={"group": 3, "groups": {2: "attack"}})
    next(a for a in state["assets"] if a["code"] == "DES-001")["assignment"] = {"group": 2}
    state["assigned_to"] = {"DES-001": "DES-000"}
    assert standing.raids(state, data) == []


def test_fleet_counts_a_raids_ships_at_its_home_only(small_state):
    import strategy
    state, data = _raid_ready(small_state, destroyers=3)
    for a in state["assets"]:
        if a["code"].startswith("DES-"):
            a["assignment"] = {"group": 9}
    plan = data["strategy"]["plan"]["stations"]
    plan["KYV-745"].update(destroyers=2, raid_sector="")
    data["standing"] = {"raid": {"home": "ZXX-974", "ships": ["DES-000", "DES-001", "DES-002"]}}
    calls = []
    real = strategy.own_build
    strategy.own_build = lambda state, pattern, size="m", brake=True: calls.append(pattern) or None
    try:
        strategy.fleet(state, data)
    finally:
        strategy.own_build = real
    assert "ship_{race}_l_destroyer_01_a_macro" in calls


def test_fleet_counts_ships_on_order_before_it_orders_another(small_state):
    """start9m: three L bays took a destroyer each for ZLR-942's three short, four in all."""
    import strategy
    state, data = _raid_ready(small_state, destroyers=2)
    state["ships_on_order"] = [{"macro": "ship_tel_l_destroyer_01_a_macro", "wharf": "KYV-745",
                                "since": state["meta"]["playtime_s"]}]
    calls = []
    real = strategy.own_build
    strategy.own_build = lambda state, pattern, size="m", brake=True: calls.append(pattern) or None
    try:
        strategy.fleet(state, data)
        assert "ship_{race}_l_destroyer_01_a_macro" not in calls      # two and one coming: three
        state["ships_on_order"] = []
        strategy.fleet(state, data)
        assert "ship_{race}_l_destroyer_01_a_macro" in calls
    finally:
        strategy.own_build = real


def test_a_sector_patrol_is_known_again_from_the_save(small_state):
    """A run starts with no memory: a free fighter on a Patrol in the sector is its patrol."""
    state, data = _fighters_ready(small_state, fighters=3)
    for code in ("FIG-000", "FIG-001"):
        next(a for a in state["assets"] if a["code"] == code).update(orders=[{"order": "Patrol"}],
                                                                    place={"sector": XEN_SECTOR})
    # start9f's seven each on its own Patrol: one leads, the others go under it, a free one joins.
    assert standing.fighter_posts(state, data) == ["release FIG-001", "command FIG-001 FIG-000 attack",
                                                   "command FIG-002 TRA-001 defence"]


def test_fleet_builds_fighters_for_the_patrols_and_escorts(small_state):
    import strategy
    state, data = _fighters_ready(small_state, fighters=0)
    calls = []
    real = strategy.own_build
    strategy.own_build = lambda state, pattern, size="m", brake=True: calls.append(pattern) or None
    try:
        strategy.fleet(state, data)
    finally:
        strategy.own_build = real
    assert "ship_{race}_s_fighter_02_a_macro" in calls


def test_the_bridge_names_an_attackers_faction_by_its_id(small_state):
    md = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/md/x4_agent_bridge.xml").read_text(encoding="utf-8")
    assert "ATTACKED: %s by %s (%s) [%s]" in md and "@event.param.owner.id]" in md
    assert "DESTROYED: %s by %s (%s) [%s]" in md and "@event.param2.owner.id]" in md


def test_a_guard_that_lost_its_patrol_is_told_again_at_once(small_state):
    """start8y: the Pact's base fell, the queue was empty and the guard flew home."""
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(raid_guard=True, raid_faction="scaleplate")
    state["hostiles"] = {}
    state["all_stations"] = [{"code": "PAC-001", "owner": "scaleplate", "sector": XEN_SECTOR}]
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR} stay scaleplate"
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader.update(place={"sector": XEN_SECTOR}, orders=[{"order": "Patrol"}])
    state["all_stations"] = []
    assert standing.raids(state, data) == []                    # posted, nothing left
    leader["orders"] = [{"order": "ProtectStation", "default": True}]
    assert standing.raids(state, data) == [f"raid DES-000 {XEN_SECTOR} stay scaleplate"]


def test_a_guard_posted_on_the_way_to_a_new_raid_sector_goes_on_from_there(small_state):
    """start8p: the guard of Hatikvah's Choice I went on to Silent Witness XI."""
    import purchases
    state, data = _raid_ready(small_state)
    graph, home = purchases._graph(), _station(state)["place"]["sector"]
    target = next(s for s in sorted(graph) if purchases.jumps(graph, home, s) == 2)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(raid_guard=True, raid_faction="scaleplate",
                                                           raid_sector=target)
    on_the_way = next(n for n in graph[home] if purchases.jumps(graph, n, target) == 1)
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader.update(orders=[{"order": "Patrol"}, {"order": "ProtectStation", "default": True}],
                  place={"sector": on_the_way}, assignment={"group": 3, "groups": {2: "attack"}})
    next(a for a in state["assets"] if a["code"] == "DES-001")["assignment"] = {"group": 2}
    state["assigned_to"] = {"DES-001": "DES-000"}
    assert standing.raids(state, data) == ["undock DES-000", f"raid DES-000 {target} stay scaleplate"]
    raid = data["standing"]["raid"]
    assert raid["ships"] == ["DES-000", "DES-001"] and not raid["arrived"] and raid["faction"] == "scaleplate"


def test_a_raid_goes_when_every_destroyer_stands(small_state):
    state, data = _raid_ready(small_state, destroyers=2)
    assert standing.raids(state, data) == []
    state, data = _raid_ready(small_state)
    assert standing.raids(state, data) == ["command DES-001 DES-000 attack", "command DES-002 DES-000 attack",
                                           f"raid DES-000 {XEN_SECTOR}"]
    assert data["standing"]["raid"]["phase"] == "out"
    assert standing.raids(state, data) == []                      # once


def test_an_unseen_sector_is_raided_only_if_the_plan_says_so_and_looked_at_on_arrival(small_state):
    state, data = _raid_ready(small_state)
    state["hostiles"] = {}
    assert standing.raids(state, data) == []
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_unseen"] = True
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader["place"] = {"sector": XEN_SECTOR}
    state["meta"]["playtime_s"] = 1000
    assert standing.raids(state, data) == []                   # arrived, nothing in sight yet: stays
    state["hostiles"] = {XEN_SECTOR: {"xenon": {"station": 3}}}
    assert standing.raids(state, data) == [f"raid DES-000 {XEN_SECTOR}"]
    assert standing.raids(state, data) == []                   # not at once again
    leader["orders"] = [{"order": "Attack"}]
    state["meta"]["playtime_s"] += standing.RAID_ASK_AGAIN
    assert standing.raids(state, data) == []                   # it is on it
    leader["orders"] = []
    assert standing.raids(state, data) == [f"raid DES-000 {XEN_SECTOR}"]
    state["hostiles"] = {}
    state["meta"]["playtime_s"] += standing.RAID_BACK_WAIT
    assert standing.raids(state, data) == _sent_home("DES-000", "DES-001", "DES-002")  # all gone: back


def test_a_raid_that_finds_too_many_xl_turns_back_and_stays_away(small_state):
    state, data = _raid_ready(small_state)
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"
    next(a for a in state["assets"] if a["code"] == "DES-000")["place"] = {"sector": XEN_SECTOR}
    state["hostiles"][XEN_SECTOR]["xenon"]["ship_xl"] = 1      # 3 destroyers, one XL takes 6
    assert standing.raids(state, data) == _sent_home("DES-000", "DES-001", "DES-002")
    state["meta"]["playtime_s"] += standing.RAID_BACK_WAIT
    standing.raids(state, data)                                # settling
    standing.raids(state, data)                                # settled
    del state["hostiles"][XEN_SECTOR]["xenon"]["ship_xl"]      # out of sight is not gone
    for ship in state["assets"]:
        if ship["code"].startswith("DES-"):
            ship["place"] = dict(_station(state)["place"])
            ship["assignment"] = {"group": 3}
    assert standing.raids(state, data) == []
    state["meta"]["playtime_s"] += standing.RAID_STRONG_WAIT
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"


def test_a_raid_that_chases_out_of_its_sector_comes_home(small_state):
    """start8g: the raid on Hatikvah's Choice I chased Xenon into Tharka's Cascade XV, all seven lost."""
    state, data = _raid_ready(small_state)
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"
    for ship in state["assets"]:
        if ship["code"].startswith("DES-"):
            ship["place"] = {"sector": XEN_SECTOR}
    assert standing.raids(state, data) == [f"raid DES-000 {XEN_SECTOR}"]  # there: told to attack
    next(a for a in state["assets"] if a["code"] == "DES-001")["place"] = {"sector": "XENON_CORE"}
    assert standing.raids(state, data) == _sent_home("DES-000", "DES-001", "DES-002")


def test_a_lost_destroyer_counts_as_damage(small_state):
    state, data = _raid_ready(small_state)
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"
    next(a for a in state["assets"] if a["code"] == "DES-000")["place"] = {"sector": XEN_SECTOR}
    state["assets"] = [a for a in state["assets"] if a["code"] != "DES-002"]
    assert standing.raids(state, data) == _sent_home("DES-000", "DES-001")  # 2 of 3 whole: 0.67, below 0.75


def test_no_raid_without_xenon_seen_there(small_state):
    state, data = _raid_ready(small_state)
    state["hostiles"] = {XEN_SECTOR: {"outlaw": {"ship_s": 1}}}
    assert standing.raids(state, data) == []
    state["hostiles"] = {XEN_SECTOR: {"xenon": {"ship_m": 5}}}    # no station: it goes for the ships
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"


def test_no_raid_on_more_xl_than_the_fleet_can_take(small_state):
    state, data = _raid_ready(small_state)
    state["hostiles"][XEN_SECTOR]["xenon"]["ship_xl"] = 1
    assert standing.raids(state, data) == []                      # 3 destroyers, one XL takes 6


def _with_fighters(state, n):
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"] += [dict(copy.deepcopy(aso), code=f"FIG-00{i}", cls="ship_s", assignment={},
                             macro="ship_tel_s_fighter_02_a_macro",
                             orders=[{"order": "Wait", "state": "started", "default": True}])
                        for i in range(n)]


def test_free_fighters_spread_over_the_destroyers_up_to_the_plan(small_state):
    state, data = _raid_ready(small_state, destroyers=2)
    data["strategy"]["plan"]["stations"]["KYV-745"]["fighters_per_destroyer"] = 1
    _with_fighters(state, 3)
    assert standing.wings(state, data) == ["command FIG-000 DES-000 interception",
                                           "command FIG-001 DES-001 interception"]
    assert standing.wings(state, data) == []
    state["assets"] = [a for a in state["assets"] if a["code"] != "FIG-000"]
    assert standing.wings(state, data) == ["command FIG-002 DES-000 interception"]


def test_a_carrier_is_filled_first_also_from_the_fighters_guarding_home(small_state):
    state, data = _raid_ready(small_state, destroyers=1)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(fighters_per_destroyer=1, fighters_per_carrier=2)
    _add_ship(state, "CAR-000", "ship_arg_xl_carrier_01_a_macro", cls="ship_xl",
              assignment={"groups": {5: "interception"}})
    _with_fighters(state, 4)
    # FIG-000 flew under the carrier in the run before; FIG-001 was made a guard of home.
    next(a for a in state["assets"] if a["code"] == "FIG-000")["assignment"] = {"group": 5}
    next(a for a in state["assets"] if a["code"] == "FIG-001").update(
        assignment={"group": 3}, orders=[{"order": "ProtectStation", "default": True}])
    assert standing.wings(state, data) == ["command FIG-001 CAR-000 interception",
                                           "command FIG-002 DES-000 interception"]
    assert standing.wings(state, data) == []                   # carrier and destroyer full


def test_fighters_without_a_place_patrol_until_a_destroyer_stands(small_state):
    state, data = _raid_ready(small_state, destroyers=1)
    data["strategy"]["plan"]["stations"]["KYV-745"]["fighters_per_destroyer"] = 1
    _with_fighters(state, 3)
    sector = _station(state)["place"]["sector"]
    state["hostiles"] = {sector: {"xenon": {"ship_s": 2}}}
    assert standing.patrols(state, data) == []                 # one place free: `wings` first
    assert standing.wings(state, data) == ["command FIG-000 DES-000 interception"]
    next(a for a in state["assets"] if a["code"] == "FIG-000")["assignment"] = {"group": 1}
    next(a for a in state["assets"] if a["code"] == "FIG-000")["orders"] = [{"order": "Escort"}]
    assert standing.patrols(state, data) == ["patrol FIG-001 KYV-745", "patrol FIG-002 KYV-745"]
    assert standing.patrols(state, data) == []                 # once
    for code in ("FIG-001", "FIG-002"):
        next(a for a in state["assets"] if a["code"] == code)["orders"] = [{"order": "Patrol", "default": True}]
    assert standing.wings(state, data) == []                   # the one destroyer is full
    state["assets"].append(dict(copy.deepcopy(next(a for a in state["assets"] if a["code"] == "DES-000")),
                                code="DES-001"))
    assert standing.wings(state, data) == ["command FIG-001 DES-001 interception"]


def test_a_fighter_left_waiting_under_a_leader_gets_its_orders(small_state):
    state, data = _raid_ready(small_state, destroyers=2)
    data["strategy"]["plan"]["stations"]["KYV-745"]["fighters_per_destroyer"] = 1
    _with_fighters(state, 1)
    next(a for a in state["assets"] if a["code"] == "FIG-000")["assignment"] = {"group": 1}
    assert standing.wings(state, data) == ["command FIG-000 DES-000 interception"]
    assert standing.wings(state, data) == []


def test_destroyers_left_under_a_leader_by_an_ended_run_go_back_to_the_station(small_state):
    state, data = _raid_ready(small_state, destroyers=2)
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader["assignment"] = {"group": 3, "groups": {2: "attack"}}
    next(a for a in state["assets"] if a["code"] == "DES-001")["assignment"] = {"group": 2}
    state["assigned_to"] = {"DES-001": "DES-000"}
    assert standing.raids(state, data) == ["assign DES-001 KYV-745 defend"]


def _guarding(state, data):
    data["strategy"]["plan"]["stations"]["KYV-745"]["raid_guard"] = True
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR} stay"
    next(a for a in state["assets"] if a["code"] == "DES-000")["place"] = {"sector": XEN_SECTOR}
    state["meta"]["playtime_s"] = data["standing"]["raid"]["since"] + 1


def test_a_guard_stays_when_no_xenon_is_left(small_state):
    state, data = _raid_ready(small_state)
    _guarding(state, data)
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader["orders"] = [{"order": "Patrol"}]
    state["hostiles"] = {}
    state["meta"]["playtime_s"] += 2 * standing.RAID_BACK_WAIT
    assert standing.raids(state, data) == []
    assert data["standing"]["raid"]["phase"] == "out"


def test_a_guard_without_a_patrol_is_given_one(small_state):
    state, data = _raid_ready(small_state)
    _guarding(state, data)
    next(a for a in state["assets"] if a["code"] == "DES-000")["orders"] = []
    state["hostiles"] = {}
    assert standing.raids(state, data) == [f"raid DES-000 {XEN_SECTOR} stay"]


def test_a_guard_on_its_post_holds_against_more_than_a_raid_would_go_for(small_state):
    state, data = _raid_ready(small_state, destroyers=5)
    _guarding(state, data)
    state["hostiles"][XEN_SECTOR]["xenon"]["ship_xl"] = 1
    assert 1 * standing.RAID_PER_XL > 5 >= 1 * standing.RAID_HOLD_PER_XL
    assert not any(c.startswith("release") for c in standing.raids(state, data))
    assert data["standing"]["raid"]["phase"] == "out"
    state["hostiles"][XEN_SECTOR]["xenon"]["ship_xl"] = 2
    assert "release DES-000" in standing.raids(state, data)


def test_a_guard_on_its_post_is_topped_up_from_home_with_the_reserve_kept(small_state):
    state, data = _raid_ready(small_state, destroyers=5)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal.update(destroyers=5, raid_from=2, raid_home=1)
    _guarding(state, data)
    assert data["standing"]["raid"]["ships"] == ["DES-000", "DES-001"]
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR} stay"
    goal["raid_from"] = 4
    assert standing.raids(state, data) == ["command DES-002 DES-000 attack", "command DES-003 DES-000 attack"]
    assert data["standing"]["raid"]["ships"][-2:] == ["DES-002", "DES-003"]
    goal["raid_from"] = 6                                       # DES-004 is the reserve
    assert not any(c.startswith("command") for c in standing.raids(state, data))


def test_a_carrier_with_its_wing_full_and_an_auxiliary_go_with_the_guard(small_state):
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["fighters_per_carrier"] = 2
    assert standing.carriers(state, data) == []                # no guard out
    _guarding(state, data)
    _add_ship(state, "CAR-000", "ship_arg_xl_carrier_01_a_macro", cls="ship_xl",
              assignment={"groups": {5: "interception"}})
    _add_ship(state, "ATL-000", "ship_arg_xl_resupplier_01_a_macro", cls="ship_xl")
    _with_fighters(state, 2)
    next(a for a in state["assets"] if a["code"] == "FIG-000")["assignment"] = {"group": 5}
    assert standing.carriers(state, data) == ["command ATL-000 DES-000 supplyfleet"]   # wing 1 of 2
    next(a for a in state["assets"] if a["code"] == "FIG-001")["assignment"] = {"group": 5}
    assert standing.carriers(state, data) == ["command CAR-000 DES-000 defence"]
    assert standing.carriers(state, data) == []
    data["standing"]["raid"]["leader"] = "DES-001"                # the next guard
    assert standing.carriers(state, data) == ["command CAR-000 DES-001 defence",
                                              "command ATL-000 DES-001 supplyfleet"]


def _route_ready(state, frigates=2):
    """KYV-745 with whole frigates defending it and a plan for a route patrol of two stops."""
    state, data = _raid_ready(state, destroyers=0)
    home = _station(state)
    for i in range(frigates):
        _add_ship(state, f"FRI-00{i}", "ship_tel_m_frigate_01_a_macro", cls="ship_m", assignment={"group": 3},
                  place=dict(home["place"]), orders=[{"order": "ProtectStation", "default": True}])
    data["strategy"]["plan"]["stations"]["KYV-745"].update(route_sectors=["S1", "S2"], route_frigates=2)
    return state, data


def test_a_route_patrol_goes_out_stop_by_stop_and_back_home(small_state):
    """The player asked for it at 191 game hours, against the Scale Plate Pact on the way to the Teladi."""
    state, data = _route_ready(small_state, frigates=1)
    assert standing.route_patrol(state, data) == []                    # one of two
    state, data = _route_ready(small_state)
    assert standing.route_patrol(state, data) == ["command FRI-001 FRI-000 attack", "raid FRI-000 S1 ships"]
    route = data["standing"]["route"]
    assert route["stops"] == ["S1", "S2", "S1"]
    leader = next(a for a in state["assets"] if a["code"] == "FRI-000")
    leader["place"] = {"sector": "S1"}
    now = state["meta"]["playtime_s"] = route["since"] + 10
    assert standing.route_patrol(state, data) == []                    # arrived, stays a while
    state["meta"]["playtime_s"] = now + standing.ROUTE_DWELL + 1
    assert standing.route_patrol(state, data) == ["undock FRI-000", "raid FRI-000 S2 ships"]
    for stop in ("S2", "S1"):
        leader["place"] = {"sector": stop}
        standing.route_patrol(state, data)
        state["meta"]["playtime_s"] += standing.ROUTE_DWELL + 1
        out = standing.route_patrol(state, data)
    assert out == ["release FRI-000", "release FRI-001", "undock FRI-000",
                   "assign FRI-000 KYV-745 defend", "assign FRI-001 KYV-745 defend"]
    assert "route" not in data["standing"]


def test_a_hurt_route_patrol_comes_home_and_one_left_out_is_taken_over(small_state):
    state, data = _route_ready(small_state)
    standing.route_patrol(state, data)
    next(a for a in state["assets"] if a["code"] == "FRI-001")["hull"] = 0
    assert standing.route_patrol(state, data)[-1] == "assign FRI-001 KYV-745 defend"
    # A new run, with the leader patrolling S2 and one under it.
    state, data = _route_ready(small_state)
    leader = next(a for a in state["assets"] if a["code"] == "FRI-000")
    leader.update(place={"sector": "S2"}, orders=[{"order": "Patrol"}, {"order": "ProtectStation", "default": True}],
                  assignment={"group": 3, "groups": {6: "attack"}})
    next(a for a in state["assets"] if a["code"] == "FRI-001")["assignment"] = {"group": 6}
    state["assigned_to"] = {"FRI-001": "FRI-000"}
    assert standing.route_patrol(state, data) == []
    assert data["standing"]["route"]["ships"] == ["FRI-000", "FRI-001"] and data["standing"]["route"]["stop"] == 1


def _with_destroyers(state, n):
    home = _station(state)
    for i in range(n):
        _add_ship(state, f"DES-00{i}", "ship_tel_l_destroyer_01_a_macro", cls="ship_l", assignment={"group": 3},
                  place=dict(home["place"]), orders=[{"order": "ProtectStation", "default": True}])


def test_a_route_patrol_with_destroyers_is_led_by_one_and_leaves_the_reserve_home(small_state):
    """By 410 game hours Pact and Fallen Families L destroyers on the route killed freighters
    the frigates could not stop: the player chose eight destroyers for the route."""
    state, data = _route_ready(small_state)
    _with_destroyers(state, 3)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(route_destroyers=2, raid_home=2)
    assert standing.route_patrol(state, data) == ["command FRI-000 DES-000 attack", "command FRI-001 DES-000 attack",
                                                  "raid DES-000 S1 ships"]
    # The raid leaves the route's destroyers alone: none called home, none sent.
    state, data = _route_ready(small_state)
    _with_destroyers(state, 3)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal.update(route_destroyers=2, destroyers=3, raid_sector=XEN_SECTOR)
    standing.route_patrol(state, data)
    assert data["standing"]["route"]["ships"] == ["DES-000", "DES-001", "FRI-000", "FRI-001"]
    leader = next(a for a in state["assets"] if a["code"] == "DES-000")
    leader.update(place={"sector": "S1"}, orders=[{"order": "Patrol"}], assignment={"group": 3, "groups": {6: "attack"}})
    next(a for a in state["assets"] if a["code"] == "DES-001").update(place={"sector": "S1"}, assignment={"group": 6})
    state["assigned_to"] = {"DES-001": "DES-000"}
    assert standing.raids(state, data) == []


def test_a_new_run_takes_over_the_route_but_not_a_frigate_leading_fighters(small_state):
    state, data = _route_ready(small_state)
    leader = next(a for a in state["assets"] if a["code"] == "FRI-000")
    leader.update(place={"sector": "S1"}, orders=[{"order": "Patrol"}], assignment={"group": 3, "groups": {6: "attack"}})
    _add_ship(state, "FIG-000", "ship_tel_s_fighter_01_a_macro", cls="ship_s", assignment={"group": 6})
    state["assigned_to"] = {"FIG-000": "FRI-000"}
    assert standing.route_patrol(state, data) == []
    assert "route" not in data["standing"]


def test_a_carrier_guards_the_plans_station_instead_of_flying_with_the_guard(small_state):
    """start8v: three freighters lost near ZXX-974 while the carrier flew with the guard."""
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(fighters_per_carrier=2, carrier_station="KYV-745")
    _guarding(state, data)
    _add_ship(state, "CAR-000", "ship_arg_xl_carrier_01_a_macro", cls="ship_xl",
              assignment={"groups": {5: "interception"}})
    _add_ship(state, "ATL-000", "ship_arg_xl_resupplier_01_a_macro", cls="ship_xl")
    assert standing.carriers(state, data) == ["assign CAR-000 KYV-745 defend", "command ATL-000 DES-000 supplyfleet"]
    assert standing.carriers(state, data) == []


def test_a_guard_leaves_when_outgunned_or_with_an_xl_at_home(small_state):
    state, data = _raid_ready(small_state)
    _guarding(state, data)
    state["hostiles"][XEN_SECTOR]["xenon"]["ship_xl"] = 1
    assert "release DES-000" in standing.raids(state, data)
    state, data = _raid_ready(small_state)
    _guarding(state, data)
    home = _station(state)["place"]["sector"]
    state["hostiles"][home] = {"xenon": {"ship_xl": 1}}
    assert "release DES-000" in standing.raids(state, data)


def test_no_raid_leaves_with_an_xl_at_home(small_state):
    state, data = _raid_ready(small_state)
    state["hostiles"][_station(state)["place"]["sector"]] = {"xenon": {"ship_xl": 1}}
    assert standing.raids(state, data) == []


def test_a_satellite_in_the_sector_lifts_the_strong_wait(small_state):
    state, data = _raid_ready(small_state)
    state["meta"]["playtime_s"] = 5000
    data["standing"] = {"raid_strong": {XEN_SECTOR: 4000}}
    assert standing.raids(state, data) == []
    state["eyes"] = [XEN_SECTOR]
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"


def _watching(state):
    state = copy.deepcopy(state)
    state["meta"]["playtime_s"] = 5000
    state["player"]["occupied_ship"] = None
    state["assets"] = [a for a in state["assets"] if a.get("code") != "TJL-171"]
    state["all_stations"] = [{"code": "AAA-001", "owner": "paranid", "sector": "S", "builds": []},
                             {"code": "BBB-002", "owner": "paranid", "sector": "S", "builds": []},
                             {"code": "XEN-003", "owner": "xenon", "sector": "S", "builds": []}]
    _add_ship(state, "SCO-001", "ship_par_s_scout_01_a_macro", orders=[{"order": "Explore"}], satellites_aboard=5)
    data = {"strategy": {"plan": {"stations": {"KYV-745": {"build": {}, "miners": {}, "traders": 0, "defenders": 0,
                                                           "destroyers": 0, "raid_sector": "",
                                                           "watch_sectors": ["S"]}}}}}
    return state, data


def test_a_watched_sector_gets_two_satellites_by_different_stations(small_state):
    state, data = _watching(small_state)
    assert standing.watch(state, data) == ["release SCO-001", "satellite SCO-001 AAA-001 paranid"]
    assert standing.watch(state, data) == []                   # on its way
    state["meta"]["playtime_s"] += standing.WATCH_AGAIN
    state["satellites"] = {"S": 1}
    assert standing.watch(state, data) == ["release SCO-001", "satellite SCO-001 BBB-002 paranid"]
    state["meta"]["playtime_s"] += standing.WATCH_AGAIN
    state["satellites"] = {"S": 2}
    assert standing.watch(state, data) == []
    state["satellites"] = {"S": 1}                             # one shot down
    assert standing.watch(state, data)[-1] == "satellite SCO-001 AAA-001 paranid"


def test_the_report_tells_who_stands_in_a_watched_sector(small_state):
    import strategy
    state, data = _watching(small_state)
    state["all_stations"][0].update(builds=["l", "xl"], attacked=4990)
    state["satellites"] = {"S": 1}
    state["hostiles"] = {"S": {"xenon": {"ship_xl": 2}}}
    line = next(l for l in strategy.lines(state, data) if l.startswith("watch "))
    for part in ("satellites 1", "'paranid': 2", "AAA-001 l+xl", "'ship_xl': 2", "attacked lately ['AAA-001']"):
        assert part in line


def test_watch_known_puts_eyes_on_the_sectors_with_most_stations_first(small_state):
    state, data = _watching(small_state)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal["watch_sectors"], goal["watch_known"] = [], True
    state["all_stations"] += [{"code": "CCC-004", "owner": "argon", "sector": "T", "builds": []},
                              {"code": "XEN-005", "owner": "xenon", "sector": "X", "builds": []}]
    assert standing.watch(state, data) == ["release SCO-001", "satellite SCO-001 AAA-001 paranid"]
    assert "X" not in data["standing"]["watch"]


def test_a_scout_without_satellites_buys_one_that_has_them(small_state):
    state, data = _watching(small_state)
    next(a for a in state["assets"] if a["code"] == "SCO-001")["satellites_aboard"] = 0
    state["market"] = state.get("market") or []
    import catalog
    option = catalog.Option("buy", "buyship YRD-001 paranid ship_par_s_scout_01_a_macro scout 3000000")
    original = catalog._buy_options
    catalog._buy_options = lambda *a, **k: [option]
    try:
        assert standing.watch(state, data) == [f"{option.command} {standing.SCOUT_SATELLITES}"]
        assert standing.watch(state, data) == []               # on order, not a second one
        state["meta"]["playtime_s"] += standing.SCOUT_DELIVERY + 1
        next(a for a in state["assets"] if a["code"] == "SCO-001")["satellites_aboard"] = 3
        assert standing.watch(state, data)[-1] == "satellite SCO-001 AAA-001 paranid"
    finally:
        catalog._buy_options = original


def test_a_scout_on_its_errand_is_not_sent_again(small_state):
    state, data = _watching(small_state)
    next(a for a in state["assets"] if a["code"] == "SCO-001")["orders"] = [{"order": "DeployObjectAtPosition"}]
    assert standing.watch(state, data) == []


def test_a_guard_going_home_has_its_patrol_taken_off():
    alive = [{"code": "DES-000"}, {"code": "DES-001"}]
    home = standing._fly_home({"guard": True, "leader": "DES-000", "home": "KYV-745"}, alive)
    assert home == ["release DES-000", "release DES-001", "undock DES-000",
                    "assign DES-000 KYV-745 defend", "assign DES-001 KYV-745 defend"]
    plain = standing._fly_home({"leader": "DES-000", "home": "KYV-745"}, alive)
    assert not any(c.startswith("undock") for c in plain)


def test_a_raid_goes_from_its_number_with_more_on_order(small_state):
    state, data = _raid_ready(small_state, destroyers=2)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal["destroyers"] = 5
    assert standing.raids(state, data) == []
    goal["raid_from"] = 2
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"


def test_a_raid_leaves_its_defenders_at_home(small_state):
    state, data = _raid_ready(small_state)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal.update(raid_from=2, raid_home=2)
    assert standing.raids(state, data) == []                   # 3 stand, 4 wanted
    state, data = _raid_ready(small_state, destroyers=4)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(raid_from=2, raid_home=2)
    assert standing.raids(state, data) == ["command DES-001 DES-000 attack", f"raid DES-000 {XEN_SECTOR}"]
    assert data["standing"]["raid"]["ships"] == ["DES-000", "DES-001"]


def test_a_raid_waits_for_its_fighters(small_state):
    state, data = _raid_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["fighters_per_destroyer"] = 1
    assert standing.raids(state, data) == []
    _with_fighters(state, 3)
    for ship in state["assets"]:
        if ship["code"].startswith("FIG-"):
            ship["assignment"] = {"group": 1}      # as a run started from a save finds them, with no wing in memory
    assert standing.raids(state, data)[-1] == f"raid DES-000 {XEN_SECTOR}"


def test_a_hurt_fleet_comes_back_and_defends_again(small_state):
    import gamedata
    state, data = _raid_ready(small_state)
    standing.raids(state, data)
    top = gamedata.ships()["ship_tel_l_destroyer_01_a_macro"]["hull"]
    for ship in state["assets"]:
        if ship["code"].startswith("DES-"):
            ship["hull"] = top * 0.6
            ship["place"] = {"sector": XEN_SECTOR}
    assert standing.raids(state, data) == _sent_home("DES-000", "DES-001", "DES-002")
    assert data["standing"]["raid"]["phase"] == "back"
    assert standing.raids(state, data) == []                      # still on the way
    for ship in state["assets"]:
        if ship["code"].startswith("DES-"):
            ship["place"] = dict(_station(state)["place"])
    assert standing.raids(state, data) == ([f"release DES-00{i}" for i in range(3)]
                                           + [f"assign DES-00{i} KYV-745 defend" for i in range(3)])
    assert data["standing"]["raid"]["phase"] == "settling"        # `fleet` still counts them this cycle
    assert not any("buildship" in c for c in standing.fleet(state, data))
    state["hostiles"] = {}
    assert standing.raids(state, data) == []
    assert "raid" not in data["standing"]


def test_a_raid_ends_when_the_station_is_gone_or_the_leader_is(small_state):
    state, data = _raid_ready(small_state)
    standing.raids(state, data)
    state["hostiles"] = {}
    assert standing.raids(state, data) == []                      # not there yet: out of sight, not gone
    for ship in state["assets"]:
        if ship["code"].startswith("DES-"):
            ship["place"] = {"sector": XEN_SECTOR}
    assert standing.raids(state, data) == _sent_home("DES-000", "DES-001", "DES-002")
    state, data = _raid_ready(small_state)
    standing.raids(state, data)
    state["meta"]["playtime_s"] += standing.RAID_BACK_WAIT
    assert standing.raids(state, data) == _sent_home("DES-000", "DES-001", "DES-002")     # never got there
    state, data = _raid_ready(small_state)
    standing.raids(state, data)
    state["assets"] = [a for a in state["assets"] if a["code"] != "DES-000"]
    assert standing.raids(state, data) == _sent_home("DES-001", "DES-002")  # the leader gone: back all the same
    assert data["standing"]["raid"]["leader"] == "DES-001"


def test_no_repair_at_a_yard_among_the_xenon(small_state):
    import gamedata
    state = copy.deepcopy(small_state)
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    aso["hull"] = gamedata.ships()[aso["macro"]]["hull"] * 0.5
    sector = aso["place"]["sector"]
    state["known_stations"] = [{"code": "YRD-001", "owner": "paranid", "builds": ["m"],
                                "place": {"sector": sector}, "offers": []}]
    state["hostiles"] = {sector: {"xenon": {"ship_xl": 1}}}
    assert standing.repairs(state, {}) == []
    state["hostiles"] = {sector: {"xenon": {"ship_s": 3}}}     # a fighter passing is no reason
    assert standing.repairs(state, {}) == ["repair ASO-629 YRD-001 paranid"]


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


def test_a_plans_number_of_scouts_is_the_ceiling_too(small_state):
    """start8s: 15 scouts, the plan's 5, every loss replaced up to the most ever."""
    import copy
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    home = _station(state)
    state["known_stations"].append({"code": "YRD-001", "owner": "argon", "builds": ["m"],
                                    "place": dict(home["place"])})
    state["assets"] = [a for a in state["assets"] if sitrep.ship_type(a.get("macro")) != "scout"]
    for i in range(3):
        _add_ship(state, f"SCT-00{i}", "ship_arg_s_scout_01_a_macro", owner="player",
                  orders=[{"order": "Explore", "default": True, "state": "started"}])
    data = {"strategy": {"plan": {"stations": {"START": {"scouts": 2}}}}, "standing": {"scouts_most": 15}}
    assert not any(c.startswith("buyship") for c in standing.scouts(state, data))
    state["assets"] = [a for a in state["assets"] if a.get("code") not in ("SCT-000", "SCT-001")]
    assert any(c.startswith("buyship") for c in standing.scouts(state, data))    # one left of two


def test_a_plan_buys_the_first_scouts(small_state):
    import copy
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    home = _station(state)
    state["known_stations"].append({"code": "YRD-001", "owner": "argon", "builds": ["m"],
                                    "place": dict(home["place"])})
    state["assets"] = [a for a in state["assets"]
                       if sitrep.ship_type(a.get("macro")) != "scout"]
    data = {"strategy": {"plan": {"stations": {"START": {"scouts": 2}}}}}
    commands = standing.scouts(state, data)
    assert len(commands) == 1 and commands[0].startswith("buyship YRD-001 argon ship_arg_s_scout_01_a_macro")
    assert commands[0].endswith(f" {standing.SCOUT_SATELLITES}")


def test_with_no_station_the_first_scout_comes_from_a_wharf_near_the_player(small_state):
    import copy
    state = copy.deepcopy(small_state)
    state["player"]["money"] = 50_000_000
    place = dict(_station(state)["place"])
    _add_ship(state, "OUR-001", "ship_gen_m_corvette_01_macro", owner="player")
    state["assets"] = [a for a in state["assets"] if a["code"] == "OUR-001"]
    state["assets"][0]["place"] = place
    state["player"]["occupied_ship"] = "OUR-001"
    state["known_stations"] = [{"code": "YRD-001", "owner": "argon", "builds": ["m"], "place": dict(place)}]
    data = {"strategy": {"plan": {"stations": {"START": {"scouts": 5}}}}}
    assert standing.scouts(state, data)[0].startswith("buyship YRD-001 argon ship_arg_s_scout_01_a_macro")
    assert standing.shelter(state, data)[-1] == "autopilot YRD-001 argon"


def _scouts_spreading(small_state):
    import copy
    state = copy.deepcopy(small_state)
    state["meta"]["playtime_s"] = 5000
    state["player"]["money"] = 50_000_000
    state["assets"] = [a for a in state["assets"] if sitrep.ship_type(a.get("macro")) != "scout"]
    state["known_stations"], state["all_stations"] = [], []
    for code in ("SCA-001", "SCB-002"):
        _add_ship(state, code, "ship_arg_s_scout_01_a_macro", owner="player")
        next(a for a in state["assets"] if a["code"] == code)["place"] = {"sector": "cluster_14_sector001_macro"}
    return state, {"strategy": {"plan": {"stations": {"START": {"scouts": 2}}}}}


def test_scouts_go_to_different_unknown_sectors(small_state):
    state, data = _scouts_spreading(small_state)
    commands = standing.scouts(state, data)
    targets = [c.split()[2] for c in commands if c.startswith("scout ")]
    assert len(targets) == 2 and len(set(targets)) == 2
    assert commands[0] == "release SCA-001"
    assert standing.scouts(state, data) == []                 # on their way


def test_a_scout_gets_a_new_sector_after_its_sweep(small_state):
    state, data = _scouts_spreading(small_state)
    standing.scouts(state, data)
    first = data["standing"]["scout_targets"]["SCA-001"]["sector"]
    next(a for a in state["assets"] if a["code"] == "SCA-001")["place"] = {"sector": first}
    state["meta"]["playtime_s"] += standing.SCOUT_SWEEP + 1
    commands = standing.scouts(state, data)
    assert commands[0] == "release SCA-001" and commands[1].split()[2] != first
    assert first in data["standing"]["scouts_visited"]


def test_a_sector_the_game_cannot_find_gets_another_at_once(small_state):
    state, data = _scouts_spreading(small_state)
    standing.scouts(state, data)
    first = data["standing"]["scout_targets"]["SCA-001"]["sector"]
    state["logbook"] = [(5001, f"[x4-agent] REFUSED: scout: SCA-001 found no sector {first} within 40 jumps")]
    commands = standing.scouts(state, data)
    assert commands[0] == "release SCA-001" and commands[1].split()[2] != first
    assert first in data["standing"]["scouts_visited"]


def test_a_scout_placing_a_satellite_is_left_alone(small_state):
    state, data = _scouts_spreading(small_state)
    next(a for a in state["assets"] if a["code"] == "SCA-001")["orders"] = [{"order": "DeployObjectAtPosition"}]
    assert not any("SCA-001" in c for c in standing.scouts(state, data))


def test_the_plans_scouts_are_bought_without_the_wait(small_state):
    state, data = _scouts_spreading(small_state)
    data["strategy"]["plan"]["stations"]["START"]["scouts"] = 4
    place = dict(_station(state)["place"])
    state["known_stations"] = [{"code": "YRD-001", "owner": "argon", "builds": ["m"], "place": place}]
    assert standing.scouts(state, data)[-1].startswith("buyship YRD-001 argon")
    state["ships_on_order"] = [{"macro": "ship_arg_s_scout_01_a_macro", "wharf": "YRD-001", "since": 5000}]
    assert standing.scouts(state, data)[-1].startswith("buyship YRD-001 argon")
    state["ships_on_order"] *= 2
    assert not any(c.startswith("buyship") for c in standing.scouts(state, data))


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


def test_an_l_bay_alone_gets_a_ship_trader_too(small_state):
    """start7: ZLR-942 had only the L bay, and our destroyer sat in its queue
    for 27 game hours with every ware in store."""
    import copy
    import executor
    state = copy.deepcopy(small_state)
    _station(state)["modules"] = _station(state)["modules"] + [executor.EXPANSION_MODULES["wharf_l"][0]]
    assert standing.shiptraders(state, {}) == ["shiptrader KYV-745"]


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


def test_scouts_sweep_the_plans_sectors_to_their_edges_one_each(small_state):
    """At 416 game hours the player saw parts of Silent Witness XII we had never seen."""
    state = copy.deepcopy(small_state)
    here = _station(state)["place"]["sector"]
    for i in range(3):
        _add_ship(state, f"SCO-00{i}", "ship_tel_s_scout_01_a_macro", place={"sector": here}, satellites_aboard=0,
                  orders=[{"order": "Explore", "default": True}])
    data = {"strategy": {"plan": {"stations": {"KYV-745": {"build": {}, "miners": {}, "traders": 0, "defenders": 0,
                                                           "destroyers": 0, "raid_sector": "", "scouts": 2,
                                                           "sweep_sectors": [here, "S2"]}}}}}
    assert standing.sweeps(state, data) == [f"sweep SCO-000 {here}", "sweep SCO-001 S2"]
    assert standing.sweeps(state, data) == []                   # the bridge flies the legs
    # On a leg it is left alone; with its sweep cut short, it is sent again after a while.
    next(a for a in state["assets"] if a["code"] == "SCO-000")["orders"] = [{"order": "MoveWait"}]
    state["meta"]["playtime_s"] += standing.SWEEP_AGAIN
    assert standing.sweeps(state, data) == ["sweep SCO-001 S2"]
    # Exploring, placing satellites and selling leave them alone.
    assert not any("SCO-000" in c or "SCO-001" in c for c in standing.scouts(state, data))
    assert not any("SCO-000" in c or "SCO-001" in c for c in standing.sell_scouts(state, data))
    # Once the bridge has found nothing left, the scout is free again.
    state["logbook"] = [(1.0, f"[x4-agent] SWEPT: {here} by SCO-000")]
    assert standing.sweeps(state, data) == []
    assert data["standing"]["swept"] == [here] and data["standing"]["sweeping"] == {"SCO-001": "S2"}
    md = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/md/x4_agent_bridge.xml").read_text(encoding="utf-8")
    assert "control=\"'sweep_sector'\"" in md and "<find_closest_undiscovered_position" in md
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    assert "sweep = sweep_sector," in lua


def test_a_sweep_that_never_ends_counts_as_done_after_a_while(small_state):
    """start9o to start9v: five sweeps ran 43 game hours and none was SWEPT, so no scout came
    free for Heretic's End and the campaign stood in its scout phase."""
    state = copy.deepcopy(small_state)
    here = _station(state)["place"]["sector"]
    _add_ship(state, "SCO-000", "ship_tel_s_scout_01_a_macro", place={"sector": here}, satellites_aboard=0,
              orders=[{"order": "Explore", "default": True}])
    data = {"strategy": {"plan": {"stations": {"KYV-745": {"build": {}, "miners": {}, "traders": 0, "defenders": 0,
                                                           "destroyers": 0, "raid_sector": "",
                                                           "sweep_sectors": [here, "S2"]}}}}}
    assert standing.sweeps(state, data) == [f"sweep SCO-000 {here}"]
    state["meta"]["playtime_s"] += standing.SWEEP_FOR - 1
    assert standing.sweeps(state, data) == [f"sweep SCO-000 {here}"]          # still on it, sent again
    state["meta"]["playtime_s"] += 1
    assert standing.sweeps(state, data) == ["sweep SCO-000 S2"]               # given up: on to the next
    assert data["standing"]["swept"] == [here]


def test_empty_scouts_beyond_the_plan_are_sold_at_a_wharf_of_their_race(small_state):
    """The player's call: 31 scouts flew at 363 game hours, 30 of them empty, for a plan of five."""
    state = copy.deepcopy(small_state)
    sector = _station(state)["place"]["sector"]
    _add_ship(state, "SCO-001", "ship_tel_s_scout_01_a_macro", satellites_aboard=5)
    for i in range(2, 6):
        _add_ship(state, f"SCO-00{i}", "ship_tel_s_scout_01_a_macro", satellites_aboard=0)
    state["known_stations"] = [{"code": "ARG-001", "owner": "argon", "builds": ["s", "m"], "place": {"sector": sector}},
                               {"code": "TEL-001", "owner": "teladi", "builds": ["m"], "place": {"sector": sector}}]
    data = {"strategy": {"plan": {"stations": {"KYV-745": {"build": {}, "miners": {}, "traders": 0, "defenders": 0,
                                                           "destroyers": 0, "raid_sector": "", "scouts": 2}}}}}
    # The one with satellites and one empty one stay, the plan's two.
    assert standing.sell_scouts(state, data) == [f"sellship SCO-00{i} TEL-001 teladi" for i in (3, 4, 5)]
    assert standing.sell_scouts(state, data) == []              # each once


def test_a_station_with_a_dock_and_no_pier_gets_a_pier(small_state, monkeypatch):
    """The player's call: ZXX-974's own destroyers could not dock at their wharf."""
    import copy
    import catalog
    import executor
    state = copy.deepcopy(small_state)
    monkeypatch.setattr(catalog, "_through_gates",
                        lambda action, state: f"expand {action['station_id']} {action['ware']}")
    _station(state)["modules"] = ["dockarea_arg_m_station_01_lowtech_macro", "prod_gen_water_macro"]
    assert standing.docks(state, {}) == ["expand KYV-745 pier"]
    # Not again while a build has it: start9f and start9g put four piers on ZXX-974.
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    pier = executor.EXPANSION_MODULES["pier"][0]
    bs["build"] = {"queue": [], "running": [{"since": 0.0, "sequence": [*_station(state)["modules"], pier]}]}
    assert standing.docks(state, {}) == []
    bs["build"] = {"queue": [[*_station(state)["modules"], pier]], "running": []}
    assert standing.docks(state, {}) == []
    bs["build"] = {}
    _station(state)["modules"].append(pier)
    assert standing.docks(state, {}) == []
    md = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/md/x4_agent_bridge.xml").read_text(encoding="utf-8")
    assert "'expand %s pier'" in md and "macro.pier_tel_harbor_02_macro" in md


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


def test_a_line_of_our_own_feeds_the_build_above_a_keep(small_state):
    """ship8-camp: 1,708 turret components in store, 48 on offer, 12,669 wanted."""
    state = _waiting_on_turrets(small_state, held=1708, wanted=12669)
    st = _station(state)
    st["offers"] = [{"ware": "turretcomponents", "side": "sell", "price": 332, "amount": 48, "desired": None}]
    st["production_queue"] = ["turretcomponents"]
    data = {}
    assert standing.own_stock(state, data) == [
        "traderule KYV-745 turretcomponents sell own", "limit KYV-745 turretcomponents sell 300",
        "tradeware KYV-745 turretcomponents sell on"]
    assert standing.own_stock(state, data) == []
    state = _waiting_on_turrets(small_state, held=1708, wanted=0)
    _station(state)["production_queue"] = ["turretcomponents"]
    assert standing.own_stock(state, data) == [            # it still sells what it makes
        "limit KYV-745 turretcomponents sell clear", "traderule KYV-745 turretcomponents sell default"]


def test_an_offer_of_nothing_does_not_count_as_selling(small_state):
    """ship8-camp: 51,163 hull parts in store, offered 0, a build waiting 21 game hours on 1,785."""
    state = _waiting_on_turrets(small_state, held=51163, wanted=1785)
    _station(state)["offers"] = [{"ware": "turretcomponents", "side": "sell", "price": 168, "amount": 0,
                                  "desired": None}]
    assert standing.own_stock(state, {}) == [
        "traderule KYV-745 turretcomponents sell own", "limit KYV-745 turretcomponents sell 49378",
        "tradeware KYV-745 turretcomponents sell on"]


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
    assert standing.own_stock(_waiting_on_turrets(small_state, held=300), {}) == []
    state = _waiting_on_turrets(small_state)
    _station(state)["offers"].append({"ware": "turretcomponents", "side": "sell", "price": 300,
                                      "amount": 836, "desired": 0})
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


def _sell_ready(small_state):
    """KYV-745 offering 5,000 refined metals at 92, a free freighter, and three buyers: 207 one
    jump away, 180 at home, 100 at home (not worth the trip)."""
    from purchases import _graph
    state = copy.deepcopy(small_state)
    home = _station(state)
    sector = home["place"]["sector"]
    near = _graph()[sector][0]
    home["offers"] = [{"ware": "refinedmetals", "side": "sell", "price": 92, "amount": 5000, "desired": None}]
    buyer = {"cls": "station", "owner": "argon", "offers": []}
    state["known_stations"] = [
        dict(buyer, code="NEA-001", place={"sector": near},
             offers=[{"ware": "refinedmetals", "side": "buy", "price": 207, "amount": 100, "desired": 26000}]),
        dict(buyer, code="HOM-001", place={"sector": sector},
             offers=[{"ware": "refinedmetals", "side": "buy", "price": 180, "amount": 100, "desired": 3000}]),
        dict(buyer, code="LOW-001", place={"sector": sector},
             offers=[{"ware": "refinedmetals", "side": "buy", "price": 100, "amount": 100, "desired": 9000}])]
    _add_ship(state, "VUL-001", "ship_tel_m_trans_container_01_a_macro",
              orders=[{"order": "Wait", "state": "started", "default": True}])
    next(a for a in state["assets"] if a["code"] == "ASO-629")["assignment"] = {"group": 1}   # trades for KYV-745
    data = {"strategy": {"plan": {"stations": {"KYV-745": {"build": {}, "miners": {}, "traders": 0,
                                                           "sell_runs": {"refinedmetals": 1}}}}}}
    return state, data, near


def test_a_sell_run_takes_our_goods_to_the_best_bid_in_reach(small_state):
    """Plan 1.5: ZXX-974 offered refined metals at 92 to 95 while buyers in reach paid 207."""
    state, data, near = _sell_ready(small_state)
    assert standing.sell_runs(state, data) == ["sellrun VUL-001 refinedmetals KYV-745 NEA-001 argon 5000 165"]
    assert data["standing"]["sell_runs"] == {"VUL-001": ["KYV-745", "refinedmetals"]}
    assert standing.sell_runs(state, data) == []                     # the save has not caught up yet
    # Behind an avoided sector the best bid is out of reach: the best in reach is at home.
    state, data, near = _sell_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["avoid_sectors"] = [near]
    assert standing.sell_runs(state, data) == ["sellrun VUL-001 refinedmetals KYV-745 HOM-001 argon 3000 144"]
    # Opened again, it is in reach once more.
    state, data, near = _sell_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"].update(avoid_sectors=[near], open_sectors=[near])
    assert standing.sell_runs(state, data)[0].split()[4] == "NEA-001"
    # A buyer whose offer the bridge did not find (start9u: CFK-259) is passed over a while.
    state, data, near = _sell_ready(small_state)
    state["meta"]["playtime_s"] = 10_000
    state["logbook"] = [[9_000.0, "[x4-agent lua] REFUSED: sellrun: NEA-001 has no buy offer of refinedmetals for VUL-001"]]
    assert standing.sell_runs(state, data)[0].split()[4] == "HOM-001"
    state, data, near = _sell_ready(small_state)
    state["meta"]["playtime_s"] = 9_000 + standing.SELL_SHUN + 1
    state["logbook"] = [[9_000.0, "[x4-agent lua] REFUSED: sellrun: NEA-001 pays 150 for refinedmetals, below 186"]]
    assert standing.sell_runs(state, data)[0].split()[4] == "NEA-001"             # long enough ago
    # One that took a sale of ours lately goes first, though it pays less (start9v: FAA-628).
    state, data, near = _sell_ready(small_state)
    state["meta"]["playtime_s"] = 10_000
    state["logbook"] = [[9_000.0, "[x4-agent lua] ORDER: VUL-002 sells 862 refinedmetals at HOM-001 (queued offer, order 1)"]]
    assert standing.sell_runs(state, data)[0].split()[4] == "HOM-001"
    # One whose offer is there but closed to our ships (start9v: CFK-259) is passed over longer.
    state, data, near = _sell_ready(small_state)
    state["meta"]["playtime_s"] = 9_000 + standing.SELL_SHUN + 1
    state["logbook"] = [[9_000.0, "[x4-agent lua] REFUSED: sellrun: NEA-001 has no buy offer of refinedmetals "
                                  "for VUL-001 (one closed to us, 21964 at 195.28)"]]
    assert standing.sell_runs(state, data)[0].split()[4] == "HOM-001"
    # And still once the line has left the save's logbook, which holds two game hours.
    state["logbook"], data["standing"]["sell_sent"] = [], {}
    state["meta"]["playtime_s"] += 5 * 3600
    assert standing.sell_runs(state, data)[0].split()[4] == "HOM-001"


def test_a_runner_on_its_run_or_with_little_to_sell_waits(small_state):
    state, data, _ = _sell_ready(small_state)
    ship = next(a for a in state["assets"] if a["code"] == "VUL-001")
    ship["orders"].append({"order": "SingleSell", "state": "started"})
    assert standing.sell_runs(state, data) == []
    # One the game never enabled (start9r): the runner goes again.
    ship["orders"][-1]["state"] = "setup"
    data["standing"]["sell_sent"] = {}
    assert standing.sell_runs(state, data)[0].startswith("sellrun VUL-001 ")
    ship["orders"].pop()
    _station(state)["offers"][0]["amount"] = standing.SELL_FROM - 1
    data["standing"]["sell_sent"] = {}
    assert standing.sell_runs(state, data) == []
    assert data["standing"]["sell_runs"] == {"VUL-001": ["KYV-745", "refinedmetals"]}
    # Loaded, it goes to sell whatever the station still offers: one leg a call.
    ship["cargo"] = {"refinedmetals": 862}
    assert standing.sell_runs(state, data)[0].startswith("sellrun VUL-001 refinedmetals KYV-745 NEA-001 ")


def test_a_runner_is_no_trader_to_hand_out(small_state):
    import strategy
    state, data, _ = _sell_ready(small_state)
    data["strategy"]["plan"]["stations"]["KYV-745"]["traders"] = 1
    data["standing"] = {"sell_runs": {"VUL-001": ["KYV-745", "refinedmetals"]}}
    assert not [c for c in strategy.fleet(state, data) if "VUL-001" in c]


def test_an_opened_sector_comes_off_the_avoided_list_once(small_state):
    state, data = _raid_ready(small_state)
    goal = data["strategy"]["plan"]["stations"]["KYV-745"]
    goal.update(avoid_sectors=["cluster_29_sector001_macro"], open_sectors=["cluster_29_sector001_macro"])
    assert standing.avoid_sectors(state, data) == ["avoid sector cluster_29_sector001_macro off"]
    assert standing.avoid_sectors(state, data) == []


def test_the_bridge_sells_a_run_whole():
    """A trade order's amount is what stays aboard (order.trade.single.sell.xml)."""
    lua = (Path(__file__).parent.parent / "bridge/x4_agent_bridge/ui/x4agent.lua").read_text(encoding="utf-8")
    table = lua.split("local BARE_HANDLERS = {", 1)[1].split("}", 1)[0]
    assert "sellrun = sell_run" in table
    assert 'trade_order(ship, "SingleSell", ware, buyer, 0, math.floor(floor * 100))' in lua
    assert "trade.isbuyoffer" in lua and "below %d" in lua             # the fallback sale keeps the floor
    # No more than the hold takes, and an order the game would not enable is not left behind.
    run = lua.split("local function sell_run(args)", 1)[1].split("\nend\n", 1)[0]
    assert "amount = math.min(amount, fits)" in run
    # The buy at our own station is its offer queued, as the map menu does: the game did not
    # enable a SingleBuy there (start9s).
    assert "AddTradeToShipQueue(" in run and '"SingleBuy"' not in run
    trade = lua.split("local function trade_order(", 1)[1].split("\nend\n", 1)[0]
    assert "if not C.EnableOrder(ship, index) then" in trade
