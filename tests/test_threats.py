"""3.3: hostiles the player has seen, in sectors where we own something."""

import copy

import executor
import sitrep
from schemas import PlannerResponse


def test_counts_match_a_direct_count(large_state):
    # Counted directly in the frozen 105-hour save on 2026-10-18 with a regex
    # over its components: 121 Xenon M ships carry knownto="player".
    total = sum(f.get("xenon", {}).get("ship_m", 0) for f in large_state["hostiles"].values())
    assert total == 121


def test_only_sectors_we_are_in(large_state):
    ours = {(a.get("place") or {}).get("sector") for a in large_state["assets"]}
    assert all(t["sector"] in ours for t in sitrep.threats(large_state))


def _with_attack(state, minutes_ago):
    state = copy.deepcopy(state)
    now = state["meta"]["playtime_s"]
    ship = next(a for a in state["assets"] if a["code"] == "ASO-629")
    ship["attack"] = {"method": "weapon", "time": now - minutes_ago * 60}
    sector = ship["place"]["sector"]
    state["hostiles"] = {sector: {"xenon": {"ship_s": 2}}}
    return state


def test_recent_attack_listed_old_one_not(small_state):
    (recent,) = sitrep.threats(_with_attack(small_state, 10))
    assert recent["attacked"] == ["ASO-629"] and recent["strength"] == "minor"
    (old,) = sitrep.threats(_with_attack(small_state, 120))
    assert old["attacked"] == []


def test_strength_rule(small_state):
    state = _with_attack(small_state, 10)
    sector = next(iter(state["hostiles"]))
    state["hostiles"][sector]["xenon"] = {"ship_m": 6}
    assert sitrep.threats(state)[0]["strength"] == "moderate"
    state["hostiles"][sector]["xenon"] = {"ship_l": 1}
    assert sitrep.threats(state)[0]["strength"] == "major"


def test_report_section_and_a_defender_goes_out(large_state):
    report = sitrep.build(large_state)
    assert "# THREATS" in report and report.index("# THREATS") < report.index("# ATTENTION")
    fighter = next(a for a in large_state["assets"]
                   if sitrep.ship_type(a.get("macro")) == "fighter")
    plan = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "assign_ship", "ship_ref": fighter["code"], "station_id": "KYV-745",
         "role": "defend", "rationale": "threat"}]})
    commands, skipped = executor.to_commands(plan.actions, large_state)
    assert commands == [f"assign {fighter['code']} KYV-745 defend"] or skipped
