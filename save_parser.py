"""Reads an X4 savegame and extracts the player-relevant state.

Streams the gzip with lxml.iterparse and releases finished subtrees, so memory
stays flat. A full X4 save does not fit in memory as a tree on a typical
machine; see docs/environment.md.

Usage:
    python save_parser.py --latest
    python save_parser.py "path/to/save_007.xml.gz" --json state.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

from lxml import etree

import gamedata

SHIP_CLASSES = {"ship_xs", "ship_s", "ship_m", "ship_l", "ship_xl"}
# A build storage is its own component, not part of the station it serves, and
# it keeps its own account. Leaving it out meant the agent could plan a build
# and then have no way of seeing that it had stalled.
ASSET_CLASSES = SHIP_CLASSES | {"station", "buildstorage"}
# Component classes that describe a location in the universe.
PLACE_CLASSES = ("galaxy", "cluster", "sector", "zone")
# Depth at which finished subtrees are released.
CLEAR_DEPTH = 4
# How far back, in game seconds, the bridge's logbook lines are kept.
LOGBOOK_WINDOW = 7200
# A faction at or below this standing with the player shoots on sight. The save
# keeps Yaki and outlaws at -0.32 and Xenon and Kha'ak at -1, and the game's
# own UI calls both hostile.
HOSTILE_AT = -0.32
ALWAYS_HOSTILE = {"xenon", "khaak"}


# --------------------------------------------------------------------------- #
# data model
# --------------------------------------------------------------------------- #

@dataclass
class Offer:
    ware: str
    side: str            # "buy" or "sell", from the station's point of view
    price: float | None  # credits (the save stores hundredths of a credit)
    amount: int | None
    desired: int | None


@dataclass
class Asset:
    cls: str
    macro: str | None
    code: str | None
    id: str | None
    connection: str | None          # "space" = free, "dock" = docked
    place: dict[str, str] = field(default_factory=dict)
    docked_at: str | None = None    # code of the object this hangs off
    orders: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    cargo: dict[str, int] = field(default_factory=dict)
    build: dict = field(default_factory=dict)
    reservations: list[dict] = field(default_factory=list)
    owner: str | None = None
    builds: list[str] = field(default_factory=list)
    assignment: dict = field(default_factory=dict)
    attack: dict = field(default_factory=dict)
    software: list[str] = field(default_factory=list)
    account: dict[str, str] = field(default_factory=dict)
    offers: list[Offer] = field(default_factory=list)
    # Prices fixed by hand or by us, which the manager no longer moves: {ware: {buy, sell}}.
    price_overrides: dict[str, dict[str, int]] = field(default_factory=dict)
    production_queue: list[str] = field(default_factory=list)
    production: list[dict] = field(default_factory=list)
    manager: dict | None = None     # stations: the manager and their skill
    modules: list[str] = field(default_factory=list)   # stations: built module macros
    capacity: dict[str, int] = field(default_factory=dict)  # stations: cargo type -> max
    plot: dict[str, int] = field(default_factory=dict)  # stations: buildplot half-extents, m
    workforce: dict = field(default_factory=dict)  # stations: {"amount": {race: n}, "capacity": n}
    hull: float | None = None   # ships: current hull, only written when damaged
    loop: int | None = None     # ships: <orders loop="N">, the order queue repeats
    # A station and its build storage are linked by a connection pair: the
    # station's "buildingmodule" connection id appears as <connected> inside the
    # build storage. Resolved to codes after the pass, both ways.
    links: list[str] = field(default_factory=list)
    buildstorage: str | None = None   # stations: code of their build storage
    station: str | None = None        # build storages: code of their station


# --------------------------------------------------------------------------- #
# locating the save
# --------------------------------------------------------------------------- #

def documents_dir() -> Path:
    """The real Documents path, which Windows may have redirected.

    Do not assume ~/Documents. On a machine with OneDrive folder redirection
    this can point at an entirely different drive, and hardcoding the home
    directory silently finds nothing.
    """
    if sys.platform == "win32":
        import winreg

        key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return Path(winreg.QueryValueEx(handle, "Personal")[0])
    return Path.home() / "Documents"


# X4 writes to this name while a save is in progress and renames it afterwards.
# It is the newest file in the folder exactly when the agent asks for a fresh
# save, and reading it gives "Compressed file ended before the end-of-stream
# marker was reached". Worse, a failed save leaves it behind, so it can sit
# there looking like the newest save indefinitely.
IN_PROGRESS = "temp_save.xml.gz"


def latest_save() -> Path:
    """Newest finished save across all X4 profiles under the Documents folder."""
    root = documents_dir() / "Egosoft" / "X4"
    saves = [p for p in root.glob("*/save/*.xml.gz") if p.name != IN_PROGRESS]
    if not saves:
        raise FileNotFoundError(f"no saves found under {root}")
    return max(saves, key=lambda p: p.stat().st_mtime)


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

def _events(path: str | os.PathLike):
    path = str(path)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        # huge_tree: X4 saves exceed libxml2's default limits.
        yield from etree.iterparse(fh, events=("start", "end"), huge_tree=True)


def _int(value: str | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _orders(elem) -> list[dict]:
    """Orders of an object, the active one first.

    An object usually carries a `default="1"` fallback order (typically Wait)
    plus zero or more real orders. The fallback is written first in the file, so
    naively taking orders[0] reports a busy ship as idle. Measured on a scout
    that had just been given an Explore order: the file held the default Wait
    first and `<order order="Explore" state="started">` second.
    """
    node = elem.find("orders")
    if node is None:
        return []
    out = []
    for order in node.findall("order"):
        entry = {"order": order.get("order"),
                 "state": order.get("state"),
                 "failed": order.get("failed") == "1",
                 "default": order.get("default") == "1"}
        params = {p.get("name"): p.get("value") for p in order.findall("param")
                  if p.get("value") is not None}
        if params:
            entry["params"] = params
        out.append(entry)

    # Active first: a started, non-default order beats everything else.
    out.sort(key=lambda o: (o["default"], o["state"] != "started"))
    return out


def _cargo(elem) -> dict[str, int]:
    """What this object is carrying, as {ware: amount}.

    Cargo does not sit on the ship. It sits on the storage module hanging off
    it: ship -> connections/connection/component[class=storage] -> cargo -> ware.
    Deliberately one level of connections and no deeper, because a docked ship
    is itself nested under its host, and `iter` would hand a station the cargo of
    everything parked on it.

    An empty hold writes no element at all, which is why this looked absent at
    first on exactly the ships it was wanted for. See lesson L1: a missing
    element is a value.
    """
    out: dict[str, int] = {}
    for ware in elem.findall("connections/connection/component/cargo/ware"):
        name, amount = ware.get("ware"), _int(ware.get("amount"))
        if name and amount:
            out[name] = out.get(name, 0) + amount
    return out


def _failures(elem) -> list[dict]:
    """Why the game itself says an order could not be carried out.

    X4 records this next to the orders, with a game timestamp and a message in
    plain English:

        <order order="MiningRoutine" state="started" failed="1"/>
        <failed time="20806.193" order="MiningRoutine"
                message="No buyers found in allowed sectors."/>

    This is worth more than anything the agent could infer from the outside. A
    miner that cannot sell what it digs up is still formally on a mining order,
    so it is not idle and nothing about its state looks wrong; the only evidence
    is this line, written by the part of the game that actually tried.
    """
    node = elem.find("orders")
    if node is None:
        return []
    out = []
    for failed in node.findall("failed"):
        out.append({"order": failed.get("order"),
                    "message": failed.get("message"),
                    "time": float(failed.get("time") or 0)})
    out.sort(key=lambda f: f["time"])
    return out


def _price_overrides(elem) -> dict[str, dict[str, int]]:
    """trade/prices/override/ware: the prices a station keeps fixed, in Cr,
    0 for a side that follows the manager. Kept in the save until cleared."""
    out = {}
    for ware in elem.iterfind("trade/prices/override/ware"):
        name = ware.get("ware")
        sides = {s: _int(ware.get(s)) or 0 for s in ("buy", "sell")}
        if name and any(sides.values()):
            out[name] = sides
    return out


def _ships_on_order(elem, wharf: str | None) -> list[dict]:
    """Ships the player paid for at this wharf that it has not delivered.

    A purchase is a build task in the wharf's own queue, paid in full when it
    is placed: `buildtasks/queue/build type="buildship" faction="player"` with
    the order's time and `transferred`, and `resources/insufficient` naming
    what the wharf still lacks. In the strategist run of 2026-10-26, 24 of the
    28 ships bought at SCY-867 were still queued at the end, 22.7 M Cr paid,
    the wharf short of advanced electronics; the next one was bought anyway.
    """
    return [{"wharf": wharf, "macro": b.get("macro"), "since": float(b.get("time") or 0),
             "paid": _int(b.get("transferred")) or 0,
             "missing": [w.get("ware") for w in b.iterfind("resources/insufficient/ware") if w.get("ware")]}
            for b in elem.iterfind("buildtasks/*/build")
            if b.get("type") == "buildship" and b.get("faction") == "player"]


def _offers(elem) -> list[Offer]:
    """A station's trade offers: trade/offers/production/trade."""
    node = elem.find("trade/offers")
    if node is None:
        return []
    out = []
    for trade in node.iter("trade"):
        ware = trade.get("ware")
        if not ware:
            continue
        side = "buy" if trade.get("buyer") else "sell" if trade.get("seller") else "?"
        raw_price = _int(trade.get("price"))
        out.append(Offer(
            ware=ware,
            side=side,
            # Prices are stored in hundredths of a credit: energycells 1900 = 19 Cr.
            price=round(raw_price / 100, 2) if raw_price is not None else None,
            amount=_int(trade.get("amount")),
            desired=_int(trade.get("desired")),
        ))
    return out


