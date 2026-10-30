"""3.4 roles under a ship, 4.1 build storage feeding, 4.14 assist."""

import copy

import executor
import memory
from schemas import PlannerResponse


def _plan(*actions):
    return PlannerResponse.model_validate({"assessment": "", "updated_goals": [],
                                           "actions": list(actions)}).actions


def _fleet(state):
    state = copy.deepcopy(state)
    fighter = dict(next(a for a in state["assets"] if a["code"] == "TJL-171"),
                   code="FTR-001", macro="ship_arg_s_fighter_01_a_macro",
                   orders=[{"order": "Wait", "state": "started", "default": True}],
                   assignment={})
    leader = dict(fighter, code="LDR-001", macro="ship_arg_m_frigate_01_a_macro")
    state["assets"] += [fighter, leader]
    return state


def test_intercept_under_a_ship_becomes_a_command(small_state):
    state = _fleet(small_state)
    commands, skipped = executor.to_commands(_plan(
        {"type": "assign_ship", "ship_ref": "FTR-001", "station_id": "LDR-001",
         "role": "intercept", "rationale": "t"}), state)
    assert commands == ["command FTR-001 LDR-001 interception"], skipped


def test_freighter_may_not_attack(small_state):
    state = _fleet(small_state)
    commands, skipped = executor.to_commands(_plan(
        {"type": "assign_ship", "ship_ref": "ASO-629", "station_id": "LDR-001",
         "role": "attack", "rationale": "t"}), state)
    assert commands == [] and "not built to fight" in skipped[0][1]


def test_station_roles_stay_with_stations(small_state):
    state = _fleet(small_state)
    commands, skipped = executor.to_commands(_plan(
        {"type": "assign_ship", "ship_ref": "FTR-001", "station_id": "KYV-745",
         "role": "intercept", "rationale": "t"}), state)
    assert commands == [] and "role under a ship" in skipped[0][1]


def test_assist_is_a_ship_role(small_state):
    state = _fleet(small_state)
    commands, _ = executor.to_commands(_plan(
        {"type": "assign_ship", "ship_ref": "ASO-629", "station_id": "LDR-001",
         "role": "assist", "rationale": "t"}), state)
    assert commands == ["command ASO-629 LDR-001 assist"]


def test_assignment_judged_by_group(small_state):
    state = _fleet(small_state)

    def pending():
        return {"pending": [{"command": "command FTR-001 LDR-001 interception", "sent": 0}]}

    assert "not a subordinate" in memory.check(pending(), state)[0]
    ftr = next(a for a in state["assets"] if a["code"] == "FTR-001")
    ldr = next(a for a in state["assets"] if a["code"] == "LDR-001")
    ftr["assignment"] = {"group": 2}
    ldr["assignment"] = {"groups": {2: "interception"}}
    assert memory.check(pending(), state) == []
    ldr["assignment"] = {"groups": {2: "attack"}}
    assert "uses for attack" in memory.check(pending(), state)[0]


def _building(state, offers=True):
    state = copy.deepcopy(state)
    bs = next(a for a in state["assets"] if a["code"] == "XQL-000")
    bs["build"] = {"queued": 0, "in_progress": 1, "builders": [], "processor": {}}
    bs["offers"] = [{"ware": "hullparts", "side": "buy", "price": 200,
                     "amount": 40 if offers else 0, "desired": 40}]
    return state


def test_idle_freighter_feeds_the_build_then_goes_back(small_state):
    feeders = {}
    state = _building(small_state)
    assert executor.feed_build_storages(state, feeders) == ["assign ASO-629 KYV-745 buildstorage"]
    assert executor.feed_build_storages(state, feeders) == []          # once
    done = copy.deepcopy(state)
    next(a for a in done["assets"] if a["code"] == "XQL-000")["build"]["in_progress"] = 0
    assert executor.feed_build_storages(done, feeders) == ["autotrade ASO-629"]
    assert feeders == {}


def test_station_trader_preferred_and_returned_to_trade(small_state):
    state = _building(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["assignment"] = {"groups": {1: "trade"}}
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    aso["assignment"] = {"group": 1}
    feeders = {}
    assert executor.feed_build_storages(state, feeders) == ["assign ASO-629 KYV-745 buildstorage"]
    assert feeders["KYV-745"]["before"] == "trade"


def test_a_ship_left_at_the_build_storage_is_taken_up_or_sent_back(small_state):
    """A run starts with no feeders: a trader a run before lent to the build
    storage counts as this run's feeder while a build runs, and goes back to
    trading when none does (six of GKL-870's sat there after ship7-camp)."""
    state = _building(small_state)
    next(a for a in state["assets"] if a["code"] == "KYV-745")["assignment"] = {"groups": {1: "tradeforbuildstorage"}}
    next(a for a in state["assets"] if a["code"] == "ASO-629")["assignment"] = {"group": 1}
    feeders = {}
    assert executor.feed_build_storages(state, feeders) == []
    assert feeders == {"KYV-745": {"ship": "ASO-629", "before": "trade"}}
    next(a for a in state["assets"] if a["code"] == "XQL-000")["build"]["in_progress"] = 0
    assert executor.feed_build_storages(state, {}) == ["assign ASO-629 KYV-745 trade"]


L_FREIGHTER = "ship_tel_l_trans_container_03_a_macro"
M_FREIGHTER = "ship_par_m_trans_container_01_a_macro"


def _traders(state, *ships):
    """KYV-745 with trade group 1 holding these (code, macro) freighters, in this order."""
    next(a for a in state["assets"] if a["code"] == "KYV-745")["assignment"] = {"groups": {1: "trade"}}
    aso = next(a for a in state["assets"] if a["code"] == "ASO-629")
    state["assets"] = [a for a in state["assets"] if a["code"] != "ASO-629"]
    state["assets"] += [dict(copy.deepcopy(aso), code=code, macro=macro, assignment={"group": 1})
                        for code, macro in ships]
    return state


def test_the_smallest_station_trader_feeds_the_build(small_state):
    """The game's build storage routine wants a seller holding half the hold:
    an L freighter waited 16 h for 1,291 claytronics in one place."""
    state = _traders(_building(small_state), ("SBA-383", L_FREIGHTER), ("BOJ-123", M_FREIGHTER))
    assert executor.feed_build_storages(state, {}) == ["assign BOJ-123 KYV-745 buildstorage"]


def test_a_lent_large_freighter_is_swapped_for_a_smaller_trader(small_state):
    state = _traders(_building(small_state), ("SBA-383", L_FREIGHTER), ("BOJ-123", M_FREIGHTER))
    next(a for a in state["assets"] if a["code"] == "KYV-745")["assignment"] = {
        "groups": {1: "trade", 2: "tradeforbuildstorage"}}
    next(a for a in state["assets"] if a["code"] == "SBA-383")["assignment"] = {"group": 2}
    feeders = {}
    assert executor.feed_build_storages(state, feeders) == [
        "assign SBA-383 KYV-745 trade", "assign BOJ-123 KYV-745 buildstorage"]
    assert feeders == {"KYV-745": {"ship": "BOJ-123", "before": "trade"}}


def test_nothing_to_buy_means_no_feeder(small_state):
    assert executor.feed_build_storages(_building(small_state, offers=False), {}) == []
