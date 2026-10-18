"""A refused proposal comes back in the next report, with how often."""

import json

import pytest

import agent


@pytest.fixture(autouse=True)
def model_every_cycle(monkeypatch):
    # These tests are about what the model is told, so it must run every cycle;
    # the quiet-cycle logic has its own tests.
    monkeypatch.setattr(agent, "MAX_QUIET", 0.0)

# ASO-629 is the small save's freighter. Assigning it to mine is refused by the
# executor gates (it is not a mining ship), which is exactly the kind of
# proposal the live log showed being repeated cycle after cycle.
REFUSED = {"type": "assign_ship", "ship_ref": "ASO-629",
           "station_id": "KYV-745", "role": "mine", "rationale": "test"}


def test_refusal_reported_with_count(run_cycle, fake_planner, isolated_memory):
    fake_planner.plan["actions"] = [REFUSED]

    first = run_cycle()
    assert first["skipped"] or first["rejected"], "proposal was expected to be refused"
    assert "NOT DONE LAST CYCLE" not in first["sitrep"]

    second = run_cycle()
    assert "NOT DONE LAST CYCLE" in second["sitrep"]
    assert "assign_ship ASO-629 KYV-745 mine" in second["sitrep"]
    assert "cycles running" not in second["sitrep"]

    third = run_cycle()
    assert "(refused 2 cycles running)" in third["sitrep"]

    stored = json.loads(isolated_memory.read_text(encoding="utf-8"))
    assert stored["refused"][0]["count"] == 3


def test_refusal_drops_when_not_proposed_again(run_cycle, fake_planner):
    fake_planner.plan["actions"] = [REFUSED]
    run_cycle()
    fake_planner.plan["actions"] = []
    run_cycle()
    third = run_cycle()
    assert "NOT DONE LAST CYCLE" not in third["sitrep"]
