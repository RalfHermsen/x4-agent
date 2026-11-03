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
          a build waiting on a ware its own station holds gets it from there
    6.9   a station with modules and no manager gets one from our crews
    6.10  a station without a dock gets one, an empty plot first
    6.11  a station with a manager and an empty account gets the game's estimate
          a queued build that adds nothing is cancelled
          the blueprint of the connector production modules need is bought
"""

from __future__ import annotations

import re
import collections
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
                and ship.get("code") != occupied and ship.get("satellites_aboard")):
            _mark(data, "satellite", best["code"])
            return [f"satellite {ship['code']} {best['code']} {best.get('owner')}"]
    return []


def ledger(state: dict, data: dict) -> list[str]:
    """4.7: every few cycles, ask the game what each station paid NPC sellers."""
    count = data.get("cycles", 0)
    data["cycles"] = count + 1
    return [f"ledger {LEDGER_HOURS}"] if count % LEDGER_EVERY == 0 else []


WATCH_SATELLITES = 2     # per sector the plan watches; three at most, with one on its way
WATCH_AGAIN = 3600       # game seconds before a sector short of one gets another scout
SCOUT_SATELLITES = 10    # a bought scout's, in its loadout; none comes aboard by itself


def watch(state: dict, data: dict) -> list[str]:
    """The sectors the plan watches keep two satellites, each by another station.

    ship12j-camp had nothing in Trinity Sanctum III when its wharfs fell, so the
    report said no station sold weaponcomponents while four there did. A lost
    satellite is replaced. Scouts explore all the time and are never idle, so
    the first order clears the queue; `scouts` sends them exploring again after.
    One errand per scout, and the scout that went longest ago goes next.

    Only a scout with satellites aboard goes. ship13-camp's two had none and the game
    refused both, and the game does not resupply a player's ship at another faction's
    wharf (interrupt.restock.xml). With none aboard in any scout, one is bought with them.

    `watch_known` adds every sector where we know a station that is not Xenon or Kha'ak,
    the ones with most stations first: what the scouts find gets eyes.
    """
    import catalog
    import strategy
    wanted = [s for goal in strategy.goals(data).values() for s in goal.get("watch_sectors") or []]
    if any(goal.get("watch_known") for goal in strategy.goals(data).values()):
        counts = collections.Counter(s.get("sector") for s in state.get("all_stations") or []
                                     if s.get("sector") and s.get("owner") not in ("xenon", "khaak"))
        wanted += [s for s in sorted(counts, key=counts.get, reverse=True) if s not in wanted]
    held = data.setdefault("standing", {}).setdefault("watch", {})
    went = data["standing"].setdefault("watch_scouts", {})
    occupied = state.get("player", {}).get("occupied_ship")
    stocked = [s for s in state.get("assets", [])
               if sitrep.ship_type(s.get("macro")) == "scout" and s.get("code") != occupied
               and s.get("satellites_aboard")]
    free = sorted((s["code"] for s in stocked
                   if "DeployObjectAtPosition" not in [o.get("order") for o in s.get("orders") or []]),
                  key=lambda code: went.get(code, -1e9))
    now = (state.get("meta") or {}).get("playtime_s") or 0
    out, short = [], False
    for sector in wanted:
        mark = held.setdefault(sector, {"at": -1e9, "used": []})
        if ((state.get("satellites") or {}).get(sector, 0) >= WATCH_SATELLITES
                or now - mark["at"] < WATCH_AGAIN):
            continue
        stations = [s for s in state.get("all_stations") or []
                    if s.get("sector") == sector and s.get("code") and s.get("owner") not in ("xenon", "khaak")]
        if not stations:
            continue
        if not free:
            short = True
            continue
        station = next((s for s in stations if s["code"] not in mark["used"]), stations[0])
        scout = free.pop(0)
        mark["at"], went[scout] = now, now
        mark["used"].append(station["code"])
        out += [f"release {scout}", f"satellite {scout} {station['code']} {station['owner']}"]
    st = data["standing"]
    if short and not stocked and now - st.get("scout_bought_at", -1e9) > SCOUT_DELIVERY:
        options = catalog._buy_options(state, (("scout", "ship_{race}_s_scout_01_a_macro"),),
                                       size="m", gap=False)
        if options:
            st["scout_bought_at"] = now
            out.append(f"{options[0].command} {SCOUT_SATELLITES}")
    return out


def once(state: dict, data: dict) -> list[str]:
    """4.10, 4.12, 4.13, 6.5: settings that are set once and then left alone.

    6.5: traders and miners keep out of sectors of factions hostile to us. One
    to three ships were lost per run of 2026-10-20/21, freighters to pirates
    and Xenon among them.
    """
    out = []
    if "resupply" not in _done(data, "once"):
        out.append("resupply medium")
        _mark(data, "once", "resupply")
    if "avoid" not in _done(data, "once"):
        out.append("avoid hostile on")
        _mark(data, "once", "avoid")
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
    """4.11: an idle fighter patrols a home sector where a threat is listed.

    With a plan's wing, every fighter without a place under a destroyer: in
    ship11b-camp 16 stood on Wait while Xenon shot our miners at home. `wings`
    takes them back when a destroyer stands.
    """
    home = {(st.get("place") or {}).get("sector"): st.get("code")
            for st in state.get("assets", []) if st.get("cls") == "station"}
    threatened = [home[t["sector"]] for t in sitrep.threats(state) if t["sector"] in home]
    if not threatened:
        return []
    import strategy
    per = max((goal.get("fighters_per_destroyer") or 0 for goal in strategy.goals(data).values()), default=0)
    destroyers = sum(1 for s in state.get("assets", []) if sitrep.ship_type(s.get("macro")) == "destroyer")
    if per and strategy.fighters_flying(state) < per * destroyers:
        return []       # there is room under a destroyer (`wings`)
    sent = _done(data, "patrol")
    out = []
    for ship in state.get("assets", []):
        if (sitrep.ship_type(ship.get("macro")) == "fighter" and sitrep.role_of(ship) == "IDLE"
                and (ship.get("assignment") or {}).get("group") is None
                and ship.get("code") not in sent):
            _mark(data, "patrol", ship["code"])
            out.append(f"patrol {ship['code']} {threatened[0]}")
            if not per:
                break
    return out


def find_builds(state: dict, data: dict) -> list[str]:
    """4.15: our own construction vessel serves our builds when one is waiting.

    It is sent to the waiting build's station with `deploy`, a DeployToStation
    order as the map menu gives it. FindBuildTasks, which this used first, is
    called non-functional on the Egosoft wiki, and no run ever proved it.
    """
    waiting = [bs["station"] for bs in state.get("assets", [])
               if bs.get("cls") == "buildstorage" and bs.get("station")
               and ((bs.get("build") or {}).get("queued") or (bs.get("build") or {}).get("in_progress"))
               and not _served(bs.get("build") or {})]
    if not waiting:
        # Every build is served, so the next one that waits may call them again.
        data.setdefault("standing", {})["findbuilds"] = []
        return []
    sent = _done(data, "findbuilds")
    for ship in state.get("assets", []):
        if (sitrep.ship_type(ship.get("macro")) == "construction vessel"
                and ship.get("owner") == "player" and ship.get("code") not in sent):
            _mark(data, "findbuilds", ship["code"])
            return [f"deploy {ship['code']} {waiting[0]}"]
    return []


def _served(build: dict) -> bool:
    """A vessel is on the build: named as its builder, deployed, or the build
    is running.

    A player build names its build storage, not its vessel, even while the
    vessel builds (save_parser._builders), so `builders` stays empty then; the
    processor's state is what shows it. Seen in the builder proof of
    2026-10-20: "building", step 4 and 8 of 10, builders []. A vessel waiting
    for resources shows only as deployed; the game sends away any other
    vessel while it is there.
    """
    return (bool(build.get("builders")) or bool(build.get("deployed"))
            or (build.get("processor") or {}).get("state") == "building")


# A build may wait this long, in game seconds, for a vessel before we hire one.
HIRE_AFTER = 600
# A build still waiting for a vessel this long after a hire hires again.
REHIRE_AFTER = 2 * 3600


def hire_builders(state: dict, data: dict) -> list[str]:
    """2.2: a build that has waited too long for a vessel gets one hired.

    Only when no vessel of ours could take it (4.15 tries that first), and one
    hire per build: the hire is paid and the vessel then belongs to the build
    until it is done. The candidate is a known vessel of another faction,
    nearest by jumps; the game refuses a busy or hostile one, and the refusal
    comes back through the logbook, after which the next candidate is tried.
    """
    import executor
    from purchases import _graph, jumps
    now = state.get("meta", {}).get("playtime_s") or 0
    waiting = data.setdefault("standing", {}).setdefault("build_waiting", {})
    hired = data["standing"].setdefault("hired", {})
    hired_at = data["standing"].setdefault("hired_at", {})
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
        # A build of modules that all stand gives a vessel nothing to do; it is
        # cancelled (`empty_builds`), not served.
        if (not (build.get("queued") or build.get("in_progress")) or _served(build)
                or executor._adds_nothing(bs, state)):
            waiting.pop(code, None)
            hired.pop(code, None)
            hired_at.pop(code, None)
            continue
        # A hired vessel that waits too long for resources leaves for other
        # work (the manual's Station Building page: it may "disengage"), and
        # the build waits for a vessel again: GKL-870's was hired one vessel
        # in 33 game hours and never another, and MYI-961, hired for KYV-745's
        # queued refined metals, was back on its own FindBuildTasks six game
        # hours later with nothing built. A queued build has no processor yet,
        # so the time since the hire is all there is to go by.
        if code in hired and now - hired_at.setdefault(code, now) > REHIRE_AFTER:
            hired.pop(code)
            hired_at.pop(code)
        since = waiting.setdefault(code, now)
        if now - since < HIRE_AFTER or own_builder or code in hired:
            continue
        sector = (stations.get(code, {}).get("place") or {}).get("sector")
        candidates = sorted((jumps(graph, b.get("sector"), sector), b["code"], b["owner"])
                            for b in state.get("builders", []) if b["code"] not in tried)
        if candidates:
            _, builder, owner = candidates[0]
            hired[code] = builder
            hired_at[code] = now
            tried.append(builder)
            out.append(f"hire {builder} {owner} {code}")
    return out


OWN_STOCK_KEEP = 300       # of a ware the wharf builds with, stays for the ships
OWN_STOCK_ENOUGH = 500     # on offer, enough for the freighters to buy it (trade.find.commander)


def own_stock(state: dict, data: dict) -> list[str]:
    """A build waiting on a ware its own station holds gets it from that station.

    A station offers a resource it still wants more of only above a sell limit
    of its own. Made sellable alone, KYV-745 offered none of its 4,087 turret
    components, because it wanted 12,101 more, and its build waited on 836 of
    them while every other expansion queued behind it (proof-feed, ship7e).
    So: our ships only, then a limit that leaves exactly what the build wants
    on offer, then sellable; the freighter lent to the build storage buys it
    there like from any seller. Lowered when the stock drops, cleared when the
    build no longer wants the ware. A ware the station sells enough of already
    is left alone, and so is one it holds no more of than OWN_STOCK_KEEP.

    A ware it makes counts too, and the build gets what stands above the keep
    when it wants more than the stock: in ship8-camp the new line's turret
    components piled up to 1,708 with 48 on offer and 12,669 wanted.
    """
    opened = data.setdefault("standing", {}).setdefault("own_stock", {})
    assets = {a.get("code"): a for a in state.get("assets", [])}
    wanted = {}
    for bs in state.get("assets", []):
        if bs.get("cls") != "buildstorage" or not bs.get("station"):
            continue
        for offer in bs.get("offers", []):
            if offer.get("side") == "buy" and (offer.get("amount") or 0) > 0:
                wanted[f"{bs['station']} {offer['ware']}"] = offer["amount"]
    out = []
    for key, amount in wanted.items():
        code, ware = key.split()
        station = assets.get(code) or {}
        on_offer = sum(o.get("amount") or 0 for o in station.get("offers", [])
                       if o.get("ware") == ware and o.get("side") == "sell")
        if key not in opened and on_offer >= min(amount, OWN_STOCK_ENOUGH):
            continue
        stock = (station.get("cargo") or {}).get(ware) or 0
        limit = max(stock - amount, OWN_STOCK_KEEP)
        if stock <= OWN_STOCK_KEEP or (key in opened and opened[key] <= limit):
            continue
        if key not in opened:
            out.append(f"traderule {code} {ware} sell own")
        opened[key] = limit
        out += [f"limit {code} {ware} sell {limit}", f"tradeware {code} {ware} sell on"]
    for key in [k for k in opened if k not in wanted]:
        code, ware = key.split()
        del opened[key]
        if ware not in ((assets.get(code) or {}).get("production_queue") or []):
            out.append(f"tradeware {code} {ware} sell off")
        out += [f"limit {code} {ware} sell clear", f"traderule {code} {ware} sell default"]
    return out


# Below this share of its maximum hull a ship goes for repair; at or above
# the second it counts as repaired.
REPAIR_BELOW, REPAIRED_AT = 0.70, 0.95
RAID_GO_FROM, RAID_BACK_BELOW = 0.90, 0.75     # the fleet's hull, as a share of its whole
RAID_PER_XL = 6                                # destroyers it takes per Xenon XL in the target sector
RAID_HOLD_PER_XL = 4                           # the same, for a guard already on its post
RAID_ASK_AGAIN = 1800                          # game seconds before a raid is told again to attack
RAID_BACK_WAIT = 3600                          # game seconds before a raid counts as home anyway
RAID_STRONG_WAIT = 72000                       # game seconds a sector too strong stays off the list
SIZE_GROUPS = {"ship_xs": {"s", "m"}, "ship_s": {"s", "m"}, "ship_m": {"s", "m"},
               "ship_l": {"l", "xl"}, "ship_xl": {"l", "xl"}}


def repairs(state: dict, data: dict) -> list[str]:
    """4.9: a damaged ship of ours goes to the nearest known shipyard.

    The save only writes a hull value when a ship is damaged; the maximum is in
    the ship's macro. The Repair order pays the shipyard itself and logs it. Not to
    a yard where Xenon stations or capital ships are seen: in ship11-camp the nearest
    was in Trinity Sanctum III, with 4 XL, and miners and freighters died on the way.
    """
    from purchases import _graph, jumps
    table = gamedata.ships()
    hostile = {sector for sector, seen in (state.get("hostiles") or {}).items()
               if {"station", "ship_xl", "ship_l"} & set(seen.get("xenon") or {})}
    yards = [k for k in state.get("known_stations", []) if k.get("builds")
             and (k.get("place") or {}).get("sector") not in hostile]
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


def _spread_scouts(state: dict, data: dict, ours: list[dict], now: float) -> tuple[set, list[str]]:
    """The scouts that have a sector of their own, and the orders that send them there.

    A sector counts as known once a scout has been in it or we know a station there. A
    scout placing a satellite is left alone, and gets a new sector SCOUT_SWEEP after
    the last. The explore mark keeps executor.restart_explorers off a scout on its sweep.

    A sector the game cannot find is done with: the table of sectors holds some no gate
    reaches, and in start3 three scouts waited on them for two game hours each.
    """
    from purchases import _graph, jumps
    st = data["standing"]
    targets, visited = st.setdefault("scout_targets", {}), st.setdefault("scouts_visited", [])
    alive = {s["code"] for s in ours}
    for code in [c for c in targets if c not in alive]:
        del targets[code]
    graph = _graph()
    known = {s.get("sector") for s in state.get("all_stations") or []}
    for _, text in state.get("logbook") or []:
        found = re.search(r"found no sector (\S+)", text or "")
        if found and found.group(1) not in visited:
            visited.append(found.group(1))
    for code in [c for c, m in targets.items() if m["sector"] in visited
                 and m["sector"] != (next(s for s in ours if s["code"] == c).get("place") or {}).get("sector")]:
        del targets[code]
    for scout in ours:
        here = (scout.get("place") or {}).get("sector")
        if here and here not in visited:
            visited.append(here)
    errand = st.get("watch_scouts") or {}
    out, have = [], set(targets)
    for scout in ours:
        code, here = scout["code"], (scout.get("place") or {}).get("sector")
        mark = targets.get(code)
        if (errand.get(code) == now or "DeployObjectAtPosition" in [o.get("order") for o in scout.get("orders") or []]
                or (mark and (here != mark["sector"] or now - mark["at"] < SCOUT_SWEEP)
                    and now - mark["at"] < SCOUT_GIVE_UP)):
            have.add(code)
            continue
        taken = {m["sector"] for c, m in targets.items() if c != code}
        free = [s for s in graph if s not in known and s not in visited and s not in taken]
        if not free:
            targets.pop(code, None)
            have.discard(code)
            continue
        sector = min(free, key=lambda s: (jumps(graph, here, s), s))
        targets[code] = {"sector": sector, "at": now}
        data.setdefault("sent_at", {})[f"explore {code}"] = now
        have.add(code)
        out += [f"release {code}", f"scout {code} {sector}"]
    return have, out


def scouts(state: dict, data: dict) -> list[str]:
    """Scouts explore, and a scout lost doing it is replaced at once.

    The player's decision, 2026-10-21: losing scouts while exploring hostile sectors is part of
    exploring; when one is lost, order a new one straight away. So the number
    of scouts is kept at the most we have had: one short, one is bought (S, at
    the nearest wharf, outside the game hour between purchases, one at a
    time); a scout with no orders is sent exploring. A plan's `scouts` counts as a
    most already reached, which is how a new game gets its first ones, without
    the wait between replacements: one per cycle until the plan's number is there or on order.

    With a plan's `scouts` each goes to its own sector we know nothing of, the nearest
    to it. The game's own explore sends them all to the same nearest unknown: in start1b
    four swept one sector side by side. When none is left they explore as before.
    """
    import catalog
    import strategy
    ours = [s for s in catalog._ships(state) if sitrep.ship_type(s.get("macro")) == "scout"]
    st = data.setdefault("standing", {})
    planned = max((goal.get("scouts") or 0 for goal in strategy.goals(data).values()), default=0)
    most = max(st.get("scouts_most", 0), len(ours), planned)
    st["scouts_most"] = most
    now = state.get("meta", {}).get("playtime_s") or 0
    # A scout still at the wharf takes no order yet and stays idle; the explore
    # order sent to it is remembered (agent.py, `sent_at`) and not sent again
    # for a while. QPE-143 was sent one three cycles running.
    sent_at = data.get("sent_at") or {}
    spread, spread_out = _spread_scouts(state, data, ours, now) if planned else (set(), [])
    out = spread_out + [f"explore {s['code']}" for s in ours
                        if s["code"] not in spread
                        and sitrep.role_of(s) == "IDLE" and (s.get("assignment") or {}).get("group") is None
                        and now - sent_at.get(f"explore {s['code']}", -1e9) > SCOUT_DELIVERY]
    coming = sum(1 for o in state.get("ships_on_order") or [] if sitrep.ship_type(o.get("macro")) == "scout")
    if len(ours) + coming < planned:
        options = catalog._buy_options(state, (("scout", "ship_{race}_s_scout_01_a_macro"),),
                                       size="m", gap=False, hold=False)
        if options:
            st["scout_bought_at"] = now
            out.append(f"{options[0].command} {SCOUT_SATELLITES}")
    elif len(ours) < most and now - st.get("scout_bought_at", -1e9) > SCOUT_DELIVERY:
        # A wharf's M build module builds S ships too; the parser marks such a
        # wharf "m" only, so asking for "s" found no wharf and no lost scout
        # was replaced in the catalog runs c3 and c4.
        options = catalog._buy_options(state, (("scout", "ship_{race}_s_scout_01_a_macro"),),
                                       size="m", gap=False)
        if options:
            st["scout_bought_at"] = now
            out.append(f"{options[0].command} {SCOUT_SATELLITES}")
    return out


# One defence disc per this many modules, before any other module. GKL-870 was
# expanded on margins to 187 modules with 8 turrets and no disc, and the Xenon
# took it in about nine game hours (ship7e3-camp).
DEFENCE_EVERY = 60


def _defence_due(st: dict) -> bool:
    import strategy
    return len(st.get("modules") or []) // DEFENCE_EVERY > strategy.built(st, "defence")


def grow(state: dict, data: dict) -> list[str]:
    """6.2 and 6.7: a station with modules and no build running is expanded
    with the ware that pays most at the prices and demand we know.

    The choice is Python's, from the top of the ranking: given the same
    options in reverse order, the model took the same option in 1 of 16
    choices and the same position in 9 (docs/contracts.md). Only with money
    above the capital floor, one expansion at a time per station (the gate
    refuses a second while one is planned), and through every gate a proposal
    goes through. A builder is hired by `hire_builders` when the build needs one.
    """
    import catalog
    import strategy
    if catalog._spare(state) < catalog.CAPITAL_FLOOR:
        return []
    margins = [w for w, m in catalog.expansion_margins(state) if m > 0]
    out = []
    for st in state.get("assets", []):
        if st.get("cls") != "station" or not st.get("code"):
            continue
        # A strategist's plan comes first, once the station can work; with
        # every target standing, or no plan for it, the margins decide.
        planned = strategy.next_builds(st, data)
        if planned and catalog._has_dock(st) and st.get("manager"):
            wares = planned
        else:
            # A station with no modules yet (GKL-870) starts with a ware its
            # first module can make alone (6.3); the bridge finds such
            # stations since checkoperational="false".
            wares = catalog._growth_wares(st, margins)
        if _defence_due(st) and catalog._has_dock(st) and st.get("manager"):
            wares = ["defence", *wares]
        for ware in wares:
            command = catalog._through_gates({"type": "expand_station", "station_id": st["code"],
                                              "ware": ware}, state)
            if command:
                out.append(command)
                break
    return out


def managers(state: dict, data: dict) -> list[str]:
    """6.9: a station with modules and no manager gets one from our crews.

    Without one it neither buys nor sells (catalog._managed). The game does
    not appoint one: it gives the player an upkeep mission to hire someone
    (md/upkeep.xml). The bridge moves the crew member with the best manager
    skill from one of our ships; they travel there, and the save names them
    only on arrival, so a station sent one is left for MANAGER_TRAVEL.
    """
    import catalog
    now = state.get("meta", {}).get("playtime_s") or 0
    sent_at = data.get("sent_at") or {}
    # A construction site refuses everyone ("invalid"); a built station takes
    # one with or without a dock, but without one nobody trades with it
    # (`accounts`), so a station that cannot dock is sent nobody.
    return [f"manager {st['code']}" for st in catalog._stations(state)
            if st.get("code") and st.get("modules") and catalog._has_dock(st) and not st.get("manager")
            and now - sent_at.get(f"manager {st['code']}", -1e9) > MANAGER_TRAVEL]


def shiptraders(state: dict, data: dict) -> list[str]:
    """A wharf of ours with no ship trader gets one from our crews.

    The ship trader works the wharf's build queue (aiscripts/build.shiptrader.xml):
    an NPC wharf is given one when the universe is made (md/inituniverse.xml),
    ours is not. In ship7-camp our first own ship sat in KYV-745's queue for
    ten game hours, never even checked for wares. Sent as `managers` sends a
    manager, and left for MANAGER_TRAVEL while they travel. An L bay counts as
    a wharf: in start7 ZLR-942, with only the L bay, held our destroyer in its
    queue for 27 game hours with every ware in store and nobody at the post.
    """
    import catalog
    import executor
    now = state.get("meta", {}).get("playtime_s") or 0
    sent_at = data.get("sent_at") or {}
    wharfs = {executor.EXPANSION_MODULES[w][0] for w in ("wharf", "wharf_l")}
    return [f"shiptrader {st['code']}" for st in catalog._stations(state)
            if st.get("code") and wharfs & set(st.get("modules") or []) and not st.get("shiptrader")
            and now - sent_at.get(f"shiptrader {st['code']}", -1e9) > MANAGER_TRAVEL]


def cargo_drones(state: dict, data: dict) -> list[str]:
    """A station of ours that keeps no cargo drones is told to keep CARGO_DRONES.

    Drones are not bought: the station's manager buys their parts from its
    account and the station makes them (aiscripts/lib.ammo.drones.xml), for
    the number set in the Station Overview's supply node. GKL-870 had no such
    order, and the game asked for cargo drones there from game hour 77 on (an
    upkeep mission); KYV-745 kept 10. Only a station that can trade at all:
    modules, a dock and a manager, who does the buying.
    """
    import catalog
    now = state.get("meta", {}).get("playtime_s") or 0
    sent_at = data.get("sent_at") or {}
    return [f"cargodrones {st['code']} {CARGO_DRONES}" for st in catalog._stations(state)
            if st.get("code") and st.get("modules") and catalog._has_dock(st) and st.get("manager")
            and not (st.get("supplies") or {}).get(CARGO_DRONE)
            and now - sent_at.get(f"cargodrones {st['code']}", -1e9) > SUPPLY_WAIT]


def accounts(state: dict, data: dict) -> list[str]:
    """6.11: a station with a manager and an empty or overfull account is set
    to the game's own estimate, as its "Accept Estimate" button moves it.

    `budget` sets a minimum and a maximum and moves nothing. A station that
    sells nothing yet never fills its account itself: GKL-870 sat for two game
    hours with a minimum of 4.9 million, an empty account, and a buy offer for
    0 ice. Once an hour at most, so the transfer shows in the save first.

    Only with a dock: given the game's estimate (0.62 million), GKL-870 asked
    for 17,828 ice and in 2.4 game hours no trader so much as reserved a
    trade, while KYV-745 beside it had eleven. And only once it makes
    something: before that the game recommends nothing.

    Empty means below half the minimum, not zero. Filled once, GKL-870 spent
    its account down to 4,232 Cr against a minimum of 624,000 and stayed
    there: the game does not top it up, its manager could buy no ice, and a
    miner of ours sailed with ice nobody would take for five game hours.

    Overfull means above twice the maximum, and the same button then moves the
    rest back to the player: the ceremony series ended with 70 to 78 million
    on station accounts, against a few million the game recommended, while
    the player, who pays for blueprints and ships, held 38 to 40.

    From then on the game moves the money itself (md/notifications.xml,
    PlayerOwnedMoneyUpdated): above the larger of the maximum and one and a
    half times the production money, the account goes back down to the
    production money and the rest to the player. In ship3-camp that was
    about 22.4 million every four game hours, seven times.
    """
    import catalog
    now = state.get("meta", {}).get("playtime_s") or 0
    sent_at = data.get("sent_at") or {}

    def off_estimate(st: dict) -> bool:
        acct = st.get("account") or {}
        amount = int(acct.get("amount", 0) or 0)
        drained = not amount or amount < int(acct.get("min", 0) or 0) / 2
        overfull = int(acct.get("max", 0) or 0) > 0 and amount > 2 * int(acct["max"])
        return drained or overfull

    return [f"account {st['code']}" for st in catalog._stations(state)
            if st.get("code") and st.get("manager") and catalog._has_dock(st)
            and any(m.startswith("prod_") for m in st.get("modules") or [])
            and off_estimate(st)
            and now - sent_at.get(f"account {st['code']}", -1e9) > ACCOUNT_WAIT]


def connectors(state: dict, data: dict) -> list[str]:
    """The blueprint of the connector production modules need is bought.

    Without struct_arg_cross_01 no production module or habitat attached to
    KYV-745 or GKL-870 at all; with it water fitted on both (2026-10-23). The
    expansion gate asks for it (executor.CONNECTOR). Bought as any blueprint:
    a ship of ours docks at a station of a faction that sells it. Not among
    RULES: agent.py sends its first command with the purchase jobs', which
    the errand filter lets through.
    """
    import executor
    import gamedata
    import purchases
    ware = (gamedata.modules().get(executor.CONNECTOR) or {}).get("ware")
    if not ware or ware in (state.get("player", {}).get("blueprints") or []):
        return []
    if ware in data.get("purchases", {}):
        return []
    first, _ = purchases.start(data, ware, state)
    if not first:
        return []
    return purchases.first_commands(data, ware, first, state)


def empty_builds(state: dict, data: dict) -> list[str]:
    """A queued build that adds nothing is cancelled (executor._adds_nothing).

    The ware named is the last expansion sent to that station: the bridge
    writes it into its refusal, so the expansion that made the empty build
    is not asked for again. Once an hour at most.
    """
    import executor
    now = state.get("meta", {}).get("playtime_s") or 0
    sent_at = data.get("sent_at") or {}
    out = []
    for bs in state.get("assets", []):
        code = bs.get("station")
        if bs.get("cls") != "buildstorage" or not code or not executor._adds_nothing(bs, state):
            continue
        if now - sent_at.get(f"cancelbuild {code}", -1e9) < CANCEL_WAIT:
            continue
        sent = [(t, c.split()[2]) for c, t in sent_at.items()
                if c.startswith(f"expand {code} ") and len(c.split()) == 3]
        out.append(f"cancelbuild {code} {max(sent)[1] if sent else 'unknown'}")
    return out


def docks(state: dict, data: dict) -> list[str]:
    """6.10: a station without a dock gets an M dock, an empty plot first.

    Ships trade at a dock. The expansion path builds only the modules asked
    for, so GKL-870, started from an empty plot with water, had a water
    module and a store and nowhere to dock, and on its 2 km plot no dock
    could be fitted afterwards. So an empty plot starts with its dock. Through
    the same gates as any expansion: the blueprint, one build at a time, and
    not again once the bridge could not fit it.
    """
    import catalog
    out = []
    for st in catalog._stations(state):
        if st.get("code") and not catalog._has_dock(st):
            command = catalog._through_gates({"type": "expand_station", "station_id": st["code"],
                                              "ware": "dock"}, state)
            if command:
                out.append(command)
    return out


# Game seconds a bought scout gets to arrive before another is bought.
SCOUT_DELIVERY = 1800
SCOUT_SWEEP = 1200       # game seconds a scout gets to sweep the sector it reached
SCOUT_GIVE_UP = 7200     # and to reach it, before it is sent to another
# Game seconds a manager sent from our crews gets to arrive before another is sent.
MANAGER_TRAVEL = 3600
# Game seconds before an account top-up is sent again.
ACCOUNT_WAIT = 3600
# Cargo drones a station keeps, as KYV-745 did, and the wait before asking again.
CARGO_DRONE = "ship_gen_xs_cargodrone_empty_01_a"
CARGO_DRONES = 10
SUPPLY_WAIT = 3600
# Game seconds before an empty build is asked to be cancelled again.
CANCEL_WAIT = 3600

def _hull_share(ship: dict) -> float:
    """The save writes a hull value only when a ship is damaged (`repairs`)."""
    top = (gamedata.ships().get(ship.get("macro")) or {}).get("hull")
    return (ship["hull"] / top) if (ship.get("hull") is not None and top) else 1.0


SHELTER_AGAIN = 1800


def shelter(state: dict, data: dict) -> list[str]:
    """The ship the player sits in stays by the plan's station, on the game's autopilot.

    A player in a spacesuit ends the run and makes the save useless as a start, and
    seven runs ended that way. The last two, ship12g-camp and ship12i-camp, had
    flown from the station to zone003 by themselves and fell there, while 19 game
    hours by the station passed without a loss in ship12h-camp. A `dockat` does not
    move a ship with the player at its controls: ship12i-camp stacked four of them.
    The first call also clears the queue, which held an old order for a far wharf.

    With no station of ours yet, a wharf we know in its sector does: start1's ship sat in
    the open in Argon Prime and three Xenon S came for it."""
    import strategy
    occupied = state.get("player", {}).get("occupied_ship")
    ship = next((a for a in state.get("assets", []) if a.get("code") == occupied), None)
    home = next(iter(strategy.goals(data)), None)
    station = next((a for a in state.get("assets", []) if a.get("code") == home), None)
    faction = "player"
    if not station and ship:
        station = next((k for k in state.get("known_stations", []) if k.get("builds")
                        and (k.get("place") or {}).get("sector") == (ship.get("place") or {}).get("sector")), None)
        home, faction = (station.get("code"), station.get("owner")) if station else (home, faction)
    if not ship or not station or ship.get("connection") == "dock":
        return []
    now = state["meta"]["playtime_s"]
    mark = data.setdefault("standing", {})
    first = "shelter" not in mark
    away = (ship.get("place") or {}).get("zone") != (station.get("place") or {}).get("zone")
    if not first and (not away or now - mark["shelter"] < SHELTER_AGAIN):
        return []
    mark["shelter"] = now
    return ([f"undock {occupied}"] if first else []) + [f"autopilot {home} {faction}"]


def wings(state: dict, data: dict) -> list[str]:
    """A free fighter flies under the destroyer with the fewest, as interception:
    it takes small and medium ships, and docks in the destroyer's four S bays.
    Free means idle, also with a commander on paper: ship9c-camp's 24 sat on Wait
    under theirs, and a run started from a save has no wing in its memory."""
    import catalog
    import strategy
    per = max((goal.get("fighters_per_destroyer") or 0 for goal in strategy.goals(data).values()), default=0)
    if not per:
        return []
    ships = catalog._ships(state)
    codes = {s.get("code") for s in ships}
    wing = data.setdefault("standing", {}).setdefault("wing", {})
    for code in [c for c, leader in wing.items() if c not in codes or leader not in codes]:
        del wing[code]
    load = {s["code"]: 0 for s in ships if sitrep.ship_type(s.get("macro")) == "destroyer"}
    for leader in wing.values():
        load[leader] += 1
    out = []
    for ship in ships:
        if (sitrep.ship_type(ship.get("macro")) != "fighter" or ship.get("code") in wing
                or (sitrep.role_of(ship) != "IDLE" and sitrep._first_order(ship) != "Patrol")):
            continue
        leader = min(load, key=load.get, default=None)
        if leader is None or load[leader] >= per:
            break
        load[leader] += 1
        wing[ship["code"]] = leader
        out.append(f"command {ship['code']} {leader} interception")
    return out


def undock_fleet(state: dict, data: dict) -> list[str]:
    """A destroyer the game parked out of its own accord leaves again.

    It stays for good, on a temporary DockAndWait without a timeout, and keeps
    a raid or a new ship waiting: in ship10b-camp VOK-360 lay at the pier and
    TUR-084 in the L bay of the wharf for 50 game hours, with a destroyer on order
    behind it. A Repair order waits on a DockAndWait too, and has two in its queue.
    """
    busy = data.get("standing", {}).get("repairing") or {}
    out = []
    for ship in state.get("assets", []):
        if sitrep.ship_type(ship.get("macro")) != "destroyer" or ship.get("connection") != "dock":
            continue
        queue = [o.get("order") for o in ship.get("orders") or [] if not o.get("default")]
        if queue == ["DockAndWait"] and ship.get("code") not in busy:
            out.append(f"undock {ship['code']}")
    return out


def _fly_home(raid: dict, alive: list[dict]) -> list[str]:
    """A guard's Patrol survives `release`, and `undock` takes it off: TYL-370 stayed alone
    in Trinity Sanctum III while its 24 flew home (ship13b-camp)."""
    leader = [f"undock {raid['leader']}"] if raid.get("guard") else []
    return ([f"release {s['code']}" for s in alive] + leader
            + [f"assign {s['code']} {raid['home']} defend" for s in alive])


def raids(state: dict, data: dict) -> list[str]:
    """The plan's destroyers go for the Xenon in its `raid_sector`: its
    stations, or with none its ships, by the `raid` verb's priority order.

    They gather at the station, go when all of them and their fighters stand and
    are whole, under one leader, and come back when the fleet is hurt, when it sees
    more XL than it can take, when it has
    not arrived in RAID_BACK_WAIT, or when it has arrived and no Xenon is left. What we
    see from home is not what stands there: ship11-camp left for 1 station, found
    4 XL and 90 S, stayed over four game hours and lost all 10 destroyers. A dead ship
    counts as a hull of nothing, since an average over the living does not fall. On the way
    "none left" means nothing: what we see of a sector is what our ships there see, and
    ship9-camp's first raid turned back after one cycle because the one Xenon S
    a freighter had seen was out of sight. The leader's own orders stay queued
    behind the raid, so `release` flies it home.
    With `raid_guard` it stays once there: no Xenon left is what it came for, and in
    ship12j-camp the trip home after each kill brought it back scattered, 10 of 25 lost.
    Any XL at home calls a raid back and keeps the next one in. A satellite in the sector
    shows what stands there, so its strong mark no longer needs waiting out.
    `repairs` takes out a single badly damaged ship on the way. One raid at a
    time. tasks/plan-shipbuilding-2026-10.md, Raids.
    """
    import executor
    import strategy
    ours = {s["code"]: s for s in state.get("assets", [])
            if (s.get("cls") or "").startswith("ship") and s.get("code")}
    held = data.setdefault("standing", {})
    raid = held.get("raid")
    now = (state.get("meta") or {}).get("playtime_s") or 0
    # Held one cycle past the `assign`s, for `fleet` to count them: in ship9-camp
    # the raid ended, the five under its leader read as gone, and a seventh
    # destroyer went on order in that same cycle.
    if raid and raid["phase"] == "settling":
        held.pop("raid")
        raid = None
    if raid:
        alive = [ours[code] for code in raid["ships"] if code in ours]
        if raid["phase"] == "out":
            if ((ours.get(raid["leader"]) or {}).get("place") or {}).get("sector") == raid["sector"]:
                raid["arrived"] = True
                raid.setdefault("arrived_at", now)
            left = ((state.get("hostiles") or {}).get(raid["sector"]) or {}).get("xenon")
            # A guard on its post holds longer than a raid would go. In ship13b-camp 30 stood
            # 15,000 game seconds under up to 4 XL without a loss, then left at 6. Leaving did not
            # stop the XL killing (at least 2 of its 5 went after the recall), and wharf SCY-867
            # fell 5,100 later. A falling hull still brings it home.
            per_xl = RAID_HOLD_PER_XL if raid.get("guard") and raid.get("arrived") else RAID_PER_XL
            strong = (left or {}).get("ship_xl", 0) * per_xl > len(alive)
            xl_at_home = (((state.get("hostiles") or {}).get(raid["home_sector"]) or {}).get("xenon") or {}).get("ship_xl")
            if strong:
                held.setdefault("raid_strong", {})[raid["sector"]] = now
            # Once there, a ship in any other sector is chasing, and what it chases into is not
            # what we counted: in start8g the raid on Hatikvah's Choice I followed Xenon into
            # Tharka's Cascade XV, 5 to 7 stations and up to 6 XL, and all seven were lost.
            # Home and the sectors on the way do not count: a slow ship is still coming.
            import purchases
            graph = purchases._graph()
            route = purchases.jumps(graph, raid["home_sector"], raid["sector"])

            def on_the_way(sector):
                return (sector in (raid["sector"], raid["home_sector"], None)
                        or purchases.jumps(graph, raid["home_sector"], sector)
                        + purchases.jumps(graph, sector, raid["sector"]) == route)
            strayed = raid.get("arrived") and not all(on_the_way((s.get("place") or {}).get("sector"))
                                                      for s in alive)
            hurt = (strong or strayed or xl_at_home
                    or sum(_hull_share(s) for s in alive) < RAID_BACK_BELOW * len(raid["ships"]))
            done = not left if raid.get("arrived") else now - raid["since"] >= RAID_BACK_WAIT
            if raid.get("unseen") and raid.get("arrived"):
                # It went in blind, and a sector is wide: nothing in sight on the
                # first cycle there says nothing.
                done = done and now - raid["arrived_at"] >= RAID_BACK_WAIT
            if raid.get("guard") and raid.get("arrived"):
                done = False
            if raid["leader"] in ours and not (hurt or done):
                # A station came into sight, or the one it attacked is gone and
                # another stands: the `raid` before this one only found a patrol.
                queue = [o.get("order") for o in ours[raid["leader"]].get("orders") or [] if not o.get("default")]
                stay = raid.get("guard") and "Patrol" not in queue
                if (raid.get("arrived") and ((left or {}).get("station") or stay) and "Attack" not in queue
                        and now - raid.get("asked", -1e9) >= RAID_ASK_AGAIN):
                    raid["asked"] = now
                    return [f"raid {raid['leader']} {raid['sector']}" + (" stay" if stay else "")]
                return []
            if alive:
                raid["phase"], raid["since"] = "back", now
                raid["leader"] = raid["leader"] if raid["leader"] in ours else alive[0]["code"]
                # Both: `release` alone leaves a ship under fire shooting back where it stands
                # (ship12c-camp, WKU-369), and on a dock order 15 reached home and flew back
                # into the fight for 3,000 game seconds (ship12f-camp). These two brought
                # all 14 home within 600.
                return _fly_home(raid, alive)
        elif raid["leader"] in ours and now - raid["since"] < RAID_BACK_WAIT:
            sector = (ours[raid["leader"]].get("place") or {}).get("sector")
            if sector != raid["home_sector"]:
                return []
        raid["phase"] = "settling"
        return _fly_home(raid, alive)
    for code, goal in strategy.goals(data).items():
        sector, wanted = goal.get("raid_sector"), goal.get("destroyers") or 0
        home = next((a for a in state.get("assets", []) if a.get("code") == code), None)
        # A run that ends during a raid leaves its destroyers under the leader,
        # and the next one has no raid in its memory: ship9d-camp read 1 of 6.
        strays = [s for s in ours.values() if sitrep.ship_type(s.get("macro")) == "destroyer"
                  and executor.serves(s, state)[1] == "attack"]
        if wanted and home and strays:
            return [f"assign {s['code']} {code} defend" for s in strays]
        # Its leader defends already, and keeps the guard's Patrol until `undock` (`_fly_home`):
        # NQB-447, leader of a guard start8b left out, patrolled Hatikvah's Choice I alone
        # for six game hours of start8c.
        posted = [s for s in ours.values() if sitrep.ship_type(s.get("macro")) == "destroyer"
                  and "Patrol" in [o.get("order") for o in s.get("orders") or [] if not o.get("default")]]
        if wanted and home and posted:
            return [f"undock {s['code']}" for s in posted]
        if not (sector and wanted and home):
            continue
        xenon = ((state.get("hostiles") or {}).get(sector) or {}).get("xenon", {})
        enough = goal.get("raid_from") or wanted
        # The ships that go, not the whole fleet: they turn back on arrival by this same sum.
        if (not xenon and not goal.get("raid_unseen")) or xenon.get("ship_xl", 0) * RAID_PER_XL > enough:
            continue
        if (now - (held.get("raid_strong") or {}).get(sector, -1e9) < RAID_STRONG_WAIT
                and sector not in (state.get("eyes") or [])):
            continue
        busy = held.get("repairing") or {}
        home_sector = (home.get("place") or {}).get("sector")
        if (((state.get("hostiles") or {}).get(home_sector) or {}).get("xenon") or {}).get("ship_xl"):
            continue
        ready = [s for s in ours.values()
                 if sitrep.ship_type(s.get("macro")) == "destroyer"
                 and executor.serves(s, state) == (code, "defence") and s["code"] not in busy
                 and (s.get("place") or {}).get("sector") == home_sector
                 and _hull_share(s) >= RAID_GO_FROM]
        # The ones left stay home: ship11c-camp had none when 8 XL came to the station.
        if (len(ready) < enough + (goal.get("raid_home") or 0)
                or strategy.fighters_flying(state) < (goal.get("fighters_per_destroyer") or 0) * enough):
            continue
        leader, *rest = [s["code"] for s in ready[:enough]] if goal.get("raid_home") else [s["code"] for s in ready]
        held["raid"] = {"sector": sector, "home": code, "home_sector": home_sector, "leader": leader,
                        "ships": [leader, *rest], "phase": "out", "since": now,
                        "unseen": bool(goal.get("raid_unseen")), "guard": bool(goal.get("raid_guard"))}
        return ([f"command {s} {leader} attack" for s in rest]
                + [f"raid {leader} {sector}" + (" stay" if goal.get("raid_guard") else "")])
    return []


def build_method(state: dict, data: dict) -> list[str]:
    """Each station of ours builds with the default method, once.

    A Terran character makes Terran the global method, and start6's first
    destroyer from our own bay waited 9.3 game hours on metallic microlattice,
    a Terran ware none of our modules makes. The save does not say a station's
    method, so this is sent once per station and the bridge logs what it was.
    """
    done = _done(data, "buildmethod")
    out = []
    for st in state.get("assets", []):
        if st.get("cls") == "station" and st.get("code") not in done:
            _mark(data, "buildmethod", st["code"])
            out.append(f"buildmethod {st['code']} default")
    return out


def fleet(state: dict, data: dict) -> list[str]:
    """Ships toward a strategist's numbers (strategy.fleet); nothing without a plan."""
    import strategy
    return strategy.fleet(state, data)


