"""Buying a blueprint as a job: choosing, the stages, stalls, and the guards."""

import copy
import json

import pytest

import memory
import purchases

WARE = "module_tel_conn_vertical_01"
TABLE = {"struct_tel_vertical_01_macro": {"ware": WARE, "owners": ["teladi"],
                                          "licence": "station_gen_basic",
                                          "maxprice": 73227, "cargo": {}}}
SECTOR = "cluster_19_sector001_macro"
GRAPH = {SECTOR: ["far_sector"], "far_sector": [SECTOR]}


def _with_teladi_station(state, code="ZIR-755", sector=SECTOR, keep=False):
    """A market of exactly the stations a test adds. The small save already
    knows a Teladi station in its own sector, which would win every choice."""
    state = copy.deepcopy(state)
    if not keep:
        state["known_stations"] = []
    state["known_stations"].append({"code": code, "owner": "teladi", "cls": "station",
                                    "place": {"sector": sector}, "offers": []})
    return state


def _ship(state, code):
    return next(a for a in state["assets"] if a["code"] == code)


def test_parser_knows_the_occupied_ship(small_state):
    assert small_state["player"]["occupied_ship"] == "TJL-171"


def test_never_the_occupied_ship_and_never_a_miner(small_state):
    state = _with_teladi_station(small_state)
    pick, reason = purchases.choose(WARE, state, {}, TABLE, GRAPH)
    assert reason is None
    assert pick == {"faction": "teladi", "station": "ZIR-755", "ship": "ASO-629", "jumps": 0,
                    "licence": None}
    _ship(state, "ASO-629")["macro"] = "ship_arg_m_miner_solid_01_a_macro"
    pick, reason = purchases.choose(WARE, state, {}, TABLE, GRAPH)
    assert pick is None and "no ship of ours is free" in reason


def test_nearest_station_wins(small_state):
    state = _with_teladi_station(small_state, "FAR-001", "far_sector")
    state = _with_teladi_station(state, "NEAR-01", SECTOR, keep=True)
    pick, _ = purchases.choose(WARE, state, {}, TABLE, GRAPH)
    assert pick["station"] == "NEAR-01"


def test_a_faction_bought_from_before_wins(small_state):
    state = _with_teladi_station(small_state, "NEAR-01", SECTOR)
    state["known_stations"].append({"code": "ARG-001", "owner": "argon", "cls": "station",
                                    "place": {"sector": SECTOR}, "offers": []})
    table = copy.deepcopy(TABLE)
    table["struct_tel_vertical_01_macro"]["owners"] = ["argon", "teladi"]
    pick, _ = purchases.choose(WARE, state, {"blueprint_factions": ["teladi"]}, table, GRAPH)
    assert pick["faction"] == "teladi"


def test_job_walks_to_done(small_state):
    state = _with_teladi_station(small_state)
    data = {}
    first, reason = purchases.start(data, WARE, state, TABLE, GRAPH)
    assert reason is None and first == "dockat ASO-629 ZIR-755 teladi"
    assert purchases.ships_in_use(data) == {"ASO-629"}

    commands, lines = purchases.advance(data, state)          # not docked yet
    assert commands == [] and lines == []

    _ship(state, "ASO-629")["docked_at"] = "ZIR-755"
    commands, _ = purchases.advance(data, state)
    assert commands == [f"blueprint {WARE} ASO-629"]
    assert data["purchases"][WARE]["stage"] == "buying"

    state["player"]["blueprints"] = state["player"]["blueprints"] + [WARE]
    commands, lines = purchases.advance(data, state)
    assert commands == ["release ASO-629"]
    assert lines == [f"bought the blueprint {WARE} from teladi at ZIR-755; ASO-629 released"]
    assert data["purchases"] == {} and data["blueprint_factions"] == ["teladi"]


def test_a_second_purchase_where_the_ship_lies_buys_at_once_and_keeps_it(small_state):
    # ship7-camp: the engine after the miner at WLI-542. The finished job's
    # `release` and the next one's `clear` and `dockat` went out in one cycle;
    # the dockat to where the ship lay ended at once, it went back to trading,
    # and the engine was given up an hour later.
    state = _with_teladi_station(small_state)
    state["player"]["money"] = 50_000_000
    miner, engine = "ship_tel_m_miner_solid_01_a", "engine_tel_m_allround_01_mk1"
    data = {}
    purchases.start(data, miner, state, TABLE, GRAPH)
    ship = _ship(state, "ASO-629")
    ship["docked_at"] = "ZIR-755"
    ship["orders"] = [{"order": "DockAndWait", "default": False}]
    purchases.advance(data, state)
    state["player"]["blueprints"] = state["player"]["blueprints"] + [miner]
    commands, _ = purchases.advance(data, state)
    assert commands == ["release ASO-629"]
    first, reason = purchases.start(data, engine, state, TABLE, GRAPH)
    assert reason is None and first == f"blueprint {engine} ASO-629"
    assert data["purchases"][engine]["stage"] == "buying"
    commands += purchases.first_commands(data, engine, first, state)
    assert purchases.kept(commands, data) == [f"blueprint {engine} ASO-629"]


