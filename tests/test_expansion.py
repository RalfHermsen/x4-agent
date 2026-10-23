"""Expansions need blueprints; builds that cannot pay get topped up."""

import pytest

import executor
from schemas import PlannerResponse


def _expand(ware):
    plan = PlannerResponse.model_validate({
        "assessment": "", "updated_goals": [],
        "actions": [{"type": "expand_station", "station_id": "KYV-745",
                     "ware": ware, "rationale": "test"}]})
    return plan.actions


def test_expand_without_blueprint_is_refused_naming_the_ware(small_state):
    small_state["player"]["blueprints"] = []
    commands, skipped = executor.to_commands(_expand("water"), small_state)
    assert commands == []
    (_, reason), = skipped
    # Water needs its module, and solid storage because the station has none.
    assert "module_gen_prod_water_01" in reason
    assert "solid" in reason


def test_expand_with_blueprints_goes_through(small_state):
    import gamedata
    table = gamedata.modules()
    small_state["player"]["blueprints"] = [
        table["prod_gen_water_macro"]["ware"], table[executor.SOLID_STORAGE]["ware"],
        table[executor.CONNECTOR]["ware"]]
    commands, skipped = executor.to_commands(_expand("water"), small_state)
    assert commands == ["expand KYV-745 water"], skipped


def test_no_solid_storage_needed_when_station_has_some(small_state):
    import gamedata
    station = next(a for a in small_state["assets"] if a["code"] == "KYV-745")
    station["capacity"] = {"container": 50000, "solid": 100000}
    small_state["player"]["blueprints"] = [gamedata.modules()["prod_gen_water_macro"]["ware"],
                                           gamedata.modules()[executor.CONNECTOR]["ware"]]
    commands, _ = executor.to_commands(_expand("water"), small_state)
    assert commands == ["expand KYV-745 water"]


def _building(state, cost_units=100, unit_price=1000.0, balance=None, money=200_000):
    state["player"]["money"] = money
    bs = next(a for a in state["assets"] if a["cls"] == "buildstorage")
    bs["build"] = {"queued": 0, "in_progress": 1, "builders": [], "processor": {}}
    bs["offers"] = [{"ware": "hullparts", "side": "buy", "price": unit_price,
                     "amount": cost_units, "desired": cost_units}]
    bs["account"] = {"own": "1"} if balance is None else {"own": "1", "amount": str(balance)}
    return state


def test_a_running_build_short_of_money_is_funded(small_state):
    state = _building(small_state)                    # wants 100,000 Cr, has none
    assert executor.funding(state, {}) == ["buildfund KYV-745"]


def test_no_funding_when_balance_covers_it(small_state):
    state = _building(small_state, balance=150_000)
    assert executor.funding(state, {}) == []


def test_no_funding_without_a_build(small_state):
    state = _building(small_state)
    next(a for a in state["assets"] if a["cls"] == "buildstorage")["build"]["in_progress"] = 0
    assert executor.funding(state, {}) == []


def test_a_build_storage_is_funded_once_a_game_hour(small_state):
    state = _building(small_state)
    funded = {}
    assert executor.funding(state, funded) == ["buildfund KYV-745"]
    assert executor.funding(state, funded) == []
    state["meta"]["playtime_s"] += 300           # a newer save, too soon
    assert executor.funding(state, funded) == []
    state["meta"]["playtime_s"] += executor.FUND_WAIT
    assert executor.funding(state, funded) == ["buildfund KYV-745"]


def test_a_queued_build_is_funded_before_its_vessel_comes(small_state):
    state = _building(small_state, balance=0)
    bs = next(a for a in state["assets"] if a["cls"] == "buildstorage")
    bs["build"] = {"queued": 1, "in_progress": 0, "builders": [], "processor": {}}
    bs["offers"] = []                              # a queued build offers nothing
    assert executor.funding(state, {}) == ["buildfund KYV-745"]


def test_a_production_module_needs_the_connector_blueprint(small_state):
    import gamedata
    table = gamedata.modules()
    station = next(a for a in small_state["assets"] if a["code"] == "KYV-745")
    station["capacity"] = {"container": 50000, "solid": 100000}
    small_state["player"]["blueprints"] = [table["prod_gen_water_macro"]["ware"]]
    commands, skipped = executor.to_commands(_expand("water"), small_state)
    assert commands == [] and table[executor.CONNECTOR]["ware"] in skipped[0][1]
