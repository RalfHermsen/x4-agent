"""Standing rules: settings and errands Python sends on its own, each once.

Every rule here is arithmetic over the save or a setting that stays true, so
none of them waits for the model (the split in CLAUDE.md: the model decides
where attention goes, Python works out what that means). Each rule records
what it sent in memory, so a setting is not re-sent every cycle on a pipe that
takes one command every two seconds (tasks/lessons.md L9, L11).

    4.3   sell limits on inputs a station also makes
    4.4   a scout revisits known stations where our wares have few buyers
    4.5   satellites at trade partners we cannot see
    4.7   the ledger: what each station paid NPC sellers
    4.10  automatic resupply on
    4.11  idle fighters patrol a home sector with a threat
    4.12  station turrets engage enemies
    4.13  claim abandoned ships, collect lockboxes
    4.15  our own construction vessel looks for our builds
"""

from __future__ import annotations

import gamedata
import sitrep

# How often the ledger is asked for, in cycles, and over how many hours.
LEDGER_EVERY = 10
LEDGER_HOURS = 2


def _done(data: dict, key: str) -> set:
    return set(data.setdefault("standing", {}).setdefault(key, []))


def _mark(data: dict, key: str, item: str) -> None:
    items = data.setdefault("standing", {}).setdefault(key, [])
    if item not in items:
        items.append(item)


def sell_limits(state: dict, data: dict) -> list[str]:
    """4.3: a station must not sell what its own next cycle needs.

    For a ware the station both makes and eats, keep at least what its buy
    offer asks for: that is the manager's own figure for the input it needs.
    Rounded to a thousand, so the limit does not follow every wobble.
    """
    table = gamedata.wares()
    out = []
    for st in state.get("assets", []):
        if st.get("cls") != "station" or not st.get("code"):
            continue
        made = set(st.get("production_queue") or [])
        eaten = gamedata.consumed_by(sorted(made), table) if table else set()
        sells = {o["ware"] for o in st.get("offers", []) if o.get("side") == "sell"}
        for offer in st.get("offers", []):
            ware = offer.get("ware")
            if offer.get("side") != "buy" or ware not in (made & eaten & sells):
                continue
            keep = int(round((offer.get("desired") or 0), -3))
            if keep >= 1000:
                out.append(f"limit {st['code']} {ware} sell {keep} raise")
    return out


def revisit(state: dict, data: dict) -> list[str]:
    """4.4: an idle scout refreshes offers where our wares have few known buyers.

    Repricing will not cut a price with fewer than two known buyers, and the
    only way it learned of buyers was Explore into unknown space, which cost
    five scouts. ExploreUpdate stays in known space.
    """
    known = state.get("known_stations", [])
    sent = _done(data, "revisit")
    worst, worst_buyers = None, None
    for st in state.get("assets", []):
        if st.get("cls") != "station":
            continue
        for offer in st.get("offers", []):
            if offer.get("side") != "sell":
                continue
            buyers = sum(1 for k in known for o in k.get("offers", [])
                         if o.get("ware") == offer.get("ware") and o.get("side") == "buy")
            if worst_buyers is None or buyers < worst_buyers:
                worst, worst_buyers = st.get("code"), buyers
    if worst is None or worst_buyers is None or worst_buyers >= 2:
        return []
    occupied = state.get("player", {}).get("occupied_ship")
    for ship in state.get("assets", []):
        if (sitrep.ship_type(ship.get("macro")) == "scout" and sitrep.role_of(ship) == "IDLE"
                and ship.get("code") not in sent and ship.get("code") != occupied):
            _mark(data, "revisit", ship["code"])
            return [f"revisit {ship['code']} {worst}"]
    return []


