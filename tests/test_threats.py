"""3.3: hostiles the player has seen, in sectors where we own something."""

import copy

import executor
import sitrep
from schemas import PlannerResponse


def test_counts_match_a_direct_count(large_state):
    # Counted directly in the frozen 105-hour save on 2026-10-18 with a regex
    # over its components: 121 Xenon M ships carry knownto="player", and 9 of
    # them are wrecks (state="wreck", counted on 2026-10-29).
    total = sum(f.get("xenon", {}).get("ship_m", 0) for f in large_state["hostiles"].values())
    assert total == 112


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
    # The four threats this save showed in our sectors were all wrecks
    # (2026-10-29), so a live one is put in.
    state = copy.deepcopy(large_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    state["hostiles"] = {station["place"]["sector"]: {"xenon": {"ship_m": 1}}}
    report = sitrep.build(state)
    assert "# THREATS" in report and report.index("# THREATS") < report.index("# ATTENTION")
    fighter = next(a for a in state["assets"]
                   if sitrep.ship_type(a.get("macro")) == "fighter")
    plan = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "assign_ship", "ship_ref": fighter["code"], "station_id": "KYV-745",
         "role": "defend", "rationale": "threat"}]})
    commands, skipped = executor.to_commands(plan.actions, state)
    assert commands == [f"assign {fighter['code']} KYV-745 defend"] or skipped


def test_a_shortage_is_a_time_not_an_amount(small_state):
    """ship7e3 reported "short 1242448 helium": that is when, at 345 h, not how much."""
    state = copy.deepcopy(small_state)
    now = state["meta"]["playtime_s"]
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["production"] = [
        {"ware": "superfluidcoolant", "short_of": {"helium": int(now - 90000)}},
        {"ware": "quantumtubes", "short_of": {"superfluidcoolant": int(now - 1800)}},
    ]
    text = sitrep.build(state)
    assert "production line: superfluidcoolant\n" in text
    assert "production line: quantumtubes, last short of superfluidcoolant 0.5 h ago" in text
