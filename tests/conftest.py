"""Shared fixtures: one parsed savegame, an isolated memory, a model that is not there.

The reference save is the small one the agent was first run against: one
station (KYV-745), two ships, 200,000 Cr. Parsing it takes about ten seconds,
so it is parsed once and cached in pytest's own cache directory, keyed on the
file's size and modification time. Tests get a deep copy, because the agent
mutates the state it is handed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import memory  # noqa: E402
import planner  # noqa: E402
from save_parser import documents_dir, parse_save  # noqa: E402
from schemas import PlannerResponse  # noqa: E402

SMALL_SAVE = "save_007.xml.gz"
# The newest save of the reference game: two stations, dozens of ships, a long
# exploration history. What the small save cannot show, this one does.
LARGE_SAVE = "autosave_02.xml.gz"
REPO = Path(__file__).resolve().parent.parent


def _find_save(name: str) -> Path | None:
    root = documents_dir() / "Egosoft" / "X4"
    return next(iter(sorted(root.glob(f"*/save/{name}"))), None)


@pytest.fixture(scope="session")
def small_save() -> Path:
    path = _find_save(SMALL_SAVE)
    if path is None:
        pytest.skip(f"{SMALL_SAVE} not found in the X4 profile folder")
    return path


def _parsed(request, save: Path) -> dict:
    """parse_save(), cached on the save file and on the parser's own source.

    Keyed on the file alone, a change to the parser would keep serving the old
    result and every test would pass against a state the code no longer makes.
    """
    stat = save.stat()
    code = hashlib.sha1(b"".join((REPO / name).read_bytes()
                                 for name in ("save_parser.py", "gamedata.py"))).hexdigest()[:12]
    key = f"x4-agent/state/{save.name}/{stat.st_size}-{int(stat.st_mtime)}-{code}"
    cached = request.config.cache.get(key, None)
    if cached is None:
        cached = parse_save(save)
        request.config.cache.set(key, cached)
    return cached


@pytest.fixture(scope="session")
def _small_state_cached(request, small_save) -> dict:
    return _parsed(request, small_save)


@pytest.fixture(scope="session")
def large_state(request) -> dict:
    path = _find_save(LARGE_SAVE)
    if path is None:
        pytest.skip(f"{LARGE_SAVE} not found in the X4 profile folder")
    return _parsed(request, path)


@pytest.fixture
def small_state(_small_state_cached) -> dict:
    return copy.deepcopy(_small_state_cached)


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch) -> Path:
    """Every test gets its own memory file; logs/memory.json is never touched."""
    store = tmp_path / "memory.json"
    monkeypatch.setattr(memory, "STORE", store)
    return store


class FakePlanner:
    """Stands in for both model calls. Set `.analysis` and `.plan` per test."""

    def __init__(self):
        self.analysis = "ACTIONS: none"
        self.plan = {"assessment": "nothing to do", "updated_goals": [],
                     "actions": []}
        self.reports: list[str] = []
        self.calls = 0

    def reason(self, report, guidelines, model):
        self.reports.append(report)
        self.calls += 1
        return self.analysis, 0.0

    def extract(self, analysis, report, model):
        return PlannerResponse.model_validate(copy.deepcopy(self.plan)), 0.0


@pytest.fixture
def fake_planner(monkeypatch) -> FakePlanner:
    fake = FakePlanner()
    monkeypatch.setattr(planner, "reason", fake.reason)
    monkeypatch.setattr(planner, "extract", fake.extract)
    return fake


@pytest.fixture
def run_cycle(fake_planner, small_save, small_state, monkeypatch):
    """agent.cycle() on the small save, without parsing it again."""
    import agent

    def _run(state: dict | None = None):
        monkeypatch.setattr(agent, "parse_save",
                            lambda _path: copy.deepcopy(state or small_state))
        return agent.cycle(save=small_save)
    return _run