def satellites(state: dict, data: dict) -> list[str]:
    """4.5: a satellite near the trade partner we cannot see that matters most.

    A partner is a known station that buys what we sell or sells what we buy.
    It matters by how many of our wares it trades. One satellite per cycle, so
    a resupply has time to come aboard.
    """
    eyes = set(state.get("eyes") or [])
    ours = {o.get("ware") for st in state.get("assets", []) if st.get("cls") == "station"
            for o in st.get("offers", [])}
    sent = _done(data, "satellite")
    best, best_count = None, 0
    for k in state.get("known_stations", []):
        sector = (k.get("place") or {}).get("sector")
        if not k.get("code") or k["code"] in sent or sector in eyes:
            continue
        count = sum(1 for o in k.get("offers", []) if o.get("ware") in ours)
        if count > best_count:
            best, best_count = k, count
    if not best:
        return []
    occupied = state.get("player", {}).get("occupied_ship")
    for ship in state.get("assets", []):
        if (sitrep.ship_type(ship.get("macro")) == "scout" and sitrep.role_of(ship) == "IDLE"
                and ship.get("code") != occupied):
            _mark(data, "satellite", best["code"])
            return [f"satellite {ship['code']} {best['code']} {best.get('owner')}"]
    return []


def ledger(state: dict, data: dict) -> list[str]:
    """4.7: every few cycles, ask the game what each station paid NPC sellers."""
    count = data.get("cycles", 0)
    data["cycles"] = count + 1
    return [f"ledger {LEDGER_HOURS}"] if count % LEDGER_EVERY == 0 else []


def once(state: dict, data: dict) -> list[str]:
    """4.10, 4.12, 4.13: settings that are set once and then left alone."""
    out = []
    if "resupply" not in _done(data, "once"):
        out.append("resupply medium")
        _mark(data, "once", "resupply")
    for signal, response in (("foundabandonedship", "claim"), ("foundlockbox", "collect")):
        if signal not in _done(data, "once"):
            out.append(f"respond {signal} {response}")
            _mark(data, "once", signal)
    for st in state.get("assets", []):
        if st.get("cls") == "station" and st.get("code") and st["code"] not in _done(data, "turrets"):
            out.append(f"turrets {st['code']} attackenemies")
            _mark(data, "turrets", st["code"])
    return out


def patrols(state: dict, data: dict) -> list[str]:
    """4.11: an idle fighter patrols a home sector where a threat is listed."""
    home = {(st.get("place") or {}).get("sector"): st.get("code")
            for st in state.get("assets", []) if st.get("cls") == "station"}
    threatened = [home[t["sector"]] for t in sitrep.threats(state) if t["sector"] in home]
    if not threatened:
        return []
    sent = _done(data, "patrol")
    for ship in state.get("assets", []):
        if (sitrep.ship_type(ship.get("macro")) == "fighter" and sitrep.role_of(ship) == "IDLE"
                and (ship.get("assignment") or {}).get("group") is None
                and ship.get("code") not in sent):
            _mark(data, "patrol", ship["code"])
            return [f"patrol {ship['code']} {threatened[0]}"]
    return []


def find_builds(state: dict, data: dict) -> list[str]:
    """4.15: our own construction vessel serves our builds when one is waiting."""
    waiting = any(bs.get("cls") == "buildstorage" and ((bs.get("build") or {}).get("queued")
                                                       or (bs.get("build") or {}).get("in_progress"))
                  and not (bs.get("build") or {}).get("builders")
                  for bs in state.get("assets", []))
    if not waiting:
        return []
    sent = _done(data, "findbuilds")
    for ship in state.get("assets", []):
        if (sitrep.ship_type(ship.get("macro")) == "construction vessel"
                and ship.get("owner") == "player" and ship.get("code") not in sent):
            _mark(data, "findbuilds", ship["code"])
            return [f"findbuilds {ship['code']}"]
    return []


# A build may wait this long, in game seconds, for a vessel before we hire one.
HIRE_AFTER = 600


