"""Buying a blueprint, as a job that takes several cycles.

A blueprint can only be bought where a ship of ours is docked (the owner's
rule, 2026-10-18), and our ships are almost never docked at somebody else's
station: traders dock for moments. So a purchase is a small sequence, one
step per cycle, each step a fact in the next save:

    docking   `dockat` sent; waiting for the ship to show as docked there
    buying    `blueprint` sent; waiting for the ware in the player's blueprints
    (done)    `release` sent, so the ship picks up what it was doing before

Choosing where and with which ship is arithmetic over the save, so it is done
here and never by the model. The rules, in order: a faction we already bought
from, then one whose licence we hold, then one whose reputation threshold we
meet; within that, a station where a ship of ours is already docked, then the
nearest by jumps; idle ships before busy ones; ties to the higher reputation.
Licences and reputation come from the save once the parser reads them; until
then those two rules simply do not discriminate.
"""

from __future__ import annotations

from collections import deque

import gamedata
import sitrep


# Hull types that may run an errand. A miner or a construction vessel away
# from its work costs more than the errand is worth, and an escape pod is not
# a ship any more.
ERRAND_TYPES = ("scout", "courier", "fighter", "container freighter",
                "solid freighter", "liquid freighter", "freighter")
# Game seconds a stage may take before the report says so, and before the job
# is given up and the ship released.
STALL_AFTER = {"docking": 1800, "licensing": 600, "buying": 600}
GIVE_UP_AFTER = {"docking": 3600, "licensing": 1800, "buying": 1800}
# Never leave less than this share of player money behind (as for funding).
RESERVE = 0.20
# A blueprint is bought once and kept, so it may go down to 5 %: the wharf's
# is 116.4 M, and at 20 % it waited for 146 M. Income refills the player's
# money: the game itself moves a station account's surplus back to it
# (`standing.accounts`).
BLUEPRINT_RESERVE = 0.05


def _graph() -> dict[str, list[str]]:
    return gamedata.sector_graph()


def jumps(graph: dict, start: str | None, goal: str | None) -> int:
    """Gate jumps between two sectors; a large number when unknown."""
    if not start or not goal:
        return 99
    if start == goal:
        return 0
    seen, queue = {start}, deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        for nxt in graph.get(node, []):
            if nxt == goal:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return 99


def _errand_ships(state: dict, busy: set[str]) -> list[dict]:
    occupied = state.get("player", {}).get("occupied_ship")
    out = []
    for ship in state.get("assets", []):
        if not (ship.get("cls") or "").startswith("ship"):
            continue
        if ship.get("code") in busy or ship.get("code") == occupied:
            continue
        if sitrep.ship_type(ship.get("macro")) not in ERRAND_TYPES:
            continue
        out.append(ship)
    return out


def licence_route(kind: str | None, faction: str, state: dict,
                  defs: dict) -> tuple[str, str | None]:
    """Can we get a blueprint sold under licence `kind` from `faction`?

    ("held", None), ("buy", None) when the licence is for sale and we qualify,
    or ("no", why). No licence data at all reads as held: the Lua side checks
    again and refuses with a reason the report shows.
    """
    player = state.get("player", {})
    owned = {(l.get("type"), l.get("faction")) for l in player.get("licences") or []}
    if not kind or not player.get("licences") or (kind, faction) in owned:
        return "held", None
    rule = (defs.get(faction) or {}).get(kind)
    if not rule:
        return "no", f"{faction} grants no licence {kind}"
    standing = (player.get("relations") or {}).get(faction, 0.0)
    if rule.get("minrelation") is not None and standing < rule["minrelation"]:
        return "no", (f"{kind} from {faction} needs reputation {rule['minrelation']}, "
                      f"we stand at {standing}")
    if rule.get("precursor") and (rule["precursor"], faction) not in owned:
        return "no", (f"{kind} from {faction} needs {rule['precursor']} first, which "
                      f"comes with a promotion ceremony the player attends")
    if not rule.get("price"):
        return "no", f"{kind} from {faction} is not for sale; it comes with a ceremony"
    return "buy", None