def test_a_trader_that_only_lies_at_the_station_is_sent_to_dock_first(small_state):
    # ship7b-camp: a trader docked at the seller in the save had moved on to
    # our own station when the `blueprint` order came, and it was refused.
    state = _with_teladi_station(small_state)
    ship = _ship(state, "ASO-629")
    ship["docked_at"] = "ZIR-755"
    ship["orders"] = [{"order": "TradeRoutine", "default": True}]
    first, reason = purchases.start({}, WARE, state, TABLE, GRAPH)
    assert reason is None and first.startswith("dockat ASO-629 ZIR-755")


def test_stall_then_give_up(small_state):
    state = _with_teladi_station(small_state)
    data = {}
    purchases.start(data, WARE, state, TABLE, GRAPH)
    later = copy.deepcopy(state)
    later["meta"]["playtime_s"] += 2000
    _, lines = purchases.advance(data, later)
    assert lines == [f"purchase of {WARE}: docking for 0.6h, ASO-629 not docked at ZIR-755 yet"]
    later["meta"]["playtime_s"] += 2000
    commands, lines = purchases.advance(data, later)
    assert commands == ["release ASO-629"]
    assert "given up" in lines[0] and data["purchases"] == {}


@pytest.mark.parametrize("change,expected", [
    (lambda s: s["player"].__setitem__("money", 75_000), "would leave less than 5%"),
    (lambda s: s["player"].__setitem__("blueprints", [WARE]), "already ours"),
    (lambda s: s.__setitem__("known_stations", []), "no station of teladi is known"),
])
def test_guards(small_state, change, expected):
    state = _with_teladi_station(small_state)
    change(state)
    first, reason = purchases.start({}, WARE, state, TABLE, GRAPH)
    assert first is None and expected in reason


def test_a_thruster_blueprint_is_bought_from_whoever_lists_it(small_state):
    """No thruster has an owner in wares.xml; the representatives of Teladi and
    the Ministry list them (ship7-camp's `offers`), and that is the seller."""
    ware = "thruster_gen_m_allround_01_mk1"
    state = _with_teladi_station(small_state)
    pick, reason = purchases.choose(ware, state, {}, TABLE, GRAPH)
    assert pick is None and "nobody sells" in reason
    t = state["meta"]["playtime_s"]
    state["logbook"] = [[t - 2, f"[x4-agent lua] offers: teladi thruster {ware} at 130190 Cr"],
                        [t - 1, "[x4-agent lua] offers: teladi lists 18 thruster blueprint(s)"]]
    data = {}
    memory.game_refusals(data, state)
    assert data["offered"] == {ware: {"teladi": 130190}}
    # Lines of one moment share a time, and every one counts (ship7b-camp).
    state["logbook"] = [[t, f"[x4-agent lua] offers: {f} thruster {ware} at 130190 Cr"]
                        for f in ("ministry", "alliance")]
    memory.game_refusals(data, state)
    assert data["offered"][ware] == {"teladi": 130190, "ministry": 130190, "alliance": 130190}
    pick, reason = purchases.choose(ware, state, data, TABLE, GRAPH)
    assert reason is None and (pick["faction"], pick["station"]) == ("teladi", "ZIR-755")


def test_game_refusal_reaches_the_report_once(small_state):
    state = copy.deepcopy(small_state)
    t = state["meta"]["playtime_s"]
    state["logbook"] = [[t - 5, "[x4-agent lua] ORDER: ASO-629 docking at ZIR-755 (teladi)"],
                        [t - 1, "[x4-agent lua] REFUSED: blueprint: teladi does not sell x"]]
    data = {}
    assert memory.game_refusals(data, state) == ["the game refused: blueprint: teladi does not sell x"]
    assert memory.game_refusals(data, state) == []


def test_scripted_planner_drives_the_cycle(run_cycle, small_state, tmp_path, monkeypatch):
    import agent
    script = tmp_path / "script.json"
    script.write_text(json.dumps([
        {"assessment": "step one", "updated_goals": ["g"], "actions": []},
        {"assessment": "step two", "updated_goals": ["g"], "actions": []},
    ]), encoding="utf-8")
    monkeypatch.setattr(agent, "SCRIPT", str(script))
    assert run_cycle()["plan"].assessment == "step one"
    assert run_cycle()["plan"].assessment == "step two"
    assert run_cycle()["plan"].assessment == "Script finished."