def hire_builders(state: dict, data: dict) -> list[str]:
    """2.2: a build that has waited too long for a vessel gets one hired.

    Only when no vessel of ours could take it (4.15 tries that first), and one
    hire per build: the hire is paid and the vessel then belongs to the build
    until it is done. The candidate is a known vessel of another faction,
    nearest by jumps; the game refuses a busy or hostile one, and the refusal
    comes back through the logbook, after which the next candidate is tried.
    """
    from purchases import _graph, jumps
    now = state.get("meta", {}).get("playtime_s") or 0
    waiting = data.setdefault("standing", {}).setdefault("build_waiting", {})
    hired = data["standing"].setdefault("hired", {})
    tried = data["standing"].setdefault("hire_tried", [])
    own_builder = any(sitrep.ship_type(a.get("macro")) == "construction vessel"
                      and a.get("owner") == "player" for a in state.get("assets", []))
    stations = {a.get("code"): a for a in state.get("assets", []) if a.get("cls") == "station"}
    graph = _graph()
    out = []
    for bs in state.get("assets", []):
        if bs.get("cls") != "buildstorage" or not bs.get("station"):
            continue
        build = bs.get("build") or {}
        code = bs["station"]
        if not (build.get("queued") or build.get("in_progress")) or build.get("builders"):
            waiting.pop(code, None)
            hired.pop(code, None)
            continue
        since = waiting.setdefault(code, now)
        if now - since < HIRE_AFTER or own_builder or code in hired:
            continue
        sector = (stations.get(code, {}).get("place") or {}).get("sector")
        candidates = sorted((jumps(graph, b.get("sector"), sector), b["code"], b["owner"])
                            for b in state.get("builders", []) if b["code"] not in tried)
        if candidates:
            _, builder, owner = candidates[0]
            hired[code] = builder
            tried.append(builder)
            out.append(f"hire {builder} {owner} {code}")
    return out


# Below this share of its maximum hull a ship goes for repair; at or above
# the second it counts as repaired.
REPAIR_BELOW, REPAIRED_AT = 0.70, 0.95
SIZE_GROUPS = {"ship_xs": {"s", "m"}, "ship_s": {"s", "m"}, "ship_m": {"s", "m"},
               "ship_l": {"l", "xl"}, "ship_xl": {"l", "xl"}}


def repairs(state: dict, data: dict) -> list[str]:
    """4.9: a damaged ship of ours goes to the nearest known shipyard.

    The save only writes a hull value when a ship is damaged; the maximum is in
    the ship's macro. The Repair order pays the shipyard itself and logs it.
    """
    from purchases import _graph, jumps
    table = gamedata.ships()
    yards = [k for k in state.get("known_stations", []) if k.get("builds")]
    busy = data.setdefault("standing", {}).setdefault("repairing", {})
    graph = _graph()
    out = []
    for ship in state.get("assets", []):
        if not (ship.get("cls") or "").startswith("ship") or not ship.get("code"):
            continue
        top = (table.get(ship.get("macro")) or {}).get("hull")
        share = (ship["hull"] / top) if (ship.get("hull") is not None and top) else 1.0
        if ship["code"] in busy:
            if share >= REPAIRED_AT:
                busy.pop(ship["code"])
            continue
        if share >= REPAIR_BELOW:
            continue
        # A wharf for S and M docks both; a shipyard for L and XL the big ones.
        fits = SIZE_GROUPS.get(ship.get("cls"), set())
        usable = [k for k in yards if fits & set(k.get("builds") or [])]
        if not usable:
            continue
        sector = (ship.get("place") or {}).get("sector")
        yard = min(usable, key=lambda k: jumps(graph, sector, (k.get("place") or {}).get("sector")))
        busy[ship["code"]] = yard["code"]
        out.append(f"repair {ship['code']} {yard['code']} {yard.get('owner')}")
    return out


def seminars(state: dict, data: dict) -> list[str]:
    """4.2: a manager below three stars gets a held seminar of the right tier.

    The guidelines (section 4) ask for at least three stars: below that the
    manager's trade range does not reach suppliers two jumps away (lesson L3).
    The tier is the manager's stars, as the game's own conversation picks it.
    One application per station per save, so a stale save is not used twice.
    """
    held = state.get("player", {}).get("inventory") or {}
    now = state.get("meta", {}).get("playtime_s") or 0
    last = data.setdefault("standing", {}).setdefault("seminar_at", {})
    out = []
    for st in state.get("assets", []):
        manager = st.get("manager") or {}
        stars = manager.get("management_stars")
        if st.get("cls") != "station" or stars is None or stars >= 3:
            continue
        if held.get(f"inv_seminar_management_{stars}", 0) < 1:
            continue
        if last.get(st["code"], -1) >= now:
            continue
        last[st["code"]] = now
        out.append(f"seminar {st['code']}")
    return out


RULES = (sell_limits, revisit, satellites, ledger, once, patrols, find_builds, hire_builders,
         repairs, seminars)


def commands(state: dict, data: dict) -> list[str]:
    out = []
    for rule in RULES:
        out += rule(state, data)
    return out
