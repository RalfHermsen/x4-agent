"""Advise mode sends nothing, so it remembers having done nothing."""

import json

import agent


def _one_command(monkeypatch):
    monkeypatch.setattr(agent.executor, "repricing", lambda state: [])
    monkeypatch.setattr(agent.executor, "focus_fleet", lambda state: ["autotrade ASO-629"])


def test_advise_cycle_records_nothing_as_sent(run_cycle, monkeypatch, isolated_memory):
    _one_command(monkeypatch)
    result = run_cycle(sends=False)
    assert "autotrade ASO-629" in result["commands"]
    data = json.loads(isolated_memory.read_text(encoding="utf-8"))
    assert not data.get("pending") and not data.get("applied") and not data.get("standing")
    assert "would send: autotrade ASO-629" in result["panel"]
    assert not any(line.startswith("sent: ") for line in result["panel"])


def test_next_advise_cycle_reports_no_false_failure(run_cycle, monkeypatch):
    _one_command(monkeypatch)
    run_cycle(sends=False)
    second = run_cycle(sends=False)
    assert not any("autotrade ASO-629" in f for f in second["failures"])
    # Nothing was done about it, so the same advice stands.
    assert "autotrade ASO-629" in second["commands"]


def test_execute_cycle_still_remembers_what_it_sent(run_cycle, monkeypatch, isolated_memory):
    _one_command(monkeypatch)
    result = run_cycle()
    data = json.loads(isolated_memory.read_text(encoding="utf-8"))
    assert "autotrade ASO-629" in [p["command"] for p in data["pending"]]
    assert "sent: autotrade ASO-629" in result["panel"]
    # The next cycle judges it against the save, as before: still idle there.
    second = run_cycle()
    assert any("autotrade ASO-629" in f for f in second["failures"])