def choose(ware: str, state: dict, data: dict, table: dict | None = None,
           graph: dict | None = None, defs: dict | None = None
           ) -> tuple[dict | None, str | None]:
    """(faction, station, ship) for buying `ware`, or the reason there is none."""
    table = table if table is not None else gamedata.modules()
    graph = graph if graph is not None else _graph()
    defs = defs if defs is not None else gamedata.licences()
    entry = gamedata.blueprint(ware, table)
    if not entry:
        return None, f"{ware} is not a blueprint the game knows"
    # A generic thruster has no owner in wares.xml, yet the representatives
    # of Teladi and the Ministry list it (ship7-camp's `offers`).
    owners = entry.get("owners") or sorted((data.get("offered") or {}).get(ware) or {})
    if not owners:
        return None, f"nobody sells the blueprint for {ware}, as far as wares.xml and `offers` say"
    player = state.get("player", {})
    licences = {(l.get("type"), l.get("faction")) for l in player.get("licences") or []}
    relations = player.get("relations") or {}
    used_before = set(data.get("blueprint_factions", []))
    stations = [st for st in state.get("known_stations", [])
                if st.get("owner") in owners and st.get("code")]
    if not stations:
        return None, (f"no station of {', '.join(owners)} is known, and only they "
                      f"sell {ware}")
    routes = {f: licence_route(entry.get("licence"), f, state, defs)
              for f in {st["owner"] for st in stations}}
    stations = [st for st in stations if routes[st["owner"]][0] != "no"]
    if not stations:
        return None, "; ".join(why for _, why in routes.values() if why)
    ships = _errand_ships(state, set(data.get("purchases", {}).get(w, {}).get("ship")
                                     for w in data.get("purchases", {})))
    if not ships:
        return None, "no ship of ours is free for an errand (scouts, couriers, fighters, freighters)"

    best, best_key = None, None
    for st in stations:
        faction = st["owner"]
        has_licence = routes[faction][0] == "held"
        relation = relations.get(faction)
        for ship in ships:
            docked_here = ship.get("docked_at") == st["code"]
            idle = sitrep.role_of(ship) == "IDLE"
            key = (faction not in used_before,
                   not has_licence,
                   not docked_here,
                   jumps(graph, (ship.get("place") or {}).get("sector"),
                         (st.get("place") or {}).get("sector")),
                   not idle,
                   -(relation if relation is not None else 0))
            if best_key is None or key < best_key:
                best_key = key
                best = {"faction": faction, "station": st["code"], "ship": ship["code"],
                        "jumps": key[3],
                        "licence": None if has_licence else entry.get("licence")}
    if best["jumps"] >= 99:
        return None, (f"no ship of ours can reach a station of "
                      f"{', '.join(owners)} by a known route")
    return best, None


def start(data: dict, ware: str, state: dict, table: dict | None = None,
          graph: dict | None = None, defs: dict | None = None
          ) -> tuple[str | None, str | None]:
    """Open a purchase job. Returns (first command, None) or (None, reason)."""
    table = table if table is not None else gamedata.modules()
    jobs = data.setdefault("purchases", {})
    if ware in jobs:
        return None, f"a purchase of {ware} is already under way"
    if ware in (state.get("player", {}).get("blueprints") or []):
        return None, f"{ware} is already ours"
    entry = gamedata.blueprint(ware, table) or {}
    price = entry.get("price") or 0
    money = state.get("player", {}).get("money") or 0
    if price and price > money * (1 - BLUEPRINT_RESERVE):
        return None, (f"{ware} costs about {price:,} Cr and would leave less than "
                      f"{BLUEPRINT_RESERVE:.0%} of {money:,} Cr")
    pick, reason = choose(ware, state, data, table, graph, defs)
    if reason:
        return None, reason
    now = state.get("meta", {}).get("playtime_s") or 0
    ship = next((a for a in state.get("assets", []) if a.get("code") == pick["ship"]), {})
    head = (ship.get("orders") or [{}])[0]
    if (ship.get("docked_at") == pick["station"] and head.get("order") == "DockAndWait"
            and not head.get("default")):
        # Held there already by an errand, as after a purchase at the same
        # station: a `dockat` to where it lay ended at once, the ship went back
        # to its trading, and the engine after the miner at WLI-542 was given
        # up an hour later (ship7-camp). Only held: a trader that merely lay
        # there in the save had left when the order came (ship7b-camp).
        if pick["licence"]:
            jobs[ware] = {**pick, "stage": "licensing", "since": now}
            return f"licence {pick['licence']} {pick['ship']}", None
        jobs[ware] = {**pick, "stage": "buying", "since": now}
        return f"blueprint {ware} {pick['ship']}", None
    jobs[ware] = {**pick, "stage": "docking", "since": now}
    return f"dockat {pick['ship']} {pick['station']} {pick['faction']}", None


