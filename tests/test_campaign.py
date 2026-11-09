"""The campaign: one faction at a time, its sectors one by one (tasks/plan-2026-11.md, phase 2)."""

import copy

import executor
import standing
import strategy

BASE = {"build": {"wharf_l": 1, "dock": 1}, "miners": {"solid": 2}, "traders": 3, "defenders": 0,
        "destroyers": 0, "raid_sector": ""}


def _plan(state):
    home = next(a for a in state["assets"] if a["code"] == "KYV-745")
    goal = {"build": {}, "miners": {}, "traders": 0, "defenders": 0, "destroyers": 3, "raid_sector": "S9",
            "raid_home": 0, "raid_from": 1}
    spec = {"faction": "scaleplate", "sectors": ["S1", "S2"], "home": "KYV-745", "garrison": 3,
            "hold_hours": 10, "plot_cap": 20_000_000, "base": BASE}
    return home, {"strategy": {"plan": {"stations": {"KYV-745": goal}, "campaign": spec}}}


def _ship(state, code, sector, **extra):
    base = copy.deepcopy(next(a for a in state["assets"] if a["code"] == "ASO-629"))
    base.update(code=code, macro="ship_tel_l_destroyer_01_a_macro", cls="ship_l", place={"sector": sector},
                orders=[{"order": "Patrol"}], assignment={}, **extra)
    state["assets"].append(base)


def test_a_base_goes_on_with_its_claim_and_one_disc(small_state):
    """start9y/9z: DBA-060 waited for 76 turret components with 1 of 4 discs, and the campaign
    stood in its base phase."""
    state = copy.deepcopy(small_state)
    home, data = _plan(state)
    data["strategy"]["plan"]["campaign"]["base"] = dict(BASE, build={"wharf_l": 1, "dock": 1, "defence": 4})
    data["campaign"] = {"faction": "scaleplate", "sector": "S1", "phase": "base", "base": "KYV-745",
                        "taken": [], "bases": {"KYV-745": "S1"}, "since": 0}
    home["modules"] = [*home["modules"], executor.EXPANSION_MODULES["wharf_l"][0]]
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "base"                         # no disc yet
    home["modules"].append(executor.EXPANSION_MODULES["defence"][0])
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "patrol"


def test_a_sector_the_plan_drops_is_skipped(small_state):
    """start10c: ZTU-930 killed the guard of 31 in Loomanckstrat's Legacy; the plan dropped it."""
    state = copy.deepcopy(small_state)
    _, data = _plan(state)
    data["strategy"]["plan"]["campaign"]["sectors"] = ["S0", "S2"]
    data["campaign"] = {"faction": "scaleplate", "sector": "S1", "phase": "siege", "since": 0,
                        "taken": ["S0"], "bases": {"KYV-745": "S0"}, "worth": 1}
    standing.campaign(state, data)
    at = data["campaign"]
    assert (at["sector"], at["phase"], at["taken"], at["bases"]) == ("S2", "scout", ["S0"], {"KYV-745": "S0"})


def test_the_goals_follow_the_phase(small_state):
    state = copy.deepcopy(small_state)
    _, data = _plan(state)
    data["campaign"] = {"faction": "scaleplate", "sector": "S1", "phase": "scout", "taken": [], "bases": {}}
    home = strategy.goals(data)["KYV-745"]
    assert "S1" in home["sweep_sectors"] and "S1" in home["watch_sectors"] and home["raid_sector"] == "S9"
    data["campaign"]["phase"] = "siege"
    home = strategy.goals(data)["KYV-745"]
    assert (home["raid_sector"], home["raid_faction"], home["raid_guard"]) == ("S1", "scaleplate", True)
    assert data["strategy"]["plan"]["stations"]["KYV-745"]["raid_sector"] == "S9"     # the plan itself untouched
    data["campaign"].update(phase="patrol", bases={"NEW-001": "S1"}, taken=["S0"])
    goals = strategy.goals(data)
    assert goals["KYV-745"]["raid_sector"] == "" and goals["KYV-745"]["patrol_destroyers"] == {"S1": 3}
    assert goals["NEW-001"] == BASE


def test_a_campaign_goes_from_scout_to_the_next_sector(small_state):
    state = copy.deepcopy(small_state)
    home, data = _plan(state)
    state["meta"]["playtime_s"] = 1000.0
    assert standing.campaign(state, data) == []
    assert (data["campaign"]["sector"], data["campaign"]["phase"]) == ("S1", "scout")
    # Swept, and what we know there settled: the siege.
    data["standing"] = {"swept": ["S1"]}
    standing.campaign(state, data)
    state["meta"]["playtime_s"] += standing.SCOUT_SETTLED
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "siege"
    # A guard posted elsewhere comes home first.
    _ship(state, "DES-000", "S9")
    data["standing"]["raid"] = {"sector": "S9", "home": "KYV-745", "home_sector": home["place"]["sector"],
                                "leader": "DES-000", "ships": ["DES-000"], "phase": "out", "since": 0,
                                "guard": True}
    assert "undock DES-000" in standing.campaign(state, data)
    assert data["standing"]["raid"]["phase"] == "back"
    # The target has nothing left there for a while: the claim, a plot by the guard's leader.
    data["standing"]["raid"].update(sector="S1", phase="out")
    next(a for a in state["assets"] if a["code"] == "DES-000")["place"] = {"sector": "S1"}
    standing.campaign(state, data)
    state["meta"]["playtime_s"] += standing.SIEGE_CLEAR
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "claim"
    assert standing.campaign(state, data) == ["newplot DES-000 8 20000000 30000 0 0"]
    assert standing.campaign(state, data) == []                       # once an hour
    # A station of ours stands there: the base, until its first module stands.
    home["place"] = dict(home["place"], sector="S1")
    standing.campaign(state, data)
    assert (data["campaign"]["phase"], data["campaign"]["base"]) == ("base", "KYV-745")
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "base"
    home["modules"] = [*home["modules"], executor.EXPANSION_MODULES["wharf_l"][0]]
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "patrol"
    # The guard goes home; the garrison posted, the gate.
    assert "undock DES-000" in standing.campaign(state, data)
    data["standing"]["sector_patrol"] = {"G1": "S1", "G2": "S1", "G3": "S1"}
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "gate"
    # A ship of ours lost there starts the clock again; held long enough, the next sector.
    data["standing"]["where"] = {"TRA-009": ["S1", "container freighter"]}
    clock = data["campaign"]["clock"]
    state["logbook"] = [[clock + 5, "[x4-agent] DESTROYED: TRA-009 by PAC-001 (Scale Plate Pact) [scaleplate]"]]
    state["meta"]["playtime_s"] = clock + 10 * 3600
    standing.campaign(state, data)
    assert data["campaign"]["phase"] == "gate" and data["campaign"]["clock"] == clock + 5
    state["meta"]["playtime_s"] = clock + 5 + 10 * 3600
    standing.campaign(state, data)
    assert data["campaign"]["taken"] == ["S1"]
    standing.campaign(state, data)
    assert (data["campaign"]["sector"], data["campaign"]["phase"]) == ("S2", "scout")
