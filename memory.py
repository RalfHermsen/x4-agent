"""What the agent remembers between cycles: its goals, and what it just did.

Two things live here, and the second one matters more than it sounds.

**Goals.** `active_goals` goes into the sitrep, `updated_goals` comes back out
of the plan and is stored again. Without it every cycle starts from nothing and
the model re-derives the same conclusion every few minutes.

**Outcomes.** Every command the agent sends is written down, and the next cycle
checks whether the world actually changed. This is the gap that hurt most while
building: an assignment that succeeded while the ship stayed idle, an explore
order that was created and vanished a minute later, three commands sent of which
one arrived. Each of those was invisible to the agent, which sent its order and
never looked again. Now a command that did not take effect comes back into the
next sitrep as a fact, so both the model and the log can see it.

The store is a small JSON file. A database would be tidier, but this has to
survive the host being restarted mid-session and be readable by eye when
something looks wrong.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

STORE = Path(__file__).parent / "logs" / "memory.json"

# How a sent command shows up in the world if it worked. The value is the order
# name the ship should be carrying, or "commander" for an assignment.
EXPECTED = {
    "explore": "Explore",
    "autotrade": "TradeRoutine",
    "automine": "MiningRoutine",
    "assign": "commander",
}


def load(path: Path = STORE) -> dict:
    if not path.exists():
        return {"goals": [], "pending": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"goals": [], "pending": []}
    data.setdefault("goals", [])
    data.setdefault("pending", [])
    return data


def save(data: dict, path: Path = STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record(data: dict, commands: list[str]) -> dict:
    """Remember commands just sent, so the next cycle can check them."""
    stamp = time.time()
    data["pending"] = [{"command": c, "sent": stamp} for c in commands]
    return data


def _ship_state(state: dict, code: str) -> dict | None:
    return next((a for a in state.get("assets", []) if a.get("code") == code), None)


def check(data: dict, state: dict) -> list[str]:
    """Compare what was sent last cycle against the world, return what failed.

    Only commands whose effect is visible in the savegame are judged. Anything
    else is dropped rather than guessed at: reporting a false failure would be
    worse than reporting nothing.
    """
    failures = []
    for entry in data.get("pending", []):
        parts = entry["command"].split()
        if len(parts) < 2:
            continue
        verb, ship = parts[0], parts[1]
        expected = EXPECTED.get(verb)
        if not expected:
            continue

        asset = _ship_state(state, ship)
        if asset is None:
            failures.append(f"{entry['command']!r}: {ship} is no longer there")
            continue

        if expected == "commander":
            # An assignment shows up as the ship having a commander. The parser
            # does not read that yet, so judge it by the ship no longer idling.
            order = (asset.get("orders") or [{}])[0].get("order")
            if order in (None, "Wait"):
                failures.append(
                    f"{entry['command']!r}: {ship} is still idle afterwards")
            continue

        order = (asset.get("orders") or [{}])[0].get("order")
        if order != expected:
            failures.append(
                f"{entry['command']!r}: {ship} is on {order or 'no order'}, "
                f"not {expected}")

    data["pending"] = []
    return failures
