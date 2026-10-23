"""3.7: workforce read from the save; habitats of the station's own race."""

import copy

import executor
import memory
from schemas import PlannerResponse


def test_workforce_read_on_the_reference_saves(large_state):
    stations = [a for a in large_state["assets"] if a["cls"] == "station"]
    assert any(sum(st["workforce"]["amount"].values()) > 0 for st in stations)
    assert all(st["workforce"]["capacity"] >= 0 for st in stations)


def test_race_from_the_station_modules(small_state):
    # KYV-745: a Teladi pier, an Argon connector, Teladi production and storage.
    station = next(a for a in small_state["assets"] if a["code"] == "KYV-745")
    assert executor.habitation_race(station) == "tel"


def test_habitation_expansion_is_race_specific_and_gated(small_state):
    import gamedata
    state = copy.deepcopy(small_state)
    plan = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "expand_station", "station_id": "KYV-745", "ware": "habitation", "rationale": "t"}]})
    state["player"]["blueprints"] = []
    commands, skipped = executor.to_commands(plan.actions, state)
    assert commands == [] and "module_tel_hab_s_01" in skipped[0][1]
    state["player"]["blueprints"] = [gamedata.modules()["hab_tel_s_01_macro"]["ware"],
                                     gamedata.modules()[executor.CONNECTOR]["ware"]]
    commands, _ = executor.to_commands(plan.actions, state)
    assert commands == ["expand KYV-745 habitation_tel"]


def test_habitat_done_when_the_module_stands(small_state):
    state = copy.deepcopy(small_state)
    data = {"expansions": {}}
    memory.start_expansions(data, ["expand KYV-745 habitation_tel"], state,
                            lambda w: executor.EXPANSION_MODULES[w][0])
    later = copy.deepcopy(state)
    later["meta"]["playtime_s"] += 600
    station = next(a for a in later["assets"] if a["code"] == "KYV-745")
    station["modules"] = station["modules"] + ["hab_tel_s_01_macro"]
    (line,) = memory.track_expansions(data, later)
    assert "finished" in line
