"""Translates validated planner actions into commands the in-game bridge accepts.

This is the last layer before anything reaches the game, and it is deliberately
narrow. Three separate gates stand between a model's idea and your empire:

1. `planner.check_actions()` already dropped actions referring to things that do
   not exist or are not ours.
2. This module only translates action types that the Mission Director side can
   actually execute. Everything else stays advice, no matter how confident the
   model was.
3. The caller decides whether to send at all (advise vs execute mode).

The executable vocabulary grows only when the matching MD command has been
written and verified against the game's own schemas. `describe()` reports what
that currently is, and the planner prompt is built from it, so the model is told
what its body can actually do.

Usage:
    from executor import to_commands
    commands, skipped = to_commands(validated_actions)
"""

from __future__ import annotations

from typing import Callable


def _explore(action) -> str:
    """set_behaviour(explore) -> the MD command that issues the vanilla Explore order."""
    return f"explore {action.ship_ref}"


def _autotrade(action) -> str:
    """set_behaviour(autotrade) -> the vanilla TradeRoutine order, on its defaults.

    A ware whitelist cannot travel through the pipe, because the Mission
    Director cannot parse strings. Rather than silently dropping the model's
    whitelist, `_blocked_reason` refuses the action when one was given.
    """
    return f"autotrade {action.ship_ref}"


def _automine(action) -> str:
    """set_behaviour(automine) -> the vanilla MiningRoutine order."""
    return f"automine {action.ship_ref}"


def _budget(action) -> str:
    """set_budget -> raise a station's operating budget to a level."""
    return f"budget {action.station_id} {action.level}"


def _assign(action) -> str:
    """assign_ship -> attach a ship to one of our stations as trader or miner."""
    return f"assign {action.ship_ref} {action.station_id} {action.role}"


def _blocked_reason(action, key) -> str | None:
    """Why this otherwise-executable action still must not be sent."""
    if key == ("set_behaviour", "autotrade") and getattr(action, "whitelist", None):
        wares = ", ".join(action.whitelist)
        return (f"whitelist ({wares}) cannot be transmitted; MD cannot parse "
                f"strings, so sending this would ignore half the instruction")
    return None


# (action type, discriminating value) -> command builder.
# The value is whatever second key makes the action executable; None means the
# action type alone is enough.
EXECUTABLE: dict[tuple[str, str | None], Callable] = {
    ("set_behaviour", "explore"): _explore,
    ("set_behaviour", "autotrade"): _autotrade,
    ("assign_ship", None): _assign,
    ("set_behaviour", "automine"): _automine,
    ("set_budget", None): _budget,
}


def _key(action) -> tuple[str, str | None]:
    if action.type == "set_behaviour":
        return ("set_behaviour", action.behaviour)
    return (action.type, None)


# What an executable action looks like once it has already happened. Without
# this the agent re-sends the same order every cycle, because the plan does not
# change until the world does.
SATISFIED_BY_ORDER = {
    ("set_behaviour", "explore"): "Explore",
    ("set_behaviour", "autotrade"): "TradeRoutine",
    ("set_behaviour", "automine"): "MiningRoutine",
}


def _active_orders(state: dict) -> dict[str, str]:
    """{ship code: current order name} for our own ships.

    `save_parser` sorts the active order first, so this is what the ship is
    actually doing, not the `default="1"` fallback that sits at the front of the
    file.
    """
    out = {}
    for asset in state.get("assets", []):
        if asset.get("code") and asset.get("orders"):
            out[asset["code"]] = asset["orders"][0].get("order")
    return out


def _busy_with(action, state: dict) -> str | None:
    """The real order a ship is already carrying out, if any.

    A ship on nothing but its `default="1"` fallback is free to be tasked.
    A ship running a real order is left alone, whoever gave it: you, its station
    manager, or an earlier cycle of this agent. Overriding it would undo work in
    progress, and there is no way to tell from the savegame who ordered what.

    The game itself exposes `@object.order.$internalorder` for exactly this
    distinction, but only in the running game, not in the save. Until the
    Mission Director side reads that flag, this rule errs on the side of not
    touching anything that is already busy.
    """
    ship = getattr(action, "ship_ref", None)
    if not ship:
        return None
    for asset in state.get("assets", []):
        if asset.get("code") != ship:
            continue
        for order in asset.get("orders", []):
            if not order.get("default"):
                return order.get("order")
    return None


def _already_done(action, key, state: dict) -> bool:
    wanted = SATISFIED_BY_ORDER.get(key)
    if not wanted or state is None:
        return False
    ship = getattr(action, "ship_ref", None)
    return bool(ship) and _active_orders(state).get(ship) == wanted


def to_commands(actions: list, state: dict | None = None) -> tuple[list[str], list[tuple]]:
    """Split actions into sendable commands and skipped ones with a reason.

    Pass `state` to suppress orders the game is already carrying out. This is
    the third gate: exists, allowed, and not already true.
    """
    commands: list[str] = []
    skipped: list[tuple] = []

    for action in actions:
        key = _key(action)
        builder = EXECUTABLE.get(key)
        if builder is None:
            label = key[0] if key[1] is None else f"{key[0]}({key[1]})"
            skipped.append((action, f"{label} is not executable yet, advice only"))
            continue
        busy = _busy_with(action, state) if state else None
        if busy and not _already_done(action, key, state):
            skipped.append((action, f"already busy with {busy}, not overriding"))
            continue

        blocked = _blocked_reason(action, key)
        if blocked:
            skipped.append((action, blocked))
            continue
        if _already_done(action, key, state):
            skipped.append((action, "already in effect, not re-sent"))
            continue

        command = builder(action)

        # One ship, one order. The model has emitted "put ASO-629 on autotrade"
        # and "assign ASO-629 to KYV-745" in the same plan; sending both would
        # have the second silently undo the first. Priority order decides.
        ship = getattr(action, "ship_ref", None)
        if ship and any(c.split()[1] == ship for c in commands if len(c.split()) > 1):
            skipped.append((action, f"conflicts with an order already queued for {ship}"))
            continue

        if command in commands:
            # The model happily emits the same action twice with different
            # reasons ("buy energycells", "buy water"). One command is enough.
            skipped.append((action, "duplicate of a command already queued"))
            continue
        commands.append(command)

    return commands, skipped


def describe() -> str:
    """What the executor can currently do, for logging and for the README."""
    names = sorted(k[0] if k[1] is None else f"{k[0]}({k[1]})" for k in EXECUTABLE)
    return ", ".join(names)
