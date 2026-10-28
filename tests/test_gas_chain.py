"""Shipbuilding step 2: the gas chain, and the stores an expansion brings."""

import copy
import re
from pathlib import Path

import executor
import gamedata
import strategy

BRIDGE = Path(__file__).resolve().parents[1] / "bridge" / "x4_agent_bridge" / "md" / "x4_agent_bridge.xml"


def _station(state, code="KYV-745"):
    return next(a for a in state["assets"] if a.get("code") == code)


def test_python_and_the_bridge_know_the_same_expansions():
    text = BRIDGE.read_text(encoding="utf-8")
    in_bridge = set(re.findall(r"'expand %s ([a-z_]+)'", text))
    assert in_bridge == set(executor.EXPANSION_MODULES)


def test_a_gas_module_brings_a_liquid_store_where_there_is_none(small_state):
    station = copy.deepcopy(_station(small_state))
    station["capacity"] = {"container": 1000, "solid": 1000}
    assert executor.LIQUID_STORAGE in executor.modules_needed(station, "graphene")
    station["capacity"]["liquid"] = 1000
    assert executor.LIQUID_STORAGE not in executor.modules_needed(station, "graphene")
    assert executor.LIQUID_STORAGE not in executor.modules_needed(station, "refinedmetals")


def test_a_production_module_brings_a_container_store_where_there_is_none(small_state):
    station = copy.deepcopy(_station(small_state))
    station["capacity"] = {"solid": 1000}
    assert executor.CONTAINER_STORAGE in executor.modules_needed(station, "water")
    assert executor.CONTAINER_STORAGE not in executor.modules_needed(station, "dock")


def test_a_planned_gas_module_buys_the_liquid_store_blueprint_too(small_state, monkeypatch):
    import purchases
    state = copy.deepcopy(small_state)
    station = _station(state)
    station["capacity"] = {k: v for k, v in (station.get("capacity") or {}).items() if k != "liquid"}
    modules = gamedata.modules()
    graphene = modules["prod_gen_graphene_macro"]["ware"]
    store = modules[executor.LIQUID_STORAGE]["ware"]
    connector = modules[executor.CONNECTOR]["ware"]
    state["player"]["blueprints"] = list(state["player"].get("blueprints") or []) + [graphene, connector]
    asked = []
    monkeypatch.setattr(purchases, "start", lambda data, ware, state: (asked.append(ware) or "first", None))
    monkeypatch.setattr(purchases, "first_commands", lambda data, ware, first, state: [f"buy {ware}"])
    data = {"strategy": {"plan": {"stations": {"KYV-745": {"build": {"graphene": 1}, "miners": {}, "traders": 0}}}}}
    assert strategy.blueprints(state, data) == [f"buy {store}"]


def test_a_plan_counts_a_wharf_by_its_bay(small_state):
    station = copy.deepcopy(_station(small_state))
    assert strategy.built(station, "wharf") == 0
    station["modules"] = list(station["modules"]) + [executor.EXPANSION_MODULES["wharf"][0]]
    assert strategy.built(station, "wharf") == 1
    assert strategy.built(station, "maintenance") == 0


def test_a_plan_counts_defence_modules(small_state):
    station = copy.deepcopy(_station(small_state))
    assert strategy.built(station, "defence") == 0
    station["modules"] = list(station["modules"]) + [executor.EXPANSION_MODULES["defence"][0]]
    assert strategy.built(station, "defence") == 1


def test_a_defence_module_is_armed_from_blueprints_we_hold():
    text = BRIDGE.read_text(encoding="utf-8")
    block = text[text.index('<do_if value="$agent_module.isclass.defencemodule">'):]
    block = block[:block.index("<write_to_logbook")]
    # A list of wares, not requireblueprints: without one the player
    # faction's default items are used, and it has none. Turrets only, as
    # shield components are not to be had yet.
    assert 'tags="tag.turret"' in block and 'tags="tag.shield"' not in block
    assert "player.blueprints.{$agent_w}.any.exists" in block
    assert 'wares="$agent_equipment"' in block and "requireblueprints" not in block
    assert "<apply_loadout" in block