def test_errand_ship_gets_no_other_orders(run_cycle, small_state, monkeypatch, isolated_memory):
    import agent
    monkeypatch.setattr(agent.executor, "repricing", lambda state: [])
    monkeypatch.setattr(agent.executor, "focus_fleet", lambda state: ["sellware ASO-629 water"])
    isolated_memory.write_text(json.dumps({"purchases": {WARE: {
        "faction": "teladi", "station": "ZIR-755", "ship": "ASO-629", "jumps": 0,
        "stage": "docking", "since": small_state["meta"]["playtime_s"]}}}), encoding="utf-8")
    result = run_cycle()
    assert not any(c.startswith("sellware ASO-629") for c in result["commands"])


# ---- 2.1b: licences --------------------------------------------------------

DEFS = {"teladi": {"station_gen_basic": {"minrelation": -0.01, "precursor": None, "price": None},
                   "tradesubscription": {"minrelation": 0.1, "precursor": "ceremonyally",
                                         "price": 16000000},
                   "station_gen_intermediate": {"minrelation": 0.01, "precursor": "ceremonyfriend",
                                                "price": None}}}


def test_parser_reads_reputation_and_licences(large_state):
    player = large_state["player"]
    assert player["relations"]["teladi"] > 0.1          # base plus boosters
    assert player["relations"]["xenon"] == -1
    assert {"type": "station_gen_basic", "faction": "teladi"} in player["licences"]


def _player(state, licences, relation=0.2):
    state = copy.deepcopy(state)
    state["player"]["licences"] = [{"type": t, "faction": f} for t, f in licences]
    state["player"]["relations"] = {"teladi": relation}
    return state


def test_licence_routes(small_state):
    held = _player(small_state, [("station_gen_basic", "teladi")])
    assert purchases.licence_route("station_gen_basic", "teladi", held, DEFS) == ("held", None)
    route, why = purchases.licence_route("station_gen_intermediate", "teladi", held, DEFS)
    assert route == "no" and "ceremony" in why
    ally = _player(small_state, [("station_gen_basic", "teladi"), ("ceremonyally", "teladi")])
    assert purchases.licence_route("tradesubscription", "teladi", ally, DEFS) == ("buy", None)
    low = _player(small_state, [("ceremonyally", "teladi")], relation=0.05)
    route, why = purchases.licence_route("tradesubscription", "teladi", low, DEFS)
    assert route == "no" and "needs reputation 0.1" in why


def test_job_buys_the_licence_first_when_for_sale(small_state):
    table = copy.deepcopy(TABLE)
    table["struct_tel_vertical_01_macro"]["licence"] = "tradesubscription"
    state = _with_teladi_station(_player(small_state, [("ceremonyally", "teladi")]))
    state["player"]["money"] = 100_000_000
    data = {}
    first, reason = purchases.start(data, WARE, state, table, GRAPH, DEFS)
    assert reason is None and data["purchases"][WARE]["licence"] == "tradesubscription"
    _ship(state, "ASO-629")["docked_at"] = "ZIR-755"
    commands, _ = purchases.advance(data, state)
    assert commands == ["licence tradesubscription ASO-629"]
    state["player"]["licences"].append({"type": "tradesubscription", "faction": "teladi"})
    commands, _ = purchases.advance(data, state)
    assert commands == [f"blueprint {WARE} ASO-629"]


def test_no_job_when_the_licence_comes_with_a_ceremony(small_state):
    table = copy.deepcopy(TABLE)
    table["struct_tel_vertical_01_macro"]["licence"] = "station_gen_intermediate"
    state = _with_teladi_station(_player(small_state, [("station_gen_basic", "teladi")]))
    first, reason = purchases.start({}, WARE, state, table, GRAPH, DEFS)
    assert first is None and "ceremony" in reason


def test_a_ship_blueprint_is_chosen_like_a_module_one_at_ten_times_its_average(small_state):
    import gamedata
    ware = "ship_tel_m_miner_solid_01_a"
    entry = gamedata.blueprint(ware, TABLE)
    assert entry["kind"] == "ship" and "teladi" in entry["owners"]
    assert entry["price"] == 10 * gamedata.wares()[ware]["avgprice"]     # the menu's rule
    pick, reason = purchases.choose(ware, _with_teladi_station(small_state), {}, TABLE, GRAPH)
    assert reason is None and pick["faction"] == "teladi" and pick["station"] == "ZIR-755"