def avoid_sectors(state: dict, data: dict) -> list[str]:
    """The plan's `avoid_sectors` join the hostile blacklist, each once.

    Hatikvah's Choice I is no enemy's, so the blacklist by relation let our
    freighters through: nine traders and four miners died there or beyond it
    in start7 to start8c, one with six of our destroyers in the sector.
    """
    import strategy
    done = _done(data, "avoidsector")
    out = []
    for goal in strategy.goals(data).values():
        for sector in goal.get("avoid_sectors") or []:
            if sector not in done:
                _mark(data, "avoidsector", sector)
                out.append(f"avoid sector {sector} on")
    return out


def civilians_flee(state: dict, data: dict) -> list[str]:
    """Each scout, freighter and miner of ours answers an attack by fleeing,
    once per ship; warships keep the game's own answer.

    The player's call (2026-11-03): in start7 to start8b fifteen scouts, eight
    freighters and four miners were lost. A scout's purpose is fight, as a
    destroyer's is, so this is set ship by ship, not for a purpose (`respond`).
    """
    import executor
    done = _done(data, "flee")
    out = []
    for ship in state.get("assets", []):
        kind = sitrep.ship_type(ship.get("macro"))
        civilian = kind == "scout" or kind in executor.FREIGHTERS or executor._miner_kind(ship.get("macro"))
        if civilian and ship.get("code") and ship["code"] not in done:
            _mark(data, "flee", ship["code"])
            out.append(f"shiprespond {ship['code']} attacked flee")
    return out


RULES = (sell_limits, revisit, satellites, watch, ledger, once, avoid_sectors, civilians_flee, patrols, build_method,
         find_builds, hire_builders, own_stock, repairs, seminars, scouts, empty_builds, docks, managers, shiptraders,
         cargo_drones, accounts, undock_fleet, wings, raids, fleet, grow)


def commands(state: dict, data: dict, off: set | frozenset = frozenset()) -> list[str]:
    """Every standing rule's commands, except the rules named in `off`."""
    out = []
    for rule in RULES:
        if rule.__name__ not in off:
            out += rule(state, data)
    return out
