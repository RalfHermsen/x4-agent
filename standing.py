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


def own_stock(state: dict, data: dict) -> list[str]:
    """A build waiting on a ware its own station holds gets it from that station.

    A station offers a resource it still wants more of only above a sell limit
    of its own. Made sellable alone, KYV-745 offered none of its 4,087 turret
    components, because it wanted 12,101 more, and its build waited on 836 of
    them while every other expansion queued behind it (proof-feed, ship7e).
    So: our ships only, then a limit that leaves exactly what the build wants
    on offer, then sellable; the freighter lent to the build storage buys it
    there like from any seller. Lowered when the stock drops, cleared when the
    build no longer wants the ware. A ware the station sells already is left
    alone, and so is one it holds too little of.
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
        if key not in opened and any(o.get("ware") == ware and o.get("side") == "sell"
                                     for o in station.get("offers", [])):
            continue
        limit = ((station.get("cargo") or {}).get(ware) or 0) - amount
        if limit < 0 or (key in opened and opened[key] <= limit):
            continue
        if key not in opened:
            out.append(f"traderule {code} {ware} sell own")
        opened[key] = limit
        out += [f"limit {code} {ware} sell {limit}", f"tradeware {code} {ware} sell on"]
    for key in [k for k in opened if k not in wanted]:
        code, ware = key.split()
        del opened[key]
        out += [f"tradeware {code} {ware} sell off", f"limit {code} {ware} sell clear",
                f"traderule {code} {ware} sell default"]
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


def scouts(state: dict, data: dict) -> list[str]:
    """Scouts explore, and a scout lost doing it is replaced at once.

    The player's decision, 2026-10-21: losing scouts while exploring hostile sectors is part of
    exploring; when one is lost, order a new one straight away. So the number
    of scouts is kept at the most we have had: one short, one is bought (S, at
    the nearest wharf, outside the game hour between purchases, one at a
    time); a scout with no orders is sent exploring.
    """
    import catalog
    ours = [s for s in catalog._ships(state) if sitrep.ship_type(s.get("macro")) == "scout"]
    st = data.setdefault("standing", {})
    most = max(st.get("scouts_most", 0), len(ours))
    st["scouts_most"] = most
    now = state.get("meta", {}).get("playtime_s") or 0
    # A scout still at the wharf takes no order yet and stays idle; the explore
    # order sent to it is remembered (agent.py, `sent_at`) and not sent again
    # for a while. QPE-143 was sent one three cycles running.
    sent_at = data.get("sent_at") or {}
    out = [f"explore {s['code']}" for s in ours
           if sitrep.role_of(s) == "IDLE" and (s.get("assignment") or {}).get("group") is None
           and now - sent_at.get(f"explore {s['code']}", -1e9) > SCOUT_DELIVERY]
    if len(ours) < most and now - st.get("scout_bought_at", -1e9) > SCOUT_DELIVERY:
        # A wharf's M build module builds S ships too; the parser marks such a
        # wharf "m" only, so asking for "s" found no wharf and no lost scout
        # was replaced in the catalog runs c3 and c4.
        options = catalog._buy_options(state, (("scout", "ship_{race}_s_scout_01_a_macro"),),
                                       size="m", gap=False)
        if options:
            st["scout_bought_at"] = now
            out.append(options[0].command)
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
    manager, and left for MANAGER_TRAVEL while they travel.
    """
    import catalog
    import executor
    now = state.get("meta", {}).get("playtime_s") or 0
    sent_at = data.get("sent_at") or {}
    wharf = executor.EXPANSION_MODULES["wharf"][0]
    return [f"shiptrader {st['code']}" for st in catalog._stations(state)
            if st.get("code") and wharf in (st.get("modules") or []) and not st.get("shiptrader")
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

def fleet(state: dict, data: dict) -> list[str]:
    """Ships toward a strategist's numbers (strategy.fleet); nothing without a plan."""
    import strategy
    return strategy.fleet(state, data)


RULES = (sell_limits, revisit, satellites, ledger, once, patrols, find_builds, hire_builders,
         own_stock, repairs, seminars, scouts, empty_builds, docks, managers, shiptraders,
         cargo_drones, accounts, fleet, grow)


def commands(state: dict, data: dict, off: set | frozenset = frozenset()) -> list[str]:
    """Every standing rule's commands, except the rules named in `off`."""
    out = []
    for rule in RULES:
        if rule.__name__ not in off:
            out += rule(state, data)
    return out
