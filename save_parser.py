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
ASSET_CLASSES = SHIP_CLASSES | {"station"}
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
    software: list[str] = field(default_factory=list)
    account: dict[str, str] = field(default_factory=dict)
    offers: list[Offer] = field(default_factory=list)
    production_queue: list[str] = field(default_factory=list)


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


def latest_save() -> Path:
    """Newest save across all X4 profiles under the Documents folder."""
    root = documents_dir() / "Egosoft" / "X4"
    saves = [p for p in root.glob("*/save/*.xml.gz")]
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
    node = elem.find("orders")
    if node is None:
        return []
    out = []
    for order in node.findall("order"):
        entry = {"order": order.get("order"), "state": order.get("state")}
        params = {p.get("name"): p.get("value") for p in order.findall("param")
                  if p.get("value") is not None}
        if params:
            entry["params"] = params
        out.append(entry)
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
        software=[s.get("wares") for s in elem.iter("software") if s.get("wares")],
        account=dict(elem.find("account").items()) if elem.find("account") is not None else {},
    )
    if asset.cls == "station":
        asset.offers = _offers(elem)
        asset.production_queue = [q.get("ware") for q in elem.iter("queue")
                                  if q.get("ware")]
    return asset


def parse_save(path: str | os.PathLike) -> dict:
    """One streaming pass over the save; returns meta, player and assets."""
    meta: dict = {}
    player: dict = {}
    assets: list[Asset] = []
    market: list[Asset] = []

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

            if depth == CLEAR_DEPTH:
                elem.clear()
                parent = elem.getparent()
                if parent is not None:
                    while len(parent) > 1:
                        del parent[0]

    return {
        "meta": meta,
        "player": player,
        "assets": [asdict(a) for a in assets],
        "known_stations": [asdict(a) for a in market],
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
