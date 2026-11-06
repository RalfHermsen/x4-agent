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


WHARF_KEEP = 2000           # of a ware our wharf builds with, kept before the rest is sold


def wharf_sales(state: dict, data: dict) -> list[str]:
    """A station with a ship bay keeps every ware our ships are built from, all of it: from
    191 game hours ZLR-942's new S/M bay held its 7,025 field coils, 19,700 hull parts and
    7,700 advanced electronics, none on offer, and field coils had sold 44.5 M in a day.
    For each such ware it makes, a sell limit of WHARF_KEEP, or what its own lines want
    when that is more; the rest goes on sale. Once per run: the limit stays in the save.
    """
    import executor
    table = gamedata.wares()
    held = (state.get("player") or {}).get("blueprints") or []
    needed = set()
    for bp in held:
        if bp.startswith(("ship_", "engine_", "thruster_", "shield_", "weapon_", "turret_", "missile_")):
            for recipe in ((table.get(bp) or {}).get("recipes") or {}).values():
                needed |= set((recipe.get("inputs") or {}).keys())
    bays = {executor.EXPANSION_MODULES["wharf"][0], executor.EXPANSION_MODULES["wharf_l"][0]}
    done = _done(data, "wharf_sales")
    out = []
    for st in state.get("assets", []):
        if st.get("cls") != "station" or not st.get("code") or not bays & set(st.get("modules") or []):
            continue
        wanted = {o["ware"]: o.get("desired") or 0 for o in st.get("offers") or [] if o.get("side") == "buy"}
        for ware in sorted(set(st.get("production_queue") or []) & needed):
            key = f"{st['code']} {ware}"
            if key in done:
                continue
            _mark(data, "wharf_sales", key)
            out += [f"tradeware {st['code']} {ware} sell on",
                    f"limit {st['code']} {ware} sell {max(WHARF_KEEP, int(wanted.get(ware, 0)))}"]
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
    sweeping = data["standing"].get("sweeping") or {}
    free = sorted((s["code"] for s in stocked if s["code"] not in sweeping
                   and "DeployObjectAtPosition" not in [o.get("order") for o in s.get("orders") or []]),
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
    held = data.get("standing") or {}
    posted = (set(held.get("sector_patrol") or {}) | set(held.get("escorting") or {})     # `fighter_posts`'
              | set(held.get("guarding") or {}))
    out = []
    for ship in state.get("assets", []):
        if (sitrep.ship_type(ship.get("macro")) == "fighter" and sitrep.role_of(ship) == "IDLE"
                and (ship.get("assignment") or {}).get("group") is None
                and ship.get("code") not in sent and ship.get("code") not in posted):
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
        # Not one at work on another build: a pier queued at ZLR-942 would have taken our
        # one vessel from GZI-064's half-built station.
        if (sitrep.ship_type(ship.get("macro")) == "construction vessel"
                and ship.get("owner") == "player" and ship.get("code") not in sent
                and "DeployToStation" not in [o.get("order") for o in ship.get("orders") or []]):
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


SCOUTS_SOLD_PER_CYCLE = 5


def sell_scouts(state: dict, data: dict) -> list[str]:
    """Scouts beyond the plan's number with no satellites left aboard are sold, at the
    nearest known wharf of their race that builds S or M ships (an M fabrication bay
    builds S too). The player's call (2026-11-05): `watch` buys a scout with ten satellites
    whenever none has any left, and by 363 game hours 31 flew, 30 of them empty, for a plan
    of five. The game hands a sold ship over where it is: QUZ-488 went to the Teladi five
    jumps from their wharf. Those with satellites aboard are kept, then the plan's number.
    """
    import catalog
    import strategy
    from purchases import _graph, jumps
    planned = max((goal.get("scouts") or 0 for goal in strategy.goals(data).values()), default=0)
    occupied = (state.get("player") or {}).get("occupied_ship")
    ours = sorted((s for s in catalog._ships(state) if sitrep.ship_type(s.get("macro")) == "scout"
                   and s.get("code") != occupied), key=lambda s: s["code"])
    sweeping = (data.get("standing") or {}).get("sweeping") or {}
    empty = [s for s in ours if not s.get("satellites_aboard") and s["code"] not in sweeping]
    keep = max(0, planned - (len(ours) - len(empty)))
    if not planned or len(empty) <= keep:
        return []
    sent = _done(data, "sold")
    graph = _graph()
    out = []
    for ship in [s for s in empty[keep:] if s["code"] not in sent][:SCOUTS_SOLD_PER_CYCLE]:
        race = (ship.get("macro") or "").split("_")[1:2]
        sector = (ship.get("place") or {}).get("sector")
        yards = [k for k in state.get("known_stations") or [] if set(k.get("builds") or []) & {"s", "m"}
                 and [catalog.RACE.get(k.get("owner"))] == race]
        if yards:
            yard = min(yards, key=lambda k: jumps(graph, sector, (k.get("place") or {}).get("sector")))
            _mark(data, "sold", ship["code"])
            out.append(f"sellship {ship['code']} {yard['code']} {yard.get('owner')}")
    return out


SCOUT_SETTLED = 7200       # game seconds the target's known stations stay the same before the siege
SIEGE_CLEAR = 1800         # game seconds the target has nothing left in the sector before the claim
PLOT_AGAIN = 3600          # game seconds before a plot is asked for again
PHASES = ("scout", "siege", "claim", "base", "patrol", "gate", "done")


def campaign(state: dict, data: dict) -> list[str]:
    """One faction at a time, its sectors one by one (tasks/plan-2026-11.md, phase 2): the
    plan's `campaign`, its phase kept here in memory and turned into goals by
    `strategy.goals`. The player's call on 2026-11-06: grow slowly and steadily at the
    expense of hostile factions, one at a time, every sector taken a base before the next.

    scout:  the sector is swept and its gates watched, until it is swept and what we know
            of the target there has not changed for SCOUT_SETTLED.
    siege:  the home's guard holds it (a guard elsewhere comes home first); until the
            target has no station or build storage left there for SIEGE_CLEAR. A sector
            changes hands when its owner's administration and build modules are gone and
            another's stands (Egosoft wiki, Sector Ownership).
    claim:  the guard's leader buys a plot there, until a station of ours stands in it.
    base:   that station builds the plan's template, its first module the claim, under
            the guard, until that module and its defence discs stand.
    patrol: the guard goes home and a garrison of the home's destroyers takes the sector.
    gate:   no ship of ours lost there for `hold_hours`, and net worth at cost not below
            where the campaign began; then the next sector. A loss starts the clock again.
    """
    import catalog
    import score
    import strategy
    plan = (data.get("strategy") or {}).get("plan") or {}
    spec = plan.get("campaign")
    if not spec or not spec.get("sectors"):
        return []
    held = data.setdefault("standing", {})
    now = (state.get("meta") or {}).get("playtime_s") or 0
    at = data.get("campaign") or {}
    if at.get("faction") != spec["faction"] or at.get("sector") not in spec["sectors"] + [None]:
        at = {"faction": spec["faction"], "sector": None, "taken": [], "bases": {},
              "worth": score.score(state).get("net_worth_cost")}
    if at.get("sector") is None:
        left = [s for s in spec["sectors"] if s not in at["taken"]]
        if not left:
            at["phase"] = "done"
            data["campaign"] = at
            return []
        at.update(sector=left[0], phase="scout", since=now)
    data["campaign"] = at
    sector, phase, faction = at["sector"], at["phase"], spec["faction"]
    ours = {s["code"]: s for s in state.get("assets", []) if (s.get("cls") or "").startswith("ship") and s.get("code")}
    raid = held.get("raid")

    def advance(to):
        at.update(phase=to, since=now)

    def guard_home():
        alive = [ours[c] for c in raid["ships"] if c in ours]
        raid["phase"], raid["since"] = "back", now
        return _fly_home(raid, alive)

    target = _enemy(state, sector, faction)
    if phase == "scout":
        known = (target.get("station") or 0) + (target.get("buildstorage") or 0)
        if known != at.get("known"):
            at["known"], at["known_since"] = known, now
        if sector in (held.get("swept") or []) and now - at.get("known_since", now) >= SCOUT_SETTLED:
            advance("siege")
        return []
    if phase == "siege":
        if raid and raid.get("sector") != sector and raid.get("phase") == "out":
            return guard_home()
        if target.get("station") or target.get("buildstorage"):
            at.pop("clear_since", None)
        elif now - at.setdefault("clear_since", now) >= SIEGE_CLEAR:
            advance("claim")
        return []
    if phase == "claim":
        mine = [st["code"] for st in catalog._stations(state) if (st.get("place") or {}).get("sector") == sector]
        if mine:
            at["bases"][mine[0]] = sector
            at["base"] = mine[0]
            advance("base")
            return []
        leader = (raid or {}).get("leader")
        if (raid and raid.get("sector") == sector and leader in ours
                and (ours[leader].get("place") or {}).get("sector") == sector
                and now - at.get("plotted", -1e9) >= PLOT_AGAIN):
            at["plotted"] = now
            return [f"newplot {leader} 8 {spec.get('plot_cap') or 20_000_000} 30000 0 0"]
        return []
    if phase == "base":
        st = next((s for s in catalog._stations(state) if s.get("code") == at.get("base")), None)
        build = (spec.get("base") or {}).get("build") or {}
        first = next(iter(build), None)
        if st and (not first or strategy.built(st, first) >= build[first]) and (
                strategy.built(st, "defence") >= (build.get("defence") or 0)):
            advance("patrol")
        return []
    if phase == "patrol":
        if raid and raid.get("sector") == sector and raid.get("phase") == "out":
            return guard_home()
        posted = sum(1 for s in (held.get("sector_patrol") or {}).values() if s == sector)
        if posted >= (spec.get("garrison") or 0):
            advance("gate")
            at["clock"] = now
        return []
    if phase == "gate":
        where = held.get("where") or {}
        for when, text in state.get("logbook") or []:
            found = when > at["clock"] and re.search(r"DESTROYED: (\S+) by", text or "")
            if found and (where.get(found.group(1)) or [None])[0] == sector:
                at["clock"] = when
        worth = score.score(state).get("net_worth_cost") or 0
        if now - at["clock"] >= (spec.get("hold_hours") or 10) * 3600 and worth >= (at.get("worth") or 0):
            at["taken"].append(sector)
            at.update(sector=None, phase=None)
        return []
    return []


SWEEP_AGAIN = 600          # game seconds before a sweep cut short is started again


def sweeps(state: dict, data: dict) -> list[str]:
    """The plan's `sweep_sectors` are searched to their edges, one scout each, the nearest:
    `sweep` starts the bridge on the sector's undiscovered spots, nearest first, one leg
    after the other, until it logs the sector SWEPT. Explore stays in a sector's core, and at 416 game hours the
    player saw parts of Silent Witness XII we had never seen; that is where the Pact's base
    and the Kha'ak's new hive had stood unknown. `scouts`, `watch` and `sell_scouts` leave a
    sweeping scout alone.
    """
    import catalog
    import strategy
    from purchases import _graph, jumps
    held = data.setdefault("standing", {})
    sweeping, swept = held.setdefault("sweeping", {}), held.setdefault("swept", [])
    for _, text in state.get("logbook") or []:
        found = re.search(r"SWEPT: (\S+) by", text or "")
        if found and found.group(1) not in swept:
            swept.append(found.group(1))
    occupied = (state.get("player") or {}).get("occupied_ship")
    scouts = [s for s in catalog._ships(state) if sitrep.ship_type(s.get("macro")) == "scout"
              and s.get("code") != occupied]
    alive = {s["code"] for s in scouts}
    for code in [c for c, sector in sweeping.items() if c not in alive or sector in swept]:
        del sweeping[code]
    free = [s for s in scouts if s["code"] not in sweeping
            and "DeployObjectAtPosition" not in [o.get("order") for o in s.get("orders") or []]]
    graph = _graph()
    for sector in [s for goal in strategy.goals(data).values() for s in goal.get("sweep_sectors") or []]:
        if sector in swept or sector in sweeping.values() or not free:
            continue
        scout = min(free, key=lambda s: (jumps(graph, (s.get("place") or {}).get("sector"), sector), s["code"]))
        free.remove(scout)
        sweeping[scout["code"]] = sector
    # The bridge flies the legs one after the other; `sweep` again only for a scout on none,
    # its sweep cut short, and not before the last had time to start. A scout on a leg this
    # run did not start gets one too: a leg of the bridge before 4bfb818 waits for ever, and
    # the new `sweep` takes its place.
    now = (state.get("meta") or {}).get("playtime_s") or 0
    sent = held.setdefault("sweep_sent", {})
    ours = {s["code"]: s for s in scouts}
    out = []
    for code, sector in sweeping.items():
        if (("MoveWait" in [o.get("order") for o in ours[code].get("orders") or []] and code in sent)
                or now - sent.get(code, -1e9) < SWEEP_AGAIN):
            continue
        sent[code] = now
        out.append(f"sweep {code} {sector}")
    return out


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
    # A plan's number is the ceiling too: scouts bought to place satellites raised "the most
    # we have had" to 15 by start8s, with 10 sectors left unknown, and each loss was replaced.
    most = planned or max(st.get("scouts_most", 0), len(ours))
    st["scouts_most"] = most
    now = state.get("meta", {}).get("playtime_s") or 0
    # A scout still at the wharf takes no order yet and stays idle; the explore
    # order sent to it is remembered (agent.py, `sent_at`) and not sent again
    # for a while. QPE-143 was sent one three cycles running.
    sent_at = data.get("sent_at") or {}
    sweeping = st.get("sweeping") or {}
    exploring = [s for s in ours if s["code"] not in sweeping]
    spread, spread_out = _spread_scouts(state, data, exploring, now) if planned else (set(), [])
    out = spread_out + [f"explore {s['code']}" for s in exploring
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
        elif planned == [] and not strategy.goals(data)[st["code"]].get("free_growth", True):
            # The plan stands and says build nothing more: in start8i and start8j
            # the ranking kept adding water, energy cell and field coil modules
            # past every gate, and credits fell 2.7 M a game hour.
            wares = []
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


PIERS = True                # a pier for every station (`docks`)


def docks(state: dict, data: dict) -> list[str]:
    """6.10: a station without a dock gets an M dock, an empty plot first.

    Ships trade at a dock. The expansion path builds only the modules asked
    for, so GKL-870, started from an empty plot with water, had a water
    module and a store and nowhere to dock, and on its 2 km plot no dock
    could be fitted afterwards. So an empty plot starts with its dock. Through
    the same gates as any expansion: the blueprint, one build at a time, and
    not again once the bridge could not fit it.
    A station with its dock and no pier gets a pier, where L and XL ships dock: the
    player's call, when ZXX-974's own destroyers could not dock at their wharf. Not while a
    build of the station has one in it: each run starts without memory, start9f and start9g
    asked ZXX-974 for a pier four times, and our one construction vessel built all four
    before GZI-064's turn came, which looked like a build that took no vessel.
    """
    import catalog
    out = []

    def pier_coming(code):
        for bs in state.get("assets", []):
            if bs.get("cls") == "buildstorage" and bs.get("station") == code:
                build = bs.get("build") or {}
                sequences = list(build.get("queue") or []) + [r.get("sequence") or [] for r in build.get("running") or []]
                return any(m.startswith("pier_") for seq in sequences for m in seq)
        return False
    for st in catalog._stations(state):
        if not st.get("code"):
            continue
        piers = not PIERS or any(m.startswith("pier_") for m in st.get("modules") or []) or pier_coming(st["code"])
        ware = "dock" if not catalog._has_dock(st) else None if piers else "pier"
        if ware:
            command = catalog._through_gates({"type": "expand_station", "station_id": st["code"],
                                              "ware": ware}, state)
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


PATROL_AGAIN = 1800         # game seconds before a sector patrol's fighter is told its Patrol again


def fighter_posts(state: dict, data: dict) -> list[str]:
    """The plan's fighters on their posts. `patrol_sectors` sends free fighters to patrol a
    sector as one group: a leader on a Patrol (`raid ... stay`), told again when it goes, and
    the rest under it in attack; when the leader is lost another leads. `escorts_per_trader` puts free fighters under each of a
    station's traders, in defence. The player's call at 362 game hours: five miners were lost
    to the Kha'ak in Second Contact II Flashpoint past two destroyers on Patrol there, and
    twenty freighters to the Pact over the day. The sector patrols are filled first; `wings`
    and `patrols` leave these fighters alone. A fighter with no commander on a Patrol in one
    of the sectors is that sector's, also in a run that starts with no memory.
    """
    import catalog
    import executor
    import strategy
    held = data.setdefault("standing", {})
    now = (state.get("meta") or {}).get("playtime_s") or 0
    goals = strategy.goals(data)
    sectors = {s: n for goal in goals.values() for s, n in (goal.get("patrol_sectors") or {}).items()}
    # Frigates lead a sector's patrol and join it: a light fighter met a Kha'ak M fighter at
    # even hull and lighter guns, and 32 were lost in a night (start9g to start9i).
    frigates_wanted = {s: n for goal in goals.values() for s, n in (goal.get("patrol_frigates") or {}).items()}
    # And destroyers lead and join it before frigates (tasks/plan-2026-11.md 1.2): no destroyer
    # was lost to the Kha'ak, nine frigates were (start9h to start9m). Not in a sector a guard
    # holds, where a destroyer on its Patrol is the guard's.
    guarded = {g.get("raid_sector") for g in goals.values() if g.get("raid_sector")}
    destroyers_wanted = {s: n for goal in goals.values() for s, n in (goal.get("patrol_destroyers") or {}).items()
                         if s not in guarded}
    for sector in list(frigates_wanted) + list(destroyers_wanted):
        sectors.setdefault(sector, 0)
    ships = catalog._ships(state)
    ours = {s["code"]: s for s in ships}
    fighters = [s for s in ships if sitrep.ship_type(s.get("macro")) == "fighter"]
    # Not the route patrol's frigates: Second Contact II Flashpoint is one of its stops too.
    on_route = set(((held.get("route") or {}).get("ships")) or [])
    frigates = [s for s in ships if sitrep.ship_type(s.get("macro")) == "frigate" and s["code"] not in on_route]
    destroyers = [s for s in ships if sitrep.ship_type(s.get("macro")) == "destroyer" and s["code"] not in on_route
                  and s["code"] not in ((held.get("raid") or {}).get("ships") or [])]
    heavies = frigates + destroyers
    posts = held.setdefault("sector_patrol", {})
    asked = held.setdefault("sector_patrol_asked", {})
    escorting = held.setdefault("escorting", {})

    def queue(ship):
        return [o.get("order") for o in ship.get("orders") or [] if not o.get("default")]
    leaders = held.setdefault("sector_leader", {})
    # A frigate that leads still defends its station, as the route patrol's leader does; it is
    # told apart from that one by the fighters under it.
    led = {executor.serves(s, state)[0] for s in fighters + destroyers if executor.serves(s, state)[1] == "attack"}
    for ship in fighters + heavies:
        sector = (ship.get("place") or {}).get("sector")
        free_or_leading = ((ship.get("assignment") or {}).get("group") is None
                           or (ship in heavies and ship["code"] in led))
        if (free_or_leading and sector in sectors and "Patrol" in queue(ship)
                and not (ship in destroyers and sector not in destroyers_wanted)):
            posts.setdefault(ship["code"], sector)
    # One under a ship of a sector's patrol, in attack, is that sector's too.
    for ship in fighters + heavies:
        boss, role = executor.serves(ship, state)
        if role == "attack" and boss in posts:
            posts.setdefault(ship["code"], posts[boss])
    for code in [c for c, s in posts.items() if c not in ours or s not in sectors]:
        del posts[code]
    for sector in [s for s, c in leaders.items() if c not in posts]:
        del leaders[sector]
    for code in [c for c in asked if c not in posts]:
        del asked[code]
    # An escort whose trader is gone, or that is still free a while after it was sent, is free again.
    for code in [c for c, (trader, since) in escorting.items()
                 if c not in ours or trader not in ours
                 or ((ours[c].get("assignment") or {}).get("group") is None and now - since >= PATROL_AGAIN)]:
        del escorting[code]
    # One sent to guard a station is its guard while on its way there, a while.
    guarding = held.setdefault("guarding", {})
    for code in [c for c, (station, since) in guarding.items()
                 if c not in ours or (executor.serves(ours[c], state) != (station, "defence")
                                      and ((ours[c].get("assignment") or {}).get("group") is not None
                                           or now - since >= PATROL_AGAIN))]:
        del guarding[code]
    free = [s["code"] for s in fighters if s["code"] not in posts and s["code"] not in escorting
            and s["code"] not in guarding
            and (s.get("assignment") or {}).get("group") is None and sitrep.role_of(s) == "IDLE"]
    # With no plan's carrier to fill, a carrier's fighters join a patrol or an escort too: SAP-470
    # kept 36 docked in Silent Witness XI while the Kha'ak shot a freighter there every hour (start9h).
    # A leader is a free one: one under a carrier has a commander to answer to.
    leaders_only = list(free)
    if not any(goal.get("fighters_per_carrier") for goal in goals.values()):
        carriers = {s["code"] for s in ships if sitrep.ship_type(s.get("macro")) == "carrier"}
        free += sorted(s["code"] for s in fighters if s["code"] not in posts and s["code"] not in escorting
                       and s["code"] not in guarding and executor.serves(s, state)[0] in carriers)
    free_frigates = [s["code"] for s in frigates if s["code"] not in posts
                     and (s.get("assignment") or {}).get("group") is None and sitrep.role_of(s) == "IDLE"]
    # Also the whole ones defending a station with frigates for the patrols, at home: at
    # 410 game hours five stood there and none was free. The route patrol keeps its number
    # of them while it is home.
    homes = {a["code"]: (a.get("place") or {}).get("sector") for a in catalog._stations(state)
             if (goals.get(a["code"]) or {}).get("patrol_frigates")}
    busy = set((held.get("raid") or {}).get("ships") or []) | set(held.get("repairing") or {})
    keep = 0 if held.get("route") else max([g.get("route_frigates") or 0 for g in goals.values()
                                            if g.get("route_sectors")] or [0])
    free_frigates += [s["code"] for s in frigates if s["code"] not in posts and s["code"] not in busy
                      and executor.serves(s, state)[1] == "defence" and executor.serves(s, state)[0] in homes
                      and (s.get("place") or {}).get("sector") == homes[executor.serves(s, state)[0]]
                      and _hull_share(s) >= RAID_GO_FROM][keep:]
    # Destroyers come from the station whose plan names them, whole and at home, above its
    # floor (`raid_home`), and above the route patrol's number while the route is home. Each
    # station's for its own sectors: one pool sent ZXX-974's from Silent Witness XI to ZLR-942's
    # post in Second Contact II, four jumps away (dry run before start9o).
    free_destroyers = {}
    for station in catalog._stations(state):
        goal = goals.get(station.get("code")) or {}
        if not goal.get("patrol_destroyers"):
            continue
        floor = (goal.get("raid_home") or 0) + (0 if held.get("route") or not goal.get("route_sectors")
                                                else goal.get("route_destroyers") or 0)
        mine = [s["code"] for s in destroyers if s["code"] not in posts and s["code"] not in busy
                and executor.serves(s, state) == (station["code"], "defence")
                and (s.get("place") or {}).get("sector") == (station.get("place") or {}).get("sector")
                and _hull_share(s) >= RAID_GO_FROM and "Attack" not in queue(s)]
        free_destroyers[station["code"]] = mine[floor:]
    out = []

    def frigate(code):
        return sitrep.ship_type(ours[code].get("macro")) == "frigate"

    def rank(code):
        return {"destroyer": 2, "frigate": 1}.get(sitrep.ship_type(ours[code].get("macro")), 0)
    # A sector's patrol flies as one: a leader on its Patrol and the rest under it in attack.
    # Each on its own Patrol, spread over Second Contact II Flashpoint, five were shot down one
    # by one by the Kha'ak in start9f, and none of the nineteen Kha'ak killed fell to them.
    for sector, n in sectors.items():
        have = sum(1 for c, s in posts.items() if s == sector and frigate(c))
        for code in free_frigates[:max(0, frigates_wanted.get(sector, 0) - have)]:
            posts[code], asked[code] = sector, -1e9
        free_frigates = [c for c in free_frigates if c not in posts]
        have = sum(1 for c, s in posts.items() if s == sector and rank(c) == 2)
        for station, pool in free_destroyers.items():
            n = ((goals.get(station) or {}).get("patrol_destroyers") or {}).get(sector, 0)
            for code in pool[:max(0, n - have)]:
                posts[code], asked[code] = sector, -1e9
                have += 1
            free_destroyers[station] = [c for c in pool if c not in posts]
        mine = sorted(c for c, s in posts.items() if s == sector)
        # The heaviest leads, the one leading first: a destroyer before a frigate before a
        # fighter, and the rest go under it at once.
        # With no memory of it (a new run), the one leading in the save: by name, CLU-930 would
        # have taken Second Contact II's group from TIV-371 and every ship been told again.
        best = max((rank(c) for c in mine), default=0)
        before = leaders.get(sector) or next((c for c in mine if c in led and rank(c) == best
                                              and "Patrol" in queue(ours[c])), None)
        leader = (before if before in mine and best and rank(before) == best else None) or next(
            (c for c in mine if best and rank(c) == best), None) or before or next(
            (c for c in mine if (ours[c].get("assignment") or {}).get("group") is None), None) or (
            mine[0] if mine else next((c for c in free if c in leaders_only), None))
        if leader is None:
            continue
        if before and before != leader:
            for code in mine:
                asked.pop(code, None)
        leaders[sector], posts[leader] = leader, sector
        free = [c for c in free if c != leader]
        if "Patrol" not in queue(ours[leader]) and now - asked.get(leader, -1e9) >= PATROL_AGAIN:
            asked[leader] = now
            out.append(f"raid {leader} {sector} stay")
        for code in mine:
            if (code != leader and executor.serves(ours[code], state) != (leader, "attack")
                    and now - asked.get(code, -1e9) >= PATROL_AGAIN):
                asked[code] = now
                out += [f"release {code}", f"command {code} {leader} attack"]
        have = sum(1 for c, s in posts.items() if s == sector and not rank(c))
        for code in free[:max(0, n - have)]:
            posts[code], asked[code] = sector, now
            out.append(f"command {code} {leader} attack")
        free = [c for c in free if c not in posts]
    # A station's own guard of fighters, `defence_fighters`, before the escorts: the player
    # asked for fifteen at ZLR-942 once the fleet's home moved to Silent Witness XI.
    for station, goal in goals.items():
        n = goal.get("defence_fighters") or 0
        have = ({s["code"] for s in fighters if executor.serves(s, state) == (station, "defence")}
                | {c for c, (st, _) in guarding.items() if st == station})
        for code in free[:max(0, n - len(have))]:
            guarding[code] = [station, now]
            out.append(f"assign {code} {station} defend")
        free = [c for c in free if c not in guarding]
    for station, goal in goals.items():
        per = goal.get("escorts_per_trader") or 0
        if not per:
            continue
        traders = sorted(s["code"] for s in ships if sitrep.ship_type(s.get("macro")) in executor.FREIGHTERS
                         and executor.serves(s, state) in strategy._working(station, "trade"))
        for trader in traders:
            have = ({s["code"] for s in fighters if executor.serves(s, state) == (trader, "defence")}
                    | {c for c, (t, _) in escorting.items() if t == trader})
            for code in free[:max(0, per - len(have))]:
                escorting[code] = [trader, now]
                out.append(f"command {code} {trader} defence")
            free = [c for c in free if c not in escorting]
    return out


def wings(state: dict, data: dict) -> list[str]:
    """A free fighter flies under the destroyer with the fewest, as interception:
    it takes small and medium ships, and docks in the destroyer's four S bays.
    Free means idle, also with a commander on paper: ship9c-camp's 24 sat on Wait
    under theirs, and a run started from a save has no wing in its memory.
    A carrier is filled first, to `fighters_per_carrier`: it repairs and rearms
    the fighters docked in it, and a Colossus docks about 40 S. A fighter that
    guards a station goes to a carrier with room too, as `fleet` makes every idle
    warship a guard; and one under a carrier already counts, as the next run has
    no wing in its memory."""
    import catalog
    import executor
    import strategy
    goals = strategy.goals(data).values()
    per = max((goal.get("fighters_per_destroyer") or 0 for goal in goals), default=0)
    per_carrier = max((goal.get("fighters_per_carrier") or 0 for goal in goals), default=0)
    if not (per or per_carrier):
        return []
    ships = catalog._ships(state)
    codes = {s.get("code") for s in ships}
    wing = data.setdefault("standing", {}).setdefault("wing", {})
    for code in [c for c, leader in wing.items() if c not in codes or leader not in codes]:
        del wing[code]
    carriers = [s["code"] for s in ships if sitrep.ship_type(s.get("macro")) == "carrier"]
    destroyers = [s["code"] for s in ships if sitrep.ship_type(s.get("macro")) == "destroyer"]
    # A sector's patrol and a trader's escort are `fighter_posts`', and a guard is a station's.
    held = data.get("standing") or {}
    posted = set(held.get("sector_patrol") or {}) | set(held.get("escorting") or {})
    stations = {s.get("code") for s in catalog._stations(state)}
    load = {code: 0 for code in carriers + destroyers}
    for ship in ships:
        boss, role = executor.serves(ship, state)
        if sitrep.ship_type(ship.get("macro")) == "fighter" and role == "interception" and boss in load:
            wing.setdefault(ship["code"], boss)
    for leader in wing.values():
        load[leader] = load.get(leader, 0) + 1
    out = []
    for ship in ships:
        free = sitrep.role_of(ship) == "IDLE" or sitrep._first_order(ship) == "Patrol"
        boss, role = executor.serves(ship, state)
        guard = role == "defence" and boss in stations
        if (sitrep.ship_type(ship.get("macro")) != "fighter" or ship.get("code") in wing
                or ship.get("code") in posted or not (free or guard)):
            continue
        leader = next((c for c in carriers if load[c] < per_carrier), None)
        if leader is None:
            if not free:
                continue
            leader = min(destroyers, key=load.get, default=None)
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
    A frigate or a fighter parked so at a station of ours leaves too: in start8s the route
    patrol's leader went out alone while its five lay at ZLR-942, and six of the carrier's
    fighters lay there while it held Silent Witness XI. One in its carrier stays.
    """
    busy = data.get("standing", {}).get("repairing") or {}
    stations = {a.get("code") for a in state.get("assets", []) if a.get("cls") == "station"}
    out = []
    for ship in state.get("assets", []):
        kind = sitrep.ship_type(ship.get("macro"))
        if ship.get("connection") != "dock" or not (
                kind == "destroyer" or (kind in ("frigate", "fighter") and ship.get("docked_at") in stations)):
            continue
        queue = [o.get("order") for o in ship.get("orders") or [] if not o.get("default")]
        if queue == ["DockAndWait"] and ship.get("code") not in busy:
            out.append(f"undock {ship['code']}")
    return out


def _enemy(state: dict, sector: str, faction: str) -> dict:
    """What we have seen of the raid's faction in a sector. The save counts a faction as
    hostile only at -0.32 or below; the Scale Plate Pact, set to -0.032 for start8p, shows
    by its stations we know."""
    import save_parser
    seen = dict(((state.get("hostiles") or {}).get(sector) or {}).get(faction) or {})
    if faction not in save_parser.ALWAYS_HOSTILE:
        known = sum(1 for s in state.get("all_stations") or []
                    if s.get("sector") == sector and s.get("owner") == faction)
        if known > seen.get("station", 0):
            seen["station"] = known
    # A build storage outlives its station and the faction builds again from it.
    storages = sum(1 for b in state.get("build_storages") or []
                   if b.get("sector") == sector and b.get("owner") == faction)
    if storages:
        seen["buildstorage"] = storages
    return seen


def _raid_order(leader: str, sector: str, stay: bool, faction: str) -> str:
    """`raid`, with a guard's stay and, for a faction other than the Xenon, that faction."""
    other = faction != "xenon"
    return f"raid {leader} {sector}" + (" stay" if stay else (" go" if other else "")) + (f" {faction}" if other else "")


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
    # The route patrol's destroyers are its own: `route_patrol` runs first and takes them;
    # and a sector patrol's are `fighter_posts`', which runs first as well.
    on_route = set((held.get("route") or {}).get("ships") or []) | set(held.get("sector_patrol") or {})
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
            left = _enemy(state, raid["sector"], raid.get("faction", "xenon"))
            xl = ((((state.get("hostiles") or {}).get(raid["sector"]) or {}).get("xenon") or {}).get("ship_xl", 0))
            # A guard on its post holds longer than a raid would go. In ship13b-camp 30 stood
            # 15,000 game seconds under up to 4 XL without a loss, then left at 6. Leaving did not
            # stop the XL killing (at least 2 of its 5 went after the recall), and wharf SCY-867
            # fell 5,100 later. A falling hull still brings it home.
            per_xl = RAID_HOLD_PER_XL if raid.get("guard") and raid.get("arrived") else RAID_PER_XL
            strong = xl * per_xl > len(alive)
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
                # A guard on its post is topped up to the plan's number from the whole ships at
                # home, the reserve kept: in start8m six held Hatikvah's Choice I with twenty home,
                # and the player asked for more there.
                if raid.get("guard") and raid.get("arrived"):
                    goal = strategy.goals(data).get(raid["home"]) or {}
                    spare = [s for s in ours.values() if sitrep.ship_type(s.get("macro")) == "destroyer"
                             and s["code"] not in raid["ships"] and s["code"] not in (held.get("repairing") or {})
                             and s["code"] not in on_route
                             and executor.serves(s, state) == (raid["home"], "defence")
                             and (s.get("place") or {}).get("sector") == raid["home_sector"]
                             and _hull_share(s) >= RAID_GO_FROM]
                    short = (goal.get("raid_from") or 0) - len(alive)
                    extra = spare[:max(0, min(short, len(spare) - (goal.get("raid_home") or 0)))]
                    if extra:
                        raid["ships"] += [s["code"] for s in extra]
                        return [f"command {s['code']} {raid['leader']} attack" for s in extra]
                # A station came into sight, or the one it attacked is gone and
                # another stands: the `raid` before this one only found a patrol.
                # A guard asks with its Patrol behind the attack, every time: an Attack put in
                # front takes the queued Patrol with it. In start8y the guard of 20 killed the
                # Pact's base in Silent Witness XII and flew home on its default order. One
                # without its Patrol is told at once.
                queue = [o.get("order") for o in ours[raid["leader"]].get("orders") or [] if not o.get("default")]
                lost = raid.get("guard") and "Patrol" not in queue
                if (raid.get("arrived") and ((left or {}).get("station") or (left or {}).get("buildstorage") or lost)
                        and "Attack" not in queue
                        and (lost or now - raid.get("asked", -1e9) >= RAID_ASK_AGAIN)):
                    raid["asked"] = now
                    return [_raid_order(raid["leader"], raid["sector"], bool(raid.get("guard")),
                                        raid.get("faction", "xenon"))]
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
        # A guard the run before left on its post is taken over, not called home: each run
        # starts with no raid in memory, and start8n called the guard of six home and left
        # Hatikvah's Choice I without one for 1.3 game hours.
        # One posted on the way to a new raid_sector goes on from where it is: in start8p the
        # guard of Hatikvah's Choice I was sent on to Silent Witness XI, two jumps further.
        faction = goal.get("raid_faction") or "xenon"
        if goal.get("raid_guard") and sector and wanted and home:
            import purchases
            graph, home_sector = purchases._graph(), (home.get("place") or {}).get("sector")
            route = purchases.jumps(graph, home_sector, sector)
            # Its Patrol, or the destroyers under it: an Attack in front can take the Patrol, and
            # start9k found RGM-519 on the Kha'ak nest without one and sent all 30 home.
            led = {executor.serves(s, state)[0] for s in ours.values()
                   if sitrep.ship_type(s.get("macro")) == "destroyer" and s["code"] not in on_route
                   and executor.serves(s, state)[1] == "attack"}
            leader = next((s for s in ours.values() if sitrep.ship_type(s.get("macro")) == "destroyer"
                           and (s.get("place") or {}).get("sector") not in (None, home_sector)
                           and purchases.jumps(graph, home_sector, s["place"]["sector"])
                           + purchases.jumps(graph, s["place"]["sector"], sector) == route
                           and ("Patrol" in [o.get("order") for o in s.get("orders") or [] if not o.get("default")]
                                or s["code"] in led)),
                          None)
            if leader:
                under = [s["code"] for s in ours.values() if sitrep.ship_type(s.get("macro")) == "destroyer"
                         and executor.serves(s, state) == (leader["code"], "attack")]
                there = leader["place"]["sector"] == sector
                held["raid"] = {"sector": sector, "home": code, "home_sector": home_sector,
                                "leader": leader["code"], "ships": [leader["code"], *under], "phase": "out",
                                "since": now, "arrived": there, "unseen": bool(goal.get("raid_unseen")),
                                "guard": True, "faction": faction}
                if there:
                    held["raid"]["arrived_at"] = now
                    return []
                return [f"undock {leader['code']}", _raid_order(leader["code"], sector, True, faction)]
        # A run that ends during a raid leaves its destroyers under the leader,
        # and the next one has no raid in its memory: ship9d-camp read 1 of 6.
        # Only the station with the raid: from 418 game hours ZLR-942 keeps its own destroyers
        # with no raid, and it would have called ZXX-974's guard to itself.
        strays = [s for s in ours.values() if sitrep.ship_type(s.get("macro")) == "destroyer"
                  and executor.serves(s, state)[1] == "attack" and s["code"] not in on_route]
        if sector and wanted and home and strays:
            return [f"assign {s['code']} {code} defend" for s in strays]
        # Its leader defends already, and keeps the guard's Patrol until `undock` (`_fly_home`):
        # NQB-447, leader of a guard start8b left out, patrolled Hatikvah's Choice I alone
        # for six game hours of start8c.
        posted = [s for s in ours.values() if sitrep.ship_type(s.get("macro")) == "destroyer" and s["code"] not in on_route
                  and "Patrol" in [o.get("order") for o in s.get("orders") or [] if not o.get("default")]]
        if sector and wanted and home and posted:
            return [f"undock {s['code']}" for s in posted]
        if not (sector and wanted and home):
            continue
        seen = _enemy(state, sector, faction)
        xl = (((state.get("hostiles") or {}).get(sector) or {}).get("xenon") or {}).get("ship_xl", 0)
        enough = goal.get("raid_from") or wanted
        # The ships that go, not the whole fleet: they turn back on arrival by this same sum.
        if (not seen and not goal.get("raid_unseen")) or xl * RAID_PER_XL > enough:
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
                 and s["code"] not in on_route and (s.get("place") or {}).get("sector") == home_sector
                 and _hull_share(s) >= RAID_GO_FROM]
        # The ones left stay home: ship11c-camp had none when 8 XL came to the station.
        if (len(ready) < enough + (goal.get("raid_home") or 0)
                or strategy.fighters_flying(state) < (goal.get("fighters_per_destroyer") or 0) * enough):
            continue
        leader, *rest = [s["code"] for s in ready[:enough]] if goal.get("raid_home") else [s["code"] for s in ready]
        held["raid"] = {"sector": sector, "home": code, "home_sector": home_sector, "leader": leader,
                        "ships": [leader, *rest], "phase": "out", "since": now,
                        "unseen": bool(goal.get("raid_unseen")), "guard": bool(goal.get("raid_guard")),
                        "faction": faction}
        return ([f"command {s} {leader} attack" for s in rest]
                + [_raid_order(leader, sector, bool(goal.get("raid_guard")), faction)])
    return []


HUNTERS = 6                 # a guard's destroyers sent after one ship that attacked ours
HUNT_FOR = 7200             # game seconds an attacker stays worth sending them after
HUNTED_FOR = ("container freighter", "solid miner", "liquid miner", "scout")


def hunts(state: dict, data: dict) -> list[str]:
    """A guard's destroyers go after a ship that attacked one of our freighters, miners or
    scouts in the guard's sector or the one before it on the way, once per attacker. The
    player's plan for 2026-11-05: fleets that keep attacking any enemy from Silent Witness
    XII. A guard on its Patrol did not: in start8z and start9a the Pact's scout QRJ-271 shot
    five freighters in Silent Witness XI, and its bombers kept coming into XII. By hand,
    `hunt` killed each within a cycle or two. The faction is the id MD writes behind the
    attacker's name. Not the Xenon or the Kha'ak, whom the Patrol fights where it stands.
    The hunters are the home reserve's above its floor: a ship under the guard's leader
    drops an Attack on a ship in another sector (start9j: six went after the Pact's KET-043
    in Silent Witness XI and were back on Escort while it shot two more freighters), and
    three of the reserve killed it (start9j). Ships of the guard hunt only in the guard's own
    sector, where theirs held. With hunters that are not the guard's, home counts too: in
    start9c the guard's own had followed Kha'ak off the way and the guard was called home.
    """
    import executor
    import purchases
    import save_parser
    import strategy
    held = data.setdefault("standing", {})
    ours = {s["code"]: s for s in state.get("assets", [])
            if (s.get("cls") or "").startswith("ship") and s.get("code")}
    # Where each of ours was last cycle too: a freighter shot down is not in this save.
    before = held.get("where") or {}
    held["where"] = {code: [(s.get("place") or {}).get("sector"), sitrep.ship_type(s.get("macro"))]
                     for code, s in ours.items()}
    where = {**before, **held["where"]}
    logbook = state.get("logbook") or []
    seen = held.get("hunt_seen")
    held["hunt_seen"] = max([seen or 0.0] + [when for when, _ in logbook])
    raid = held.get("raid")
    # The first cycle reads no lines: those were before this run, their attackers long gone.
    if seen is None or not (raid and raid.get("guard") and raid.get("arrived") and raid.get("phase") == "out"):
        return []
    graph = purchases._graph()
    route = purchases.jumps(graph, raid["home_sector"], raid["sector"])

    def near(sector):
        return sector is not None and (sector in (raid["sector"], raid["home_sector"]) or (
            purchases.jumps(graph, raid["home_sector"], sector) + purchases.jumps(graph, sector, raid["sector"])
            == route))

    def attacking(ship):
        return "Attack" in [o.get("order") for o in ship.get("orders") or [] if not o.get("default")]
    now =(state.get("meta") or {}).get("playtime_s") or 0
    prey = held.setdefault("prey", {})
    for when, text in logbook:
        found = when > seen and re.search(r"(?:ATTACKED|DESTROYED): (\S+) by (\S+) \([^)]*\) \[(\w+)\]", text)
        if not found:
            continue
        victim, attacker, faction = found.groups()
        sector, kind = where.get(victim) or (None, None)
        if faction not in save_parser.ALWAYS_HOSTILE and kind in HUNTED_FOR and near(sector):
            prey.setdefault(attacker, {"faction": faction, "since": when, "sector": sector})
    for code in [c for c, p in prey.items() if now - p["since"] > HUNT_FOR]:
        del prey[code]
    busy = (set(raid["ships"]) | set(held.get("repairing") or {})
            | set((held.get("route") or {}).get("ships") or []) | set(held.get("sector_patrol") or {}))
    reserve = [c for c, s in ours.items() if sitrep.ship_type(s.get("macro")) == "destroyer" and c not in busy
               and executor.serves(s, state) == (raid["home"], "defence")
               and (s.get("place") or {}).get("sector") == raid["home_sector"]
               and _hull_share(s) >= RAID_GO_FROM and not attacking(s)]
    floor = (strategy.goals(data).get(raid["home"]) or {}).get("raid_home") or 0
    spare = reserve[:max(0, len(reserve) - floor)]
    sent = _done(data, "hunt")
    for code, p in prey.items():
        if code in sent:
            continue
        guard = [c for c in raid["ships"] if c in ours and c != raid["leader"]
                 and (ours[c].get("place") or {}).get("sector") == raid["sector"] and not attacking(ours[c])]
        hunters = spare or (guard if p.get("sector", raid["sector"]) == raid["sector"] else [])
        if not hunters:
            continue
        _mark(data, "hunt", code)
        return [f"hunt {c} {code} {p['faction']}" for c in hunters[:HUNTERS]]
    return []


ROUTE_DWELL = 1800          # game seconds the route patrol stays at each stop
ROUTE_BACK_BELOW = 0.6      # the patrol's hull, as a share of its whole, that sends it home early


def route_patrol(state: dict, data: dict) -> list[str]:
    """The plan's frigates patrol the trade route: out along `route_sectors`, back the
    same way, and home they wait until `route_frigates` whole ones stand again; `repairs`
    and `fleet` see to that. The player asked for it at 191 game hours, after the Scale
    Plate Pact had killed six freighters on the way to the Teladi, most in Black Hole Sun
    IV, the one way there. At each stop the queue goes (`undock`) and a patrol of that
    sector comes in its place; the last stop's patrol would stay queued otherwise.
    With `route_destroyers` a destroyer leads and up to that many go along, those at home
    beyond `raid_home`: by 410 game hours Pact and Fallen Families L destroyers on the
    route had killed freighters a patrol of frigates could not stop (the player chose it).
    """
    import executor
    import strategy
    held = data.setdefault("standing", {})
    now = (state.get("meta") or {}).get("playtime_s") or 0
    ours = {s["code"]: s for s in state.get("assets", [])
            if (s.get("cls") or "").startswith("ship") and s.get("code")}
    code, goal = next(((c, g) for c, g in strategy.goals(data).items()
                       if g.get("route_sectors") and (g.get("route_frigates") or g.get("route_destroyers"))),
                      (None, None))
    route = held.get("route")
    if not goal:
        return []
    if route:
        alive = [ours[c] for c in route["ships"] if c in ours]
        if not alive:
            held.pop("route")
            return []
        if route["leader"] not in ours:
            route["leader"] = alive[0]["code"]
            route.pop("arrived_at", None)
            return ([f"command {s['code']} {route['leader']} attack" for s in alive[1:]]
                    + [f"undock {route['leader']}", f"raid {route['leader']} {route['stops'][route['stop']]} ships"])
        hurt = sum(_hull_share(s) for s in alive) < ROUTE_BACK_BELOW * len(route["ships"])
        here = (ours[route["leader"]].get("place") or {}).get("sector")
        go = [f"undock {route['leader']}", f"raid {route['leader']} {route['stops'][route['stop']]} ships"]
        if not hurt and here == route["stops"][route["stop"]]:
            route.setdefault("arrived_at", now)
            if now - route["arrived_at"] < ROUTE_DWELL:
                return []
            route["stop"] += 1
            route.pop("arrived_at")
            route["sent_at"] = now
            if route["stop"] < len(route["stops"]):
                return [f"undock {route['leader']}", f"raid {route['leader']} {route['stops'][route['stop']]} ships"]
        elif not hurt:
            # Not there after twice a stay: the order is told again.
            if now - route.get("sent_at", route["since"]) >= 2 * ROUTE_DWELL:
                route["sent_at"] = now
                return go
            return []
        held.pop("route")
        return _fly_home({"leader": route["leader"], "home": code, "guard": True}, alive)
    home = next((a for a in state.get("assets", []) if a.get("code") == code), {})
    home_sector = (home.get("place") or {}).get("sector")
    out = list(goal["route_sectors"])
    stops = out + out[-2::-1]
    # A patrol the run before left on the route is taken over where it is: each run
    # starts with no route in memory. Not a sector patrol's frigate, which leads fighters.
    led = {executor.serves(s, state)[0] for s in ours.values()
           if sitrep.ship_type(s.get("macro")) == "fighter" and executor.serves(s, state)[1] == "attack"}
    leader = next((s for kind in ("destroyer", "frigate") for s in ours.values()
                   if sitrep.ship_type(s.get("macro")) == kind and s["code"] not in led
                   and (s.get("place") or {}).get("sector") in stops
                   and "Patrol" in [o.get("order") for o in s.get("orders") or [] if not o.get("default")]), None)
    if leader:
        under = [s["code"] for s in ours.values() if executor.serves(s, state) == (leader["code"], "attack")]
        sector = (leader.get("place") or {}).get("sector")
        held["route"] = {"leader": leader["code"], "ships": [leader["code"], *under], "stops": stops,
                         "stop": stops.index(sector), "since": now, "sent_at": now}
        return []
    raiding = (set((held.get("raid") or {}).get("ships") or []) | set(held.get("repairing") or {})
               | set(held.get("sector_patrol") or {}))

    def ready(kind):
        return [s["code"] for s in ours.values() if sitrep.ship_type(s.get("macro")) == kind
                and executor.serves(s, state) == (code, "defence") and s["code"] not in raiding
                and (s.get("place") or {}).get("sector") == home_sector and _hull_share(s) >= RAID_GO_FROM]
    frigates, want = ready("frigate"), goal.get("route_frigates") or 0
    if len(frigates) < want:
        return []
    destroyers = ready("destroyer")
    destroyers = destroyers[:max(0, min(goal.get("route_destroyers") or 0, len(destroyers) - (goal.get("raid_home") or 0)))]
    if not destroyers and not want:
        return []
    first, *rest = destroyers + frigates[:want]
    held["route"] = {"leader": first, "ships": [first, *rest], "stops": stops, "stop": 0, "since": now,
                     "sent_at": now}
    return [f"command {s} {first} attack" for s in rest] + [f"raid {first} {stops[0]} ships"]


def carriers(state: dict, data: dict) -> list[str]:
    """A carrier with its wing full flies with the guard, under the guard's leader as
    defence, which keeps it near the leader; an auxiliary goes along as supplyfleet and
    repairs and rearms them there. A new guard takes them over from the last, which
    brought them home under its leader. The player asked for both at 182 game hours,
    for the destroyers on guard in Hatikvah's Choice I.
    With a plan's `carrier_station` the carrier guards that station instead: the guard
    held Silent Witness XI, yet the Pact killed three freighters there in start8u and
    start8v near ZXX-974, where its fighters can meet them."""
    import catalog
    import executor
    import strategy
    goals = strategy.goals(data).values()
    post = next((goal.get("carrier_station") for goal in goals if goal.get("carrier_station")), "")
    ships = catalog._ships(state)
    per = max((goal.get("fighters_per_carrier") or 0 for goal in goals), default=0)
    sent = data.setdefault("standing", {}).setdefault("with_guard", {})
    out = []
    if post:
        for ship in ships:
            if (sitrep.ship_type(ship.get("macro")) == "carrier" and executor.serves(ship, state) != (post, "defence")
                    and sent.get(ship["code"]) != post):
                sent[ship["code"]] = post
                out.append(f"assign {ship['code']} {post} defend")
    raid = (data.get("standing") or {}).get("raid")
    if not (raid and raid.get("guard") and raid["phase"] == "out"):
        return out
    leader = raid["leader"]
    for ship in ships:
        kind = sitrep.ship_type(ship.get("macro"))
        role = {"carrier": None if post else "defence", "resupplier": "supplyfleet"}.get(kind)
        if not role or executor.serves(ship, state) == (leader, role) or sent.get(ship["code"]) == leader:
            continue
        if kind == "carrier":
            wing = sum(1 for s in ships if sitrep.ship_type(s.get("macro")) == "fighter"
                       and executor.serves(s, state) == (ship["code"], "interception"))
            if not per or wing < per:
                continue
        sent[ship["code"]] = leader
        out.append(f"command {ship['code']} {leader} {role}")
    return out


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


SELL_AGAIN = 600       # game seconds before an idle runner is sent again: the save lags the order
SELL_FROM = 1000       # units a station offers before a run is worth it
SELL_PROFIT = 1.2      # a bid this far above our own price is worth the trip
SELL_NEAR = 0.95       # bids this close to the best count as the best, and the nearest goes
SELL_FLOOR = 0.9       # the sell order's minimum against the bid seen


def _hops(graph: dict, start: str | None, goal: str | None, blocked: set) -> int | None:
    """Jumps from `start` to `goal` through no sector in `blocked`; None without a way."""
    if not start or not goal or goal in blocked:
        return None
    seen, todo = {start: 0}, collections.deque([start])
    while todo:
        here = todo.popleft()
        if here == goal:
            return seen[here]
        for nxt in graph.get(here, []):
            if nxt not in seen and nxt not in blocked:
                seen[nxt] = seen[here] + 1
                todo.append(nxt)
    return None


def _best_buyer(state: dict, ware: str, ours: float, sector: str, blocked: set,
                graph: dict) -> tuple[dict, float, int] | None:
    """(station, price, wanted) of the nearest buyer paying within SELL_NEAR of the best bid
    in reach, the bid SELL_PROFIT above our price; None if there is none."""
    bids = []
    for station in state.get("known_stations") or []:
        for offer in station.get("offers") or []:
            if (offer.get("ware") == ware and offer.get("side") == "buy" and (offer.get("desired") or 0) > 0
                    and offer.get("price", 0) >= ours * SELL_PROFIT):
                hops = _hops(graph, sector, (station.get("place") or {}).get("sector"), blocked)
                if hops is not None:
                    bids.append((offer["price"], hops, station, offer["desired"]))
    if not bids:
        return None
    best = max(b[0] for b in bids)
    price, _, station, wanted = min((b for b in bids if b[0] >= best * SELL_NEAR), key=lambda b: (b[1], -b[0]))
    return station, price, wanted


def sell_runs(state: dict, data: dict) -> list[str]:
    """The plan's `sell_runs`: freighters of our own take a ware from a station of ours to
    the best bid in reach and sell it there (tasks/plan-2026-11.md 1.5). At 452 game hours
    ZXX-974 and GZI-064 offered refined metals at 92 to 95 Cr, their modules stood still on
    full stores, and buyers 3 to 8 jumps away paid 207 to 212: station traders trade in their
    own range and went to none of them. A free freighter becomes a runner, kept in memory
    (`strategy.fleet` buys one when none is free and hands no runner to a station), and is
    sent again each time it has no orders left. The buyer is the nearest of those paying
    within SELL_NEAR of the best, on a way through no avoided sector."""
    import catalog
    import executor
    import strategy
    from purchases import _graph
    plan = strategy.goals(data)
    held = data.setdefault("standing", {})
    runs, sent = held.setdefault("sell_runs", {}), held.setdefault("sell_sent", {})
    ships = {s["code"]: s for s in catalog._ships(state) if s.get("code")}
    for code in [c for c in runs if c not in ships]:
        del runs[code]
    if not any(g.get("sell_runs") for g in plan.values()):
        return []
    occupied = (state.get("player") or {}).get("occupied_ship")
    lent = {f["ship"] for each in (data.get("feeders") or {}).values() for f in each}
    busy = lent | set(held.get("sector_patrol") or {}) | set(held.get("escorting") or {}) | set(held.get("guarding") or {})
    free = [s for s in ships.values() if s["code"] not in runs and s["code"] not in busy and s["code"] != occupied
            and (s.get("assignment") or {}).get("group") is None and sitrep.role_of(s) == "IDLE"]
    blocked = ({s for g in plan.values() for s in g.get("avoid_sectors") or []}
               - {s for g in plan.values() for s in g.get("open_sectors") or []})
    graph = _graph()
    now = (state.get("meta") or {}).get("playtime_s") or 0
    stations = {a.get("code"): a for a in catalog._stations(state)}
    out = []
    for code, goal in plan.items():
        home = stations.get(code)
        for ware, n in ((goal.get("sell_runs") or {}).items() if home else ()):
            hulls = executor.CARRIES.get((gamedata.wares().get(ware) or {}).get("transport"), ())
            mine = [c for c, (station, w) in runs.items() if station == code and w == ware]
            for ship in [s for s in free if sitrep.ship_type(s.get("macro")) in hulls][:max(0, n - len(mine))]:
                runs[ship["code"]] = [code, ware]
                free.remove(ship)
                mine.append(ship["code"])
            offer = next((o for o in home.get("offers") or [] if o.get("ware") == ware and o.get("side") == "sell"), None)
            if not offer or (offer.get("amount") or 0) < SELL_FROM:
                continue
            found = _best_buyer(state, ware, offer.get("price") or 0, (home.get("place") or {}).get("sector"),
                                blocked, graph)
            if not found:
                continue
            buyer, price, wanted = found
            for c in mine:
                ship = ships[c]
                if (c in lent or (ship.get("assignment") or {}).get("group") is not None
                        or [o for o in ship.get("orders") or [] if not o.get("default")]
                        or now - sent.get(c, -1e9) < SELL_AGAIN):
                    continue
                sent[c] = now
                out.append(f"sellrun {c} {ware} {code} {buyer['code']} {buyer.get('owner')} "
                           f"{int(min(offer['amount'], wanted))} {int(price * SELL_FLOOR)}")
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
    done, opened = _done(data, "avoidsector"), _done(data, "opensector")
    goals = strategy.goals(data).values()
    # A sector listed once stays listed in the game; `open_sectors` takes it off again,
    # once a run: Hatikvah's Choice I, patrolled, between our home and Argon Prime.
    open_ = {s for goal in goals for s in goal.get("open_sectors") or []}
    out = []
    for goal in goals:
        for sector in goal.get("avoid_sectors") or []:
            if sector not in done and sector not in open_:
                _mark(data, "avoidsector", sector)
                out.append(f"avoid sector {sector} on")
    for sector in sorted(open_ - opened):
        _mark(data, "opensector", sector)
        out.append(f"avoid sector {sector} off")
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


RULES = (campaign, sweeps, sell_limits, wharf_sales, revisit, satellites, watch, ledger, once, avoid_sectors, civilians_flee, fighter_posts,
         patrols, build_method,
         find_builds, hire_builders, own_stock, repairs, seminars, sell_scouts, scouts, empty_builds, docks, managers, shiptraders,
         cargo_drones, accounts, undock_fleet, wings, route_patrol, raids, hunts, carriers, sell_runs, fleet, grow)


# Which rule gave which commands in the last call of `commands`, for `invariants.check`,
# and the orders it dropped because a rule before it had the ship that cycle.
LAST_BY_RULE: list[tuple[str, list[str]]] = []
LAST_CLAIMED: list[str] = []


def commands(state: dict, data: dict, off: set | frozenset = frozenset()) -> list[str]:
    """Every standing rule's commands, except the rules named in `off`.

    One owner per ship per cycle (tasks/plan-2026-11.md 0.3): the first rule in RULES to
    give a ship an order has it, and a later rule's order for it is dropped, with a note.
    Settings are not orders. Before this, rules that meet the same ships were kept apart
    one at a time: a station without a raid called the guard to itself, `fleet` and
    `fighter_posts` took one fighter, and the order of RULES decided the rest.
    """
    import invariants
    ships = {a.get("code") for a in state.get("assets", []) if (a.get("cls") or "").startswith("ship")}
    owner: dict[str, str] = {}
    out = []
    LAST_BY_RULE.clear()
    LAST_CLAIMED.clear()
    for rule in RULES:
        if rule.__name__ in off:
            continue
        kept = []
        for command in rule(state, data):
            words = command.split()
            ship = words[1] if len(words) > 1 and words[0] not in invariants.SETTINGS and words[1] in ships else None
            if ship and owner.setdefault(ship, rule.__name__) != rule.__name__:
                LAST_CLAIMED.append(f"CLAIMED: {command} from {rule.__name__} dropped, {ship} is "
                                    f"{owner[ship]}'s this cycle")
                continue
            kept.append(command)
        LAST_BY_RULE.append((rule.__name__, kept))
        out += kept
    return out