# Skill values in the save run 1 to 15, displayed in game as 0 to 5 stars.
# Measured across 101,543 skill entries in a late-game save: every value from
# 1 to 15 occurs and nothing above 15, so three points make a star.
SKILL_POINTS_PER_STAR = 3


def _manager(elem) -> dict | None:
    """The station's manager and their management skill.

    This matters more than it looks. The manager's skill sets how far the
    station may look for trades: the rule of thumb is three stars for three
    jumps of range. A one-star manager cannot see a supplier two sectors away,
    and the trade orders it hands out simply fail. Without this field in the
    sitrep the planner sees a stalled station and no reason for it.
    """
    post = elem.find("control/post[@id='manager']")
    if post is None or not post.get("component"):
        return None
    wanted = post.get("component")

    for npc in elem.iter("component"):
        if npc.get("id") != wanted:
            continue
        skills = npc.find("traits/skills")
        raw = _int(skills.get("management")) if skills is not None else None
        return {
            "code": npc.get("code"),
            "name": npc.get("name"),
            "management_raw": raw,
            "management_stars": (raw // SKILL_POINTS_PER_STAR) if raw else 0,
        }
    return {"code": None, "name": None, "management_raw": None,
            "management_stars": None}


def _production(elem) -> list[dict]:
    """Production lines of a station, with what each one is short of.

    A line appears here as soon as the module is planned, so its presence does
    not mean the station is producing that ware yet. The shortage is the useful
    part: it says how much of an input the line is missing, which is a much
    sharper number than the stock on a trade offer.
    """
    out = []
    for queue in elem.iter("queue"):
        ware = queue.get("ware")
        if not ware:
            continue
        short = {w.get("ware"): _int(w.get("amount"))
                 for w in queue.findall("shortage/ware") if w.get("ware")}
        out.append({"ware": ware, "short_of": short})
    return out


# Ship classes a build module can produce, read out of its macro name:
# buildmodule_gen_ships_m_dockarea_01_macro builds M ships. There is no station
# macro that says "wharf"; only Xenon shipyards carry it in their own macro, and
# every faction wharf looks like an ordinary station until you look at what
# modules it has. Searching for "wharf" finds nothing, which is why the agent
# concluded it knew no shipyards at all.
SHIP_SIZES = ("xs", "s", "m", "l", "xl")


def _shipyard(elem) -> list[str]:
    """Which ship classes this station can build, empty if it is not a wharf."""
    classes = set()
    for comp in elem.iter("component"):
        if comp.get("class") != "buildmodule":
            continue
        parts = (comp.get("macro") or "").split("_")
        if "ships" not in parts:
            continue
        after = parts[parts.index("ships") + 1:]
        if after and after[0] in SHIP_SIZES:
            classes.add(after[0])
    return sorted(classes, key=SHIP_SIZES.index)


def _reservations(elem) -> list[dict]:
    """Open trades at this station, and whether the other side is ours.

    The only honest measure of whether outside traders come to us. A falling
    stock level does not prove a sale: it can equally be one of our own
    freighters loading up to carry the goods somewhere else, which is the
    expensive way to move them. Measured once and it was ten out of ten.
    """
    node = elem.find("trade/reservations")
    if node is None:
        return []
    out = []
    for r in node.findall("reservation"):
        out.append({"ware": r.get("ware"),
                    "amount": _int(r.get("amount")),
                    "selling": r.get("seller") is not None,
                    "other": r.get("reserver")})
    return out


def _build_tasks(elem) -> dict:
    """What a build storage is working on, and what it still lacks.

    Structure, measured on a live build:

        <buildtasks>
          <queue><build type="expand" .../></queue>
          <inprogress><build type="expand" .../></inprogress>
        </buildtasks>

    The shortfall is the interesting part. A build with money and no deliveries
    looks exactly like a build with neither, and the difference decides whether
    anything can be done about it.
    """
    node = elem.find("buildtasks")
    if node is None:
        return {}
    return {
        "queued": len(node.findall("queue/build")),
        "in_progress": len(node.findall("inprogress/build")),
        # Each queued build's whole sequence, by macro: what stands already and
        # what it adds. KYV-745's refined metals expansion queued a build of
        # its 28 standing modules and nothing else (executor._adds_nothing).
        "queue": [[e.get("macro") for e in b.iterfind("sequence/entry")]
                  for b in node.iterfind("queue/build")],
        # The running build too: when it was created (`time`) and its sequence.
        # KYV-745's ran from game hour 156 with every module standing, waiting
        # for 270 shields (executor._waits_for_equipment).
        "running": [{"since": float(b.get("time") or 0),
                     "sequence": [e.get("macro") for e in b.iterfind("sequence/entry")]}
                    for b in node.iterfind("inprogress/build")],
    }


def _assignment(elem) -> dict:
    """Whether this ship works for a commander, and in what role.

    A subordinate carries `<subordinate group="1"/>` and nothing else; the
    meaning of the group lives on the commander, as
    `<group index="1" assignmment="trade"/>` (the doubled m is the game's own
    spelling). There is no commander pointer on the ship at all.

    This matters because the order alone lies about it. An assigned trader still
    shows TradeRoutine as its default behaviour, exactly like a freelancer on
    autotrade, so reading orders led to the conclusion that six assigned
    freighters were trading for themselves.
    """
    node = elem.find("subordinate")
    if node is None:
        return {}
    return {"group": _int(node.get("group"))}


def _groups(elem) -> dict[int, str]:
    """A commander's subordinate groups: {1: "trade", 2: "mining"}."""
    node = elem.find("subordinates")
    if node is None:
        return {}
    out = {}
    for group in node.findall("group"):
        index = _int(group.get("index"))
        # X4 spells it with two m's. Read both, in case that is ever fixed.
        role = group.get("assignmment") or group.get("assignment")
        if index and role:
            out[index] = role
    return out


def _attack(elem, now: float) -> dict:
    """The last time somebody hit this object, if it was recent enough to matter.

    X4 keeps `attacker`, `attackmethod` and `attacktime` right on the component.
    Nothing in this project looked at them, so an agent could plan an empire
    while its freighters were being shot at.
    """
    when = elem.get("attacktime") or elem.get("shipattacktime")
    if not when:
        return {}
    return {"method": elem.get("attackmethod"), "time": float(when)}


def _asset(elem, ancestors: list[dict]) -> Asset:
    """Build an Asset from a component element plus its ancestor chain."""
    place = {}
    for anc in ancestors:
        if anc["cls"] in PLACE_CLASSES:
            place[anc["cls"]] = anc.get("macro") or anc.get("code") or "?"

    docked_at = None
    for anc in reversed(ancestors):
        if anc["cls"] in ASSET_CLASSES:
            docked_at = anc.get("code")
            break

    asset = Asset(
        cls=elem.get("class"),
        macro=elem.get("macro"),
        code=elem.get("code"),
        id=elem.get("id"),
        connection=elem.get("connection"),
        place=place,
        docked_at=docked_at,
        orders=_orders(elem),
        failures=_failures(elem),
        cargo=_cargo(elem),
        owner=elem.get("owner"),
        assignment=_assignment(elem),
        attack=_attack(elem, 0.0),
        software=[s.get("wares") for s in elem.iter("software") if s.get("wares")],
        account=dict(elem.find("account").items()) if elem.find("account") is not None else {},
    )
    if asset.cls == "station":
        asset.links = [c.get("id") for c in elem.iterfind("connections/connection")
                       if c.get("connection") == "buildingmodule" and c.get("id")]
    if asset.cls == "buildstorage":
        # The pair sits deep: build storage > buildmodule > buildprocessor >
        # connection "buildanchor" > <connected>.
        asset.links = [c.get("connection") for c in
                       elem.iterfind(".//connection[@connection='buildanchor']/connected")
                       if c.get("connection")]
        asset.offers = _offers(elem)
        asset.price_overrides = _price_overrides(elem)
        asset.build = _build_tasks(elem)
        asset.build["builders"] = _builders(elem)
        asset.build["processor"] = _processor(elem)
    if asset.cls in SHIP_CLASSES:
        orders = elem.find("orders")
        if orders is not None and orders.get("loop") is not None:
            asset.loop = _int(orders.get("loop"))
        hull = elem.find("hull")
        if hull is not None and hull.get("value"):
            asset.hull = float(hull.get("value"))
        # A ship that commands others carries their roles the same way a
        # station does: <subordinates><group index=".." assignmment=".."/>.
        groups = _groups(elem)
        if groups:
            asset.assignment = dict(asset.assignment, groups=groups)
    if asset.cls == "station":
        asset.reservations = _reservations(elem)
        asset.assignment = {"groups": _groups(elem)}
        asset.builds = _shipyard(elem)
        asset.manager = _manager(elem)
        asset.offers = _offers(elem)
        asset.price_overrides = _price_overrides(elem)
        asset.production = _production(elem)
        asset.production_queue = [line["ware"] for line in asset.production]
        asset.modules = _built_modules(elem)
        asset.capacity = gamedata.capacity(asset.modules)
        # Workforce: <workforces><workforce race=".." amount=".."/></workforces>
        # on the station; capacity is the sum over its habitation modules.
        table = gamedata.modules()
        asset.workforce = {
            "amount": {w.get("race"): _int(w.get("amount")) or 0
                       for w in elem.iterfind("workforces/workforce") if w.get("race")},
            "capacity": sum(((table.get(m) or {}).get("workforce") or {}).get("capacity", 0)
                            for m in asset.modules),
        }
        plot = elem.find("buildplot/max")
        if plot is not None:
            asset.plot = {k: int(float(v)) for k, v in plot.items()}
    return asset


def _processor(elem) -> dict:
    """The build that is actually being worked on, and what it is waiting for.

    The buildprocessor holds `<build state="waitingforresources"
    constructionvesselrequired="1" step="6" steps="6" ...>`: the game's own
    word for why a build is not moving. Seen on an NPC build in 9.00.
    """
    node = elem.find(".//component[@class='buildprocessor']/build")
    if node is None:
        return {}
    return {"state": node.get("state"),
            "vessel_required": node.get("constructionvesselrequired") == "1",
            "step": _int(node.get("step")), "steps": _int(node.get("steps"))}


def _built_modules(elem) -> list[str]:
    """The station's modules that stand, by macro.

    A module carries construction="[0x..]", pointing at its entry in the
    station's construction sequence; planned modules have an entry and no
    component. A module being built has a component too, with
    state="construction": GKL-870's water module and store sat like that
    through a whole 33-hour run, its build waiting for money at step 1 of 9,
    and were counted as built, in the score and by every rule.
    """
    return [c.get("macro") for c in elem.iterfind("connections/connection/component[@construction]")
            if c.get("state") != "construction"]


def _builders(elem) -> list[str]:
    """Construction vessels working for this build storage, by component id.

    Every queued or running build names its vessel as builder="[0x..]". Seen on
    an NPC build in a 9.00 save. A player expansion waiting for a vessel names
    the build storage itself there (XQL-000 for KYV-745 in the 73-hour save):
    read as a vessel, it made the build look served, so no builder was ever
    hired and the expansion sat at step 1 of 10 through every run of
    2026-10-19/20. The build storage's own id is not a builder.
    """
    out = []
    own = elem.get("id")
    for build in elem.iterfind("buildtasks/*/build"):
        builder = build.get("builder")
        if builder and builder != "[0x0]" and builder != own and builder not in out:
            out.append(builder)
    return out


# Reading a station's trade offers out of the savegame gives the true, current
# prices, whether or not the player can see them in game. X4 only shows live
# supply and demand where you have eyes: a ship passing through, a station, or a
# satellite. Everywhere else the map shows whatever you saw last time, and the
# save keeps no record of that.
#
# Measured on a 27-hour game: presence in 7 sectors, trade data being read from
# 24. Two thirds of the market picture was information the player did not have.
# Filtering on presence is the closest honest approximation, and it makes buying
# satellites a real move rather than a detail.
#
# Set X4_FULL_MARKET=1 to read everything anyway.
FULL_MARKET = os.environ.get("X4_FULL_MARKET") == "1"
# Player-owned things that count as eyes in a sector.
EYES = {"satellite", "navbeacon", "resourceprobe"}


def _visible(market: list, presence: set[str]) -> list:
    """Known stations in sectors we can actually see into."""
    if FULL_MARKET:
        return market
    return [a for a in market if a.place.get("sector") in presence]


def parse_save(path: str | os.PathLike) -> dict:
    """One streaming pass over the save; returns meta, player and assets."""
    meta: dict = {}
    player: dict = {}
    assets: list[Asset] = []
    market: list[Asset] = []
    eyes: set[str] = set()   # sectors holding a satellite or beacon of ours
    logbook: list[list] = []
    trades: list[tuple] = []   # (time, ware, buyer id, seller id, price in cents, amount)
    on_order: list[dict] = []   # ships we paid for that their wharf has not delivered
    # Hostile ships and stations the player has seen, per sector: what a
    # threat assessment can honestly know (knownto="player", as for markets).
    hostiles: dict[str, dict[str, dict[str, int]]] = {}
    # Construction vessels of other factions the player has seen: who could be
    # hired for a build of ours. Whether one is busy only the game knows.
    builders: list[dict] = []
    # Component id -> sector macro. Orders point at sectors by id, so without
    # this an Explore order is an opaque "[0x2a340]" and there is no way to see
    # that a scout has been sent to explore the sector it is already sitting in.
    sectors: dict[str, str] = {}

    stack: list[str] = []
    comps: list[dict] = []   # ancestor chain of component elements

    for event, elem in _events(path):
        if event == "start":
            stack.append(elem.tag)
            path_key = "/".join(stack)

            if path_key == "savegame/info/game":
                meta.update({
                    "version": elem.get("version"),
                    "build": elem.get("build"),
                    "gamestart": elem.get("start"),
                    "playtime_s": float(elem.get("time") or 0),
                    "modified": elem.get("modified") == "1",
                })
            elif path_key == "savegame/info/save":
                meta.update({"save_name": elem.get("name"),
                             "save_date": _int(elem.get("date"))})
            elif path_key == "savegame/info/player":
                # Note: this money value is in whole credits, unlike trade
                # prices and unlike player.money on the Mission Director side.
                player.update({"name": elem.get("name"),
                               "money": _int(elem.get("money"))})
            elif elem.tag == "log" and elem.get("type") == "trade" and elem.get("seller"):
                # A completed trade: who sold what to whom, at what price (in
                # hundredths of a credit). Kept for our stations' own books
                # (_trade_book), resolved to codes after the pass.
                trades.append((float(elem.get("time") or 0), elem.get("ware"), elem.get("buyer"),
                               elem.get("seller"), _int(elem.get("price")), _int(elem.get("v"))))
            elif (elem.tag == "entry" and len(stack) > 1 and stack[-2] == "log"
                  and (elem.get("text") or "").startswith("[x4-agent")):
                # What the bridge wrote into the player's logbook: its orders, and
                # the Lua side's refusals, which nothing else reports.
                logbook.append([float(elem.get("time") or 0), elem.get("text")])
            elif elem.tag == "component":
                comps.append({"cls": elem.get("class"), "macro": elem.get("macro"),
                              "code": elem.get("code"), "owner": elem.get("owner"),
                              "knownto": elem.get("knownto")})
        else:
            depth = len(stack)
            stack.pop()

            if elem.tag == "component":
                current = comps.pop()
                cls = current["cls"]
                if cls == "player":
                    # Blueprints the player holds, as ware ids (module_*, ship_*).
                    player["blueprints"] = sorted(
                        b.get("ware") for b in elem.iterfind("blueprints/blueprint")
                        if b.get("ware"))
                    # The ship the player sits in, by component id; resolved to a
                    # code after the pass. Never one to send on an errand.
                    player["_lastcontrolled"] = elem.get("lastcontrolled")
                    # What the player carries: seminars among it. A missing
                    # amount is one (lesson L1: omitted values have a meaning).
                    player["inventory"] = {
                        w.get("ware"): _int(w.get("amount")) or 1
                        for w in elem.iterfind("inventory/ware") if w.get("ware")}
                if cls == "sector" and elem.get("id"):
                    sectors[elem.get("id")] = current["macro"]
                owner = current["owner"]
                if (cls in ("ship_l", "ship_xl") and owner and owner != "player"
                        and current["knownto"] == "player"
                        and "builder" in (current["macro"] or "")):
                    builders.append({"code": current["code"], "owner": owner,
                                     "sector": next((a.get("macro") for a in reversed(comps)
                                                     if a["cls"] == "sector"), None)})
                if ((cls in SHIP_CLASSES or cls == "station") and owner and owner != "player"
                        and current["knownto"] == "player"
                        and (owner in ALWAYS_HOSTILE
                             or (player.get("relations") or {}).get(owner, 0) <= HOSTILE_AT)):
                    sector = next((a.get("macro") for a in reversed(comps)
                                   if a["cls"] == "sector"), None)
                    if sector:
                        counts = hostiles.setdefault(sector, {}).setdefault(owner, {})
                        counts[cls] = counts.get(cls, 0) + 1
                if cls == "station":
                    on_order += _ships_on_order(elem, current["code"])
                if cls in ASSET_CLASSES:
                    if current["owner"] == "player":
                        assets.append(_asset(elem, comps))
                    elif cls == "station" and current["knownto"] == "player":
                        market.append(_asset(elem, comps))
                elif cls in EYES and current["owner"] == "player":
                    for anc in comps:
                        if anc["cls"] == "sector":
                            eyes.add(anc.get("macro"))

            if elem.tag == "faction" and elem.get("id") == "player":
                # Reputation and licences. The effective standing is the base
                # relation plus any boosters, the temporary gains from recent
                # deeds; licence thresholds are on the same -1..1 scale.
                relations: dict[str, float] = {}
                for node in elem.iterfind("relations/*"):
                    faction, value = node.get("faction"), node.get("relation")
                    if faction and value:
                        relations[faction] = relations.get(faction, 0.0) + float(value)
                player["relations"] = {k: round(v, 4) for k, v in relations.items()}
                player["licences"] = [
                    {"type": node.get("type"), "faction": faction}
                    for node in elem.iterfind("licences/licence")
                    for faction in (node.get("factions") or "").split()]

            if depth == CLEAR_DEPTH:
                elem.clear()
                parent = elem.getparent()
                if parent is not None:
                    while len(parent) > 1:
                        del parent[0]

    # Resolve every order's target sector now that the whole file has been seen.
    for asset in assets:
        for order in asset.orders:
            target = (order.get("params") or {}).get("targetspace")
            if target and target in sectors:
                order["target_sector"] = sectors[target]

    by_id = {a.id: a.code for a in assets if a.id}
    player["occupied_ship"] = by_id.get(player.pop("_lastcontrolled", None))

    by_link = {link: a for a in assets if a.cls == "station" for link in a.links}
    for storage in (a for a in assets if a.cls == "buildstorage"):
        station = next((by_link[l] for l in storage.links if l in by_link), None)
        if station is not None:
            storage.station, station.buildstorage = station.code, storage.code

    presence = {a.place.get("sector") for a in assets if a.place.get("sector")} | eyes
    visible = _visible(market, presence)

    return {
        "meta": meta,
        "player": player,
        "assets": [asdict(a) for a in assets],
        "known_stations": [asdict(a) for a in visible],
        # What was withheld, so the report can say so instead of quietly
        # showing a smaller market than the player has explored.
        "unseen_stations": len(market) - len(visible),
        "hostiles": hostiles,
        "builders": builders,
        # Sectors where we have eyes: a satellite, beacon or probe of ours.
        "eyes": sorted(e for e in eyes if e),
        # The last two game hours of the bridge's logbook lines, oldest first.
        "logbook": [e for e in logbook
                    if e[0] >= (meta.get("playtime_s") or 0) - LOGBOOK_WINDOW],
        # Who the bridge last put each ship under, over the whole logbook.
        "assigned_to": _assigned_to(logbook),
        # The bridge's refusals to fit a module, over the whole logbook too:
        # in the two-hour window GKL-870's refusal of a shield components
        # module dropped out, and the same expansion was sent again
        # (executor._expansion_refused, ship6-camp).
        "fit_refusals": [e for e in logbook if FIT_REFUSAL in (e[1] or "")],
        # What our stations really sold and bought, from the game's trade log.
        "trades": _trade_book(trades, assets),
        "ships_on_order": on_order,
    }


def _trade_book(trades: list[tuple], assets: list) -> dict:
    """Per station of ours and ware: what it sold to others and bought from
    them, in units and credits, over the span the save's trade log covers.

    The prices a model reasons on are offers; this is what changed hands. In
    the strategist's run KYV-745 sold 33.7 million of water while buying 31.0
    million of ice. Trades between two of our own stations or ships move no
    money and are left out; build storages count as their station.

    Not the whole of our income: over the same 24 game hours of lean4-long,
    credits and accounts grew by 2.67 million an hour while these trades, our
    ships' included, come to about 0.2. Which flows the log leaves out is not
    known yet, so read it for what is bought and sold, not as a profit."""
    ours = {}
    for a in assets:
        if a.id and a.cls == "station":
            ours[a.id] = a.code
    for a in assets:
        if a.id and a.cls == "buildstorage" and a.station:
            ours[a.id] = a.station
    book: dict[str, dict[str, dict[str, float]]] = {}
    times = []
    for time_, ware, buyer, seller, price, amount in trades:
        if not ware or not amount or (seller in ours) == (buyer in ours):
            continue
        side, code = ("sold", ours[seller]) if seller in ours else ("bought", ours[buyer])
        entry = book.setdefault(code, {}).setdefault(ware, {"sold": 0, "sold_cr": 0.0,
                                                            "bought": 0, "bought_cr": 0.0})
        entry[side] += amount
        entry[side + "_cr"] += amount * (price or 0) / 100
        times.append(time_)
    return {"since": min(times) if times else None, "until": max(times) if times else None,
            "stations": book}


# The bridge's logbook line for each assignment it makes (md/x4_agent_bridge.xml).
ASSIGNED = re.compile(r"^\[x4-agent\] ORDER: (\S+) (?:now (?:trades for|mines for|defends|"
                      r"supplies the build storage of) (\S+)|under \S+ as \S+, commander now (\S+))$")


FIT_REFUSAL = "could not build a construction sequence"


def _assigned_to(logbook: list[list]) -> dict[str, str]:
    """{ship: commander} from the bridge's own ORDER lines, the latest winning.

    The save gives a subordinate its group number and nothing else, and every
    commander numbers its groups itself: group 1 was trade on KYV-745 and
    mining on GKL-870, so four miners of GKL-870 read as traders of KYV-745
    and were sent to sell wafers they cannot carry. The bridge logs every
    assignment it makes, and that line names the commander.
    """
    out: dict[str, str] = {}
    for _, text in sorted(logbook, key=lambda e: e[0]):
        m = ASSIGNED.match(text or "")
        if m:
            out[m.group(1)] = m.group(2) or m.group(3)
    return out


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #

def summarise(state: dict) -> str:
    meta, player = state["meta"], state["player"]
    lines = [
        f"save        {meta.get('save_name')}  (X4 {meta.get('version')} "
        f"build {meta.get('build')}, mods: {'yes' if meta.get('modified') else 'no'})",
        f"gamestart   {meta.get('gamestart')}   playtime {meta.get('playtime_s', 0):.0f}s",
        f"player      {player.get('name')}   {player.get('money'):,} credits",
        "",
    ]

    assets = state["assets"]
    ships = [a for a in assets if a["cls"] in SHIP_CLASSES]
    stations = [a for a in assets if a["cls"] == "station"]

    lines.append(f"stations ({len(stations)})")
    for st in stations:
        where = st["place"].get("sector", "?")
        lines.append(f"  {st['code']}  {st['macro']}  in {where}")
        for offer in st["offers"]:
            verb = "buys " if offer["side"] == "buy" else "sells"
            lines.append(f"      {verb} {offer['ware']:<16} "
                         f"{offer['price']:>9,.0f} Cr   stock {offer['amount']}"
                         + (f"  wanted {offer['desired']}" if offer["desired"] else ""))
        if st["production_queue"]:
            lines.append(f"      produces: {', '.join(st['production_queue'])}")

    lines.append("")
    lines.append(f"ships ({len(ships)})")
    for sh in ships:
        order = sh["orders"][0]["order"] if sh["orders"] else "no order"
        docked = f"docked at {sh['docked_at']}" if sh["connection"] == "dock" else "in space"
        where = sh["place"].get("sector", "?")
        lines.append(f"  {sh['code']}  {sh['cls']:<7} {sh['macro']}")
        lines.append(f"      {docked}, sector {where}, order: {order}"
                     + (f", software: {', '.join(sh['software'])}" if sh["software"] else ""))

    known = state["known_stations"]
    lines.append("")
    lines.append(f"known stations owned by others: {len(known)}")
    for st in known:
        lines.append(f"  {st['code']}  {st['macro']}  ({len(st['offers'])} offers)")

    return "\n".join(lines)


def main() -> int:
    # The Windows console runs on cp1252; game names are UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", nargs="?", help="path to the save (.xml.gz)")
    parser.add_argument("--latest", action="store_true",
                        help="pick the newest save automatically")
    parser.add_argument("--json", help="write the full state to this file")
    args = parser.parse_args()

    if args.latest:
        target = latest_save()
        print(f"# save: {target}", file=sys.stderr)
    elif args.save:
        target = Path(args.save)
    else:
        parser.error("give a save path, or use --latest")

    state = parse_save(target)
    if args.json:
        Path(args.json).write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"# state written to {args.json}", file=sys.stderr)
    print(summarise(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
