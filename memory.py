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
import os
import time
from pathlib import Path

# X4_AGENT_MEMORY points an experiment at its own store, so a test run never
# writes into the live agent's memory.
STORE = Path(os.environ.get("X4_AGENT_MEMORY")
             or Path(__file__).parent / "logs" / "memory.json")

# How a sent command shows up in the world if it worked. The value is the order
# name the ship should be carrying, or "commander" for an assignment.
EXPECTED = {
    "explore": "Explore",
    "autotrade": "TradeRoutine",
    "automine": "MiningRoutine",
    "assign": "commander",
    "command": "commander",
}


# Commands that configure something rather than tell somebody to do something.
# A trade rule or a price stays true until it is changed, and none of them are
# visible in the savegame, so the "is this already true" gate cannot see them.
# Without this the agent re-sends the same setting every cycle for ever, on a
# pipe that accepts one command every two seconds.
CONFIGURATION = ("traderule", "price", "tradeware", "limit")

_EMPTY = {"goals": [], "pending": [], "applied": {}, "fleet": {},
          "explore_retried": {}, "refused": [], "funded": {}, "expansions": {},
          "purchases": {}, "blueprint_factions": [], "logbook_seen": -1.0,
          "feeders": {}, "standing": {}, "ledger": {}, "reserved": []}

# What the agent did, as opposed to what it saw or decided. In advise mode
# nothing is sent, so a cycle there must leave these as they were: recording
# an unsent command as pending made the next cycle report it as failed, and a
# purchase job or an expansion started on paper would stall the same way.
# Observations (fleet, logbook, ledger, reservations) and the model's own
# goals and refusals are kept in both modes.
DID_KEYS = ("pending", "applied", "funded", "expansions", "purchases", "feeders", "standing",
            "sent_at")


# The path is looked up at call time rather than bound as a default, so a test
# can point STORE at a temp file. Bound at import, every test that ran a cycle
# would have written into the live agent's memory.
def load(path: Path | None = None) -> dict:
    path = path or STORE
    if not path.exists():
        return dict(_EMPTY)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_EMPTY)
    for key, default in _EMPTY.items():
        data.setdefault(key, type(default)())
    return data


def save(data: dict, path: Path | None = None) -> None:
    path = path or STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# Ships that join the fleet on loan and leave again when their work is done. A
# hired construction vessel comes under player control for the length of a
# build, so comparing rosters naively reports every finished build as a loss.
BORROWED = ("construction vessel", "builder")


def check_fleet(data: dict, state: dict, ship_type) -> list[str]:
    """Ships that were here last cycle and are not here now.

    The agent remembered what it did and never what it had, so a ship simply
    stopped appearing. Nothing said so, and with twenty freighters on routes
    that are being shot at, nothing noticing is the difference between losing
    one ship and losing six.

    Says only that a ship is gone, not why: sold, destroyed and returned to its
    owner look identical from a savegame, and guessing would be worse than the
    plain fact.
    """
    now = {a["code"]: ship_type(a.get("macro"))
           for a in state.get("assets", [])
           if a.get("code") and (a.get("cls") or "").startswith("ship")}
    before = data.get("fleet") or {}
    data["fleet"] = now
    if not before:
        return []
    gone = [(code, kind) for code, kind in before.items()
            if code not in now and kind not in BORROWED]
    killed = {}
    for _, text in state.get("logbook", []):
        if "DESTROYED:" in text:
            what = text.split("DESTROYED:", 1)[1].strip()
            killed[what.split(" ", 1)[0]] = what
    return [f"{code} ({kind}) was in the fleet last cycle and is not there now"
            + (f": destroyed, {killed[code].split(' ', 1)[1]}." if code in killed else ".")
            for code, kind in sorted(gone)]


def _setting(command: str) -> tuple[str, str] | None:
    parts = command.split()
    # "sellware SHIP WARE" re-creates the ship's default trade order. Sent
    # every cycle with the same ware, the old order's children were left in the
    # queue: FWR-392 carried ten TradeRoutine orders in the 73-hour save. Only
    # a change of ware is worth sending.
    if len(parts) == 3 and parts[0] == "sellware":
        return " ".join(parts[:2]), parts[2]
    return _config_setting(command)


def _config_setting(command: str) -> tuple[str, str] | None:
    """A configuration command as (what it configures, what it was set to).

    All share one shape: `<verb> <station> <ware> <side> <value>`, limit with a
    trailing mode that is part of the value. Keeping
    the subject and the value apart is what lets a setting be changed back to an
    earlier value later; keying on the whole command would swallow that.
    """
    parts = command.split()
    if len(parts) not in (5, 6) or parts[0] not in CONFIGURATION:
        return None
    return " ".join(parts[:4]), " ".join(parts[4:])


