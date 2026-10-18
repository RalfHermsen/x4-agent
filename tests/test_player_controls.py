"""3.8 a reserved ship gets nothing; 3.9 the panel lines after a cycle."""

import copy
import json

import agent
import memory


def test_reservation_read_from_the_logbook(small_state):
    state = copy.deepcopy(small_state)
    state["logbook"] = [[1.0, "[x4-agent] RESERVED: ASO-629 on"]]
    data = {}
    assert memory.game_refusals(data, state) == ["the player took ASO-629 and keeps it"]
    assert data["reserved"] == ["ASO-629"]
    state["logbook"].append([2.0, "[x4-agent] RESERVED: ASO-629 off"])
    memory.game_refusals(data, state)
    assert data["reserved"] == []


def test_reserved_ship_never_in_commands(run_cycle, small_state, monkeypatch, isolated_memory):
    monkeypatch.setattr(agent.executor, "repricing", lambda state: [])
    monkeypatch.setattr(agent.executor, "focus_fleet", lambda state: ["autotrade ASO-629"])
    isolated_memory.write_text(json.dumps({"reserved": ["ASO-629"]}), encoding="utf-8")
    result = run_cycle()
    assert not any(c.split()[1:2] == ["ASO-629"] for c in result["commands"])
    assert any("reserved by the player: autotrade ASO-629" in f for f in result["failures"])


def test_panel_lines_match_the_cycle(run_cycle):
    result = run_cycle()
    panel = result["panel"]
    assert len(panel) <= 30
    assert all(len(line) <= 120 for line in panel)
    sent = [line for line in panel if line.startswith("sent: ")]
    assert [line[6:] for line in sent] == [c[:114] for c in result["commands"][:12]]
