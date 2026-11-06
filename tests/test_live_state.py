"""All standing rules together on a real game state (tasks/plan-2026-11.md, 0.6).

The unit tests give each rule a small state of its own, and none of today's bugs
showed there: they came from rules meeting each other, or a run starting with no
memory on a state with a guard out, a route out, patrols, three stations and builds.
saves/reference/live_state.json.gz is parse_save() of the game at 426 game hours (the
player's name replaced), saves/reference/live_plan.json its plan without the narrative.
Like the saves, they are derived from the game and stay out of the repository; the
tests are skipped where they are missing.
"""

import copy
import gzip
import json
from pathlib import Path

import pytest

import executor
import invariants
import standing

DATA = Path(__file__).parent.parent / "saves" / "reference"


@pytest.fixture(scope="session")
def _live():
    if not (DATA / "live_state.json.gz").exists():
        pytest.skip("saves/reference/live_state.json.gz is not on this machine")
    with gzip.open(DATA / "live_state.json.gz", "rt", encoding="utf-8") as handle:
        state = json.load(handle)
    plan = json.loads((DATA / "live_plan.json").read_text(encoding="utf-8"))
    return state, plan


@pytest.fixture
def live(_live):
    state, plan = copy.deepcopy(_live)
    return state, {"strategy": {"plan": plan}}


def _cycle(state, data):
    commands = list(dict.fromkeys(standing.commands(state, data)))
    return commands, invariants.check(state, commands, standing.LAST_BY_RULE)


def test_a_run_starting_on_the_live_state_trips_no_check(live):
    state, data = live
    commands, found = _cycle(state, data)
    assert commands and found == [] and standing.LAST_CLAIMED == []
    # Nor the cycle after, with the memory the first one left.
    assert _cycle(state, data)[1] == [] and standing.LAST_CLAIMED == []


def test_a_guard_leader_without_its_patrol_keeps_its_guard(live):
    """start9k: an Attack had taken RGM-519's Patrol and the 30 were assigned home."""
    state, data = live
    leader = next(a for a in state["assets"] if a.get("code") == "TXA-598")
    leader["orders"] = [{"order": "Attack"}, {"order": "ProtectStation", "default": True}]
    commands, found = _cycle(state, data)
    assert found == []
    assert not [c for c in commands if c.startswith("assign ") and c.endswith(" ZXX-974 defend")]
    assert data["standing"]["raid"]["leader"] == "TXA-598"


def test_a_campaign_against_the_pact_starts_by_scouting_heretics_end(live):
    """tasks/plan-2026-11.md phase 3: the Pact first, Heretic's End first."""
    state, data = live
    plan = data["strategy"]["plan"]
    base = {k: v for k, v in plan["stations"]["GZI-064"].items()}
    plan["campaign"] = {"faction": "scaleplate", "home": "ZXX-974", "garrison": 3, "hold_hours": 10,
                        "plot_cap": 20_000_000, "base": base,
                        "sectors": ["cluster_31_sector001_macro", "cluster_04_sector002_macro"]}
    # Our own five sectors swept by then, a scout is free for it.
    data["standing"] = {"swept": [s for g in plan["stations"].values() for s in g.get("sweep_sectors") or []]}
    commands, found = _cycle(state, data)
    assert found == [] and standing.LAST_CLAIMED == []
    assert (data["campaign"]["sector"], data["campaign"]["phase"]) == ("cluster_31_sector001_macro", "scout")
    assert any(c.startswith("sweep ") and c.endswith(" cluster_31_sector001_macro") for c in commands)


def test_a_pier_in_a_build_is_not_asked_for_again(live):
    """start9f and start9g: four piers for ZXX-974."""
    state, data = live
    pier = executor.EXPANSION_MODULES["pier"][0]
    gzi = next(a for a in state["assets"] if a.get("code") == "GZI-064")
    bs = next(a for a in state["assets"] if a.get("cls") == "buildstorage" and a.get("station") == "GZI-064")
    bs["build"] = {**(bs.get("build") or {}), "queue": [],
                   "running": [{"since": 0.0, "sequence": [*gzi["modules"], pier]}]}
    commands, found = _cycle(state, data)
    assert found == [] and "expand GZI-064 pier" not in commands