def drop_repeats(data: dict, commands: list[str]) -> tuple[list[str], list[str]]:
    """Split off configuration commands that are already in force.

    The cost is that a setting the player undoes by hand is not re-applied. That
    is the right way round: the player outranks the agent.
    """
    applied = data.get("applied", {})
    fresh, repeats = [], []
    for command in commands:
        setting = _setting(command)
        if setting and applied.get(setting[0]) == setting[1]:
            repeats.append(command)
        else:
            fresh.append(command)
    return fresh, repeats


def record(data: dict, commands: list[str]) -> dict:
    """Remember commands just sent, so the next cycle can check them."""
    stamp = time.time()
    data["pending"] = [{"command": c, "sent": stamp} for c in commands]
    applied = data.setdefault("applied", {})
    for command in commands:
        setting = _setting(command)
        if setting:
            applied[setting[0]] = setting[1]
    return data


def _proposal(action) -> str:
    """An action as one line: its type and every field it was given.

    This is also the identity of a proposal across cycles. Two proposals with
    the same type and the same references are the same idea proposed again,
    whatever their rationale says.
    """
    fields = action.model_dump(exclude={"type", "priority", "rationale"})
    values = [str(v) if not isinstance(v, list) else ",".join(map(str, v))
              for v in fields.values() if v not in (None, [], "")]
    return " ".join([action.type, *values])


def record_refusals(data: dict, refusals: list[tuple]) -> dict:
    """Remember what was refused this cycle, and for how many cycles running.

    The model never heard that a proposal was refused, so it proposed the same
    thing again three minutes later: 220 times "already busy" in six days of
    log. The count is what turns a repeat into something the model can see.
    A proposal not refused this cycle drops out, so the count is consecutive.
    """
    before = {r["proposal"]: r["count"] for r in data.get("refused", [])}
    data["refused"] = []
    for action, reason in refusals:
        proposal = _proposal(action)
        if any(r["proposal"] == proposal for r in data["refused"]):
            continue
        data["refused"].append({"proposal": proposal, "reason": reason,
                                "count": before.get(proposal, 0) + 1})
    return data


# An expansion moves through these, in order. Each has the longest it may sit
# there, in game seconds, before the report calls it stalled, and the plain
# observation that goes with it. Observations, not diagnoses: "no vessel
# assigned" is what the save says; why is for the reader.
EXPANSION_STAGES = [
    ("planned", 1800, "no build started"),
    ("building", 1800, "build queued but no construction vessel assigned"),
    ("vessel", 7200, "vessel assigned, build still waiting for resources"),
    ("resources", 7200, "resources in, module not built yet"),
    ("done", None, None),
]
_STAGE = {name: i for i, (name, _, _) in enumerate(EXPANSION_STAGES)}


def start_expansions(data: dict, commands: list[str], state: dict,
                     module_for) -> None:
    """Begin tracking every expansion just sent. `module_for(ware)` -> macro."""
    now = state.get("meta", {}).get("playtime_s") or 0
    tracked = data.setdefault("expansions", {})
    for command in commands:
        parts = command.split()
        if len(parts) != 3 or parts[0] != "expand":
            continue
        _, station, ware = parts
        key = f"{station} {ware}"
        if key in tracked:
            continue
        asset = _ship_state(state, station) or {}
        macro = module_for(ware)
        tracked[key] = {"stage": "planned", "since": now, "module": macro,
                        "modules_before": (asset.get("modules") or []).count(macro)}


def _observed_stage(entry: dict, station: dict, storage: dict, ware: str) -> int:
    """The furthest stage the save shows, judged from the far end backwards."""
    built = (station.get("modules") or []).count(entry["module"]) > entry["modules_before"]
    # A habitat, a store or a dock produces nothing; it is done when it stands.
    # GKL-870's dock stood for 20 game hours while the report called it queued.
    if built and (not entry["module"].startswith("prod_")
                  or ware in (station.get("production_queue") or [])):
        return _STAGE["done"]
    build = storage.get("build") or {}
    if not (build.get("queued") or build.get("in_progress")):
        return _STAGE["planned"]
    if not build.get("builders"):
        return _STAGE["building"]
    still_buying = any(o.get("side") == "buy" and o.get("amount")
                       for o in storage.get("offers", []))
    if still_buying or (build.get("processor") or {}).get("state") == "waitingforresources":
        return _STAGE["vessel"]
    return _STAGE["resources"]


