"""An expansion is followed through its stages, and a stall is reported."""

import copy
import json

import memory

MACRO = "prod_gen_water_macro"


def _states(base):
    """A factory of saves for one water expansion at KYV-745, minutes apart."""
    station = next(a for a in base["assets"] if a["code"] == "KYV-745")
    t0 = base["meta"]["playtime_s"]

    def at(minutes, build=None, offers=(), modules=(), produces=False, processor=None):
        s = copy.deepcopy(base)
        s["meta"]["playtime_s"] = t0 + minutes * 60
        st = next(a for a in s["assets"] if a["code"] == "KYV-745")
        bs = next(a for a in s["assets"] if a["code"] == "XQL-000")
        build = dict(build or {})
        bs["build"] = {"queued": build.get("queued", 0),
                       "in_progress": build.get("in_progress", 0),
                       "builders": build.get("builders", []),
                       "processor": processor or {}}
        bs["offers"] = list(offers)
        st["modules"] = station["modules"] + list(modules)
        if produces:
            st["production_queue"] = station["production_queue"] + ["water"]
        return s
    return at


def _start(data, state):
    memory.start_expansions(data, ["expand KYV-745 water"], state, lambda w: MACRO)


def _stage(data):
    return data["expansions"]["KYV-745 water"]["stage"]


def test_stages_advance_in_order_and_finish(small_state):
    at = _states(small_state)
    data = {"expansions": {}}
    _start(data, at(0))

    assert memory.track_expansions(data, at(5)) == []
    assert _stage(data) == "planned"
    memory.track_expansions(data, at(10, build={"queued": 1}))
    assert _stage(data) == "building"
    memory.track_expansions(data, at(20, build={"in_progress": 1, "builders": ["[0x9]"]},
                                     offers=[{"side": "buy", "ware": "hullparts", "amount": 50}]))
    assert _stage(data) == "vessel"
    memory.track_expansions(data, at(30, build={"in_progress": 1, "builders": ["[0x9]"]}))
    assert _stage(data) == "resources"
    done = memory.track_expansions(data, at(40, modules=[MACRO], produces=True))
    assert done == ["expansion of water at KYV-745 finished: the station produces water"]
    assert "KYV-745 water" not in data["expansions"]


def test_stall_is_reported_as_an_observation(small_state):
    at = _states(small_state)
    data = {"expansions": {}}
    _start(data, at(0))
    assert memory.track_expansions(data, at(20)) == []
    (line,) = memory.track_expansions(data, at(120))
    assert line == "expansion of water at KYV-745: planned for 2.0h, no build started"


def test_stage_never_moves_back(small_state):
    at = _states(small_state)
    data = {"expansions": {}}
    _start(data, at(0))
    memory.track_expansions(data, at(10, build={"in_progress": 1, "builders": ["[0x9]"]}))
    assert _stage(data) == "resources"
    memory.track_expansions(data, at(20))          # build task gone, module not there yet
    assert _stage(data) == "resources"


def test_vessel_stage_from_processor_state(small_state):
    at = _states(small_state)
    data = {"expansions": {}}
    _start(data, at(0))
    memory.track_expansions(data, at(10, build={"in_progress": 1, "builders": ["[0x9]"]},
                                     processor={"state": "waitingforresources"}))
    assert _stage(data) == "vessel"


def test_sent_expansion_is_tracked_by_the_cycle(run_cycle, fake_planner, small_state,
                                                isolated_memory):
    import gamedata
    table = gamedata.modules()
    small_state["player"]["blueprints"] = [table[MACRO]["ware"],
                                           table["storage_tel_m_solid_01_macro"]["ware"],
                                           table["struct_arg_cross_01_macro"]["ware"]]
    fake_planner.plan["actions"] = [{"type": "expand_station", "station_id": "KYV-745",
                                     "ware": "water", "rationale": "test"}]
    result = run_cycle(small_state)
    assert "expand KYV-745 water" in result["commands"]
    stored = json.loads(isolated_memory.read_text(encoding="utf-8"))
    assert stored["expansions"]["KYV-745 water"]["stage"] == "planned"


def test_a_dock_is_done_when_it_stands(small_state):
    # GKL-870's dock stood for 20 game hours while the report called it queued:
    # a dock or a store produces nothing, so it never showed in production.
    import executor
    data = {"expansions": {}}
    memory.start_expansions(data, ["expand KYV-745 dock"], small_state,
                            lambda w: executor.EXPANSION_MODULES[w][0])
    later = copy.deepcopy(small_state)
    later["meta"]["playtime_s"] += 600
    station = next(a for a in later["assets"] if a["code"] == "KYV-745")
    station["modules"] = station["modules"] + ["dockarea_arg_m_station_01_lowtech_macro"]
    (line,) = memory.track_expansions(data, later)
    assert "finished" in line and not data["expansions"]