def ships_in_use(data: dict) -> set[str]:
    return {job["ship"] for job in data.get("purchases", {}).values()}


def first_commands(data: dict, ware: str, first: str, state: dict) -> list[str]:
    """A new job's first command, with `clear` before it when its ship has to
    dock and is on an order of its own that is not its default: the MoveWait
    VSR-185 carried kept it from the dock through three hours of `dockat` and
    `release`. A ship that buys where it lies keeps its order, which holds it
    there; cleared, it would go back to its default and leave."""
    job = (data.get("purchases") or {}).get(ware) or {}
    code = job.get("ship")
    ship = next((a for a in state.get("assets", []) if code and a.get("code") == code), {})
    head = (ship.get("orders") or [{}])[0]
    if job.get("stage") == "docking" and head.get("order") and not head.get("default"):
        return [f"clear {code}", first]
    return [first]


def kept(commands: list[str], data: dict) -> list[str]:
    """A cycle's job commands without the `release` of a ship that a job
    opened in the same cycle took again: released, it goes back to its
    trading, off the dock the next purchase needs."""
    busy = ships_in_use(data)
    return [c for c in commands if not (c.startswith("release ") and c.split()[1] in busy)]


def advance(data: dict, state: dict) -> tuple[list[str], list[str]]:
    """Move every job one step if the save allows it. (commands, report lines)."""
    now = state.get("meta", {}).get("playtime_s") or 0
    assets = {a.get("code"): a for a in state.get("assets", [])}
    held = set(state.get("player", {}).get("blueprints") or [])
    commands, lines = [], []
    for ware in list(data.get("purchases", {})):
        job = data["purchases"][ware]
        ship = assets.get(job["ship"])
        held_for = now - job["since"]
        if ware in held:
            commands.append(f"release {job['ship']}")
            lines.append(f"bought the blueprint {ware} from {job['faction']} at "
                         f"{job['station']}; {job['ship']} released")
            data.setdefault("blueprint_factions", [])
            if job["faction"] not in data["blueprint_factions"]:
                data["blueprint_factions"].append(job["faction"])
            del data["purchases"][ware]
            continue
        if ship is None:
            lines.append(f"purchase of {ware}: {job['ship']} is no longer there; given up")
            del data["purchases"][ware]
            continue
        owned = {(l.get("type"), l.get("faction"))
                 for l in state.get("player", {}).get("licences") or []}
        if job["stage"] == "docking" and ship.get("docked_at") == job["station"]:
            if job.get("licence") and (job["licence"], job["faction"]) not in owned:
                commands.append(f"licence {job['licence']} {job['ship']}")
                job["stage"], job["since"] = "licensing", now
            else:
                commands.append(f"blueprint {ware} {job['ship']}")
                job["stage"], job["since"] = "buying", now
            continue
        if job["stage"] == "licensing" and (job["licence"], job["faction"]) in owned:
            commands.append(f"blueprint {ware} {job['ship']}")
            job["stage"], job["since"] = "buying", now
            continue
        if held_for > GIVE_UP_AFTER[job["stage"]]:
            commands.append(f"release {job['ship']}")
            lines.append(f"purchase of {ware}: {job['stage']} for "
                         f"{held_for / 3600:.1f}h; given up and {job['ship']} released")
            del data["purchases"][ware]
            continue
        if held_for > STALL_AFTER[job["stage"]]:
            what = {"docking": f"{job['ship']} not docked at {job['station']} yet",
                    "licensing": f"licence {job.get('licence')} not held yet",
                    "buying": "bought nothing yet"}[job["stage"]]
            what += "; the game's refusal, if any, is listed above" if job["stage"] != "docking" else ""
            lines.append(f"purchase of {ware}: {job['stage']} for "
                         f"{held_for / 3600:.1f}h, {what}")
    return commands, lines