def track_expansions(data: dict, state: dict) -> list[str]:
    """Advance every tracked expansion and report the ones that stalled.

    `memory.check` judges orders by what a ship is doing next cycle. An
    expansion takes hours and passes through several hands (plan, build
    storage, construction vessel, suppliers), and the one that drops it leaves
    no trace: in August a whole expansion path did nothing for two days while
    looking like it worked. Each stage is a fact in the save, so each can be
    checked, and a stage held too long is reported.

    Time is the save's playtime, not the wall clock, so a paused game is not
    a stalled build.
    """
    now = state.get("meta", {}).get("playtime_s") or 0
    assets = {a.get("code"): a for a in state.get("assets", [])}
    lines = []
    for key in list(data.get("expansions", {})):
        entry = data["expansions"][key]
        station_code, ware = key.split()
        station = assets.get(station_code)
        if station is None:
            lines.append(f"expansion of {ware} at {station_code}: the station is gone")
            del data["expansions"][key]
            continue
        storage = assets.get(station.get("buildstorage")) or {}
        seen = _observed_stage(entry, station, storage, ware)
        # Stages only move forward: a build that finished leaves no build
        # task behind, which must not read as "back to planned".
        if seen > _STAGE[entry["stage"]]:
            entry["stage"], entry["since"] = EXPANSION_STAGES[seen][0], now
        if entry["stage"] == "done":
            lines.append(f"expansion of {ware} at {station_code} finished: "
                         + (f"the station produces {ware}" if entry["module"].startswith("prod_")
                            else "the module stands"))
            del data["expansions"][key]
            continue
        _, limit, observation = EXPANSION_STAGES[_STAGE[entry["stage"]]]
        held = now - entry["since"]
        if held > limit:
            lines.append(f"expansion of {ware} at {station_code}: {entry['stage']} "
                         f"for {held / 3600:.1f}h, {observation}")
    return lines


def game_refusals(data: dict, state: dict) -> list[str]:
    """What the Lua side refused since the last cycle, from the logbook.

    A verb that MD forwards to Lua can be refused there (no licence, ship not
    docked, too little money), and the refusal was written into the game's
    logbook and read by nobody. Every refusal on the Lua side starts with
    REFUSED:, so it can be told from confirmations.
    """
    seen = data.get("logbook_seen", -1.0)
    lines = []
    for when, text in state.get("logbook", []):
        if when <= seen:
            continue
        seen = max(seen, when)
        if "REFUSED:" in text:
            lines.append("the game refused: " + text.split("REFUSED:", 1)[1].strip())
        elif "ATTACKED:" in text or "DESTROYED:" in text:
            # MD's early warning (4.8): what hit or killed one of ours, by whom.
            lines.append("the game reports: " + text.split("] ", 1)[-1].strip())
        elif "RESERVED:" in text:
            # 3.8: the player took a ship back, or handed it to the agent again.
            parts = text.split("RESERVED:", 1)[1].split()
            if len(parts) == 2:
                reserved = set(data.get("reserved", []))
                (reserved.add if parts[1] == "on" else reserved.discard)(parts[0])
                data["reserved"] = sorted(reserved)
                lines.append(f"the player {'took' if parts[1] == 'on' else 'handed back'} "
                             f"{parts[0]}" + (" and keeps it" if parts[1] == "on" else ""))
        elif "LEDGER " in text:
            # The ledger verb (4.7): what each station paid NPC sellers.
            parts = text.split("LEDGER ", 1)[1].split()
            if len(parts) >= 3 and parts[2].startswith("paid_to_npcs="):
                data.setdefault("ledger", {})[parts[0]] = {
                    "hours": parts[1], "paid": int(parts[2].split("=", 1)[1] or 0),
                    "wares": dict(p.split("=", 1) for p in parts[3:] if "=" in p),
                    "time": when}
    data["logbook_seen"] = seen
    return lines


_ROLE_NAMES = {"mine": "mining", "trade": "trade", "defend": "defence",
               "buildstorage": "tradeforbuildstorage", "intercept": "interception"}


def _same_role(game_role: str, command_role: str) -> bool:
    return game_role == _ROLE_NAMES.get(command_role, command_role)


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
            # An assignment shows up as the ship carrying a subordinate group
            # (<subordinate group="N"/>); the commander holds what group N does.
            # Idleness used to stand in for this and was wrong both ways: an
            # assigned trader can sit waiting, a freelancer can look busy.
            group = (asset.get("assignment") or {}).get("group")
            if group is None:
                failures.append(
                    f"{entry['command']!r}: {ship} is not a subordinate afterwards")
            else:
                commander = _ship_state(state, parts[2]) if len(parts) > 2 else None
                role = ((commander or {}).get("assignment") or {}).get("groups", {}).get(str(group))                     or ((commander or {}).get("assignment") or {}).get("groups", {}).get(group)
                wanted = parts[3] if len(parts) > 3 else None
                if commander and wanted and role and not _same_role(role, wanted):
                    failures.append(f"{entry['command']!r}: {ship} is in group {group}, "
                                    f"which {parts[2]} uses for {role}")
            continue

        order = (asset.get("orders") or [{}])[0].get("order")
        if order != expected:
            failures.append(
                f"{entry['command']!r}: {ship} is on {order or 'no order'}, "
                f"not {expected}")

    data["pending"] = []
    return failures
