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
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

from lxml import etree

SHIP_CLASSES = {"ship_xs", "ship_s", "ship_m", "ship_l", "ship_xl"}
# A build storage is its own component, not part of the station it serves, and
# it keeps its own account. Leaving it out meant the agent could plan a build
# and then have no way of seeing that it had stalled.
ASSET_CLASSES = SHIP_CLASSES | {"station", "buildstorage"}
# Component classes that describe a location in the universe.
PLACE_CLASSES = ("galaxy", "cluster", "sector", "zone")
# Depth at which finished subtrees are released.
CLEAR_DEPTH = 4


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
    owner: str | None = None
    builds: list[str] = field(default_factory=list)
    software: list[str] = field(default_factory=list)
    account: dict[str, str] = field(default_factory=dict)
    offers: list[Offer] = field(default_factory=list)
    production_queue: list[str] = field(default_factory=list)
    production: list[dict] = field(default_factory=list)
    manager: dict | None = None     # stations: the manager and their skill


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
    }


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
        software=[s.get("wares") for s in elem.iter("software") if s.get("wares")],
        account=dict(elem.find("account").items()) if elem.find("account") is not None else {},
    )
    if asset.cls == "buildstorage":
        asset.offers = _offers(elem)
        asset.build = _build_tasks(elem)
    if asset.cls == "station":
        asset.builds = _shipyard(elem)
        asset.manager = _manager(elem)
        asset.offers = _offers(elem)
        asset.production = _production(elem)
        asset.production_queue = [line["ware"] for line in asset.production]
    return asset


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
                if cls in ASSET_CLASSES:
                    if current["owner"] == "player":
                        assets.append(_asset(elem, comps))
                    elif cls == "station" and current["knownto"] == "player":
                        market.append(_asset(elem, comps))
                elif cls in EYES and current["owner"] == "player":
                    for anc in comps:
                        if anc["cls"] == "sector":
                            eyes.add(anc.get("macro"))

            if depth == CLEAR_DEPTH:
                elem.clear()
                parent = elem.getparent()
                if parent is not None:
                    while len(parent) > 1:
                        del parent[0]

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
    }


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
