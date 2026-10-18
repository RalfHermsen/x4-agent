"""Reads X4's .cat/.dat archives and turns macro names into readable names.

The save calls sectors things like `cluster_19_sector001_macro`. The real name
lives in the game data: the macro refers to a text ID, and the text database
sits inside the game's .cat archives. This module pulls both out and builds the
translation table.

The cat format is simple: one line per file, `<name> <bytes> <mtime> <md5>`, and
the matching .dat holds the blobs back to back in the same order. File names can
contain spaces, so lines are parsed from the right.

Usage:
    python gamedata.py --build          # builds data/names.json
    python gamedata.py --lookup cluster_19_sector001_macro
    python gamedata.py --modules        # builds data/modules.json

Set X4_DIR if your installation is not in the default Steam location.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from lxml import etree

X4_DIR = Path(os.environ.get(
    "X4_DIR", r"C:\Program Files (x86)\Steam\steamapps\common\X4 Foundations"))
CACHE = Path(__file__).parent / "data" / "names.json"
LANGUAGE = "l044"  # English; the save itself uses language-independent text IDs

# Names of clusters, sectors and zones live here, not with the macro definitions.
MAPDEFAULTS = "libraries/mapdefaults.xml"

_TEXT_REF = re.compile(r"\{(\d+),(\d+)\}")
# Round brackets are comments in X4 text entries, unless escaped.
_COMMENT = re.compile(r"(?<!\\)\([^()]*(?<!\\)\)")


# --------------------------------------------------------------------------- #
# cat/dat
# --------------------------------------------------------------------------- #

def read_index(cat: Path) -> dict[str, tuple[int, int]]:
    """Return {filename: (offset, size)} for a .cat archive."""
    index: dict[str, tuple[int, int]] = {}
    offset = 0
    with cat.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").rsplit(" ", 3)
            if len(parts) != 4:
                continue
            name, size = parts[0], int(parts[1])
            index[name] = (offset, size)
            offset += size
    return index


def archives(x4_dir: Path) -> list[Path]:
    """All .cat archives, base game first, then extensions.

    The `_sig` variants only hold signatures and are skipped.
    """
    base = sorted(p for p in x4_dir.glob("*.cat") if "_sig" not in p.name)
    ext = sorted(p for p in x4_dir.glob("extensions/*/*.cat") if "_sig" not in p.name)
    return base + ext


def extract_all(x4_dir: Path, wanted: str) -> list[bytes]:
    """Every version of a file, base game first, then the DLC patches.

    DLCs do not ship a replacement but an addition: `libraries/mapdefaults.xml`
    occurs seven times in a full install, and only all of them together give the
    complete map.
    """
    out = []
    for cat in archives(x4_dir):
        entry = read_index(cat).get(wanted)
        if not entry:
            continue
        offset, size = entry
        with cat.with_suffix(".dat").open("rb") as fh:
            fh.seek(offset)
            out.append(fh.read(size))
    if not out:
        raise FileNotFoundError(f"{wanted} is in no archive under {x4_dir}")
    return out


def extract(x4_dir: Path, wanted: str) -> bytes:
    """The last version of a file."""
    return extract_all(x4_dir, wanted)[-1]


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #

def load_texts(x4_dir: Path, language: str = LANGUAGE) -> dict[tuple[str, str], str]:
    """Read the text database: {(page, id): text}. DLCs extend pages."""
    parser = etree.XMLParser(huge_tree=True, recover=True)
    texts: dict[tuple[str, str], str] = {}
    for raw in extract_all(x4_dir, f"t/0001-{language}.xml"):
        root = etree.fromstring(raw, parser=parser)
        for page in root.iter("page"):
            page_id = page.get("id")
            for entry in page.iter("t"):
                texts[(page_id, entry.get("id"))] = entry.text or ""
    return texts


def resolve(value: str, texts: dict[tuple[str, str], str], depth: int = 0) -> str:
    """Turn `{20005,1901}` into real text, including nested references."""
    if depth > 4:
        return value

    def swap(match: re.Match) -> str:
        target = texts.get((match.group(1), match.group(2)))
        return resolve(target, texts, depth + 1) if target else match.group(0)

    value = _TEXT_REF.sub(swap, value)
    value = _COMMENT.sub("", value)
    return value.replace("\\(", "(").replace("\\)", ")").strip()


# --------------------------------------------------------------------------- #
# macros
# --------------------------------------------------------------------------- #

def build_names(x4_dir: Path = X4_DIR) -> dict[str, str]:
    """Build {macro name: readable name} for clusters, sectors and zones.

    The names are not attached to the macro definitions but live in
    `libraries/mapdefaults.xml`, one `dataset` per object. DLC copies of that
    file are diff patches; `iter("dataset")` picks the entries out of both
    shapes.
    """
    texts = load_texts(x4_dir)
    names: dict[str, str] = {}
    parser = etree.XMLParser(huge_tree=True, recover=True)

    for raw in extract_all(x4_dir, MAPDEFAULTS):
        root = etree.fromstring(raw, parser=parser)
        for dataset in root.iter("dataset"):
            macro = dataset.get("macro")
            ident = dataset.find("properties/identification")
            if not macro or ident is None:
                continue
            label = resolve(ident.get("name") or "", texts)
            if label:
                names[macro.lower()] = label
    return names


def load(rebuild: bool = False) -> dict[str, str]:
    """Names from cache, or build them if the cache is missing."""
    if CACHE.exists() and not rebuild:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    names = build_names()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")
    return names


MODULES = Path(__file__).parent / "data" / "modules.json"
_MODULE_FILE = re.compile(r"assets/structures/[^/]+/macros/([^/]+_macro)\.xml$")
_CARGO = re.compile(rb'<cargo max="(\d+)" tags="([^"]+)"')
_CLASS = re.compile(rb'<macro name="[^"]+" class="([^"]+)"')
_WORKFORCE = re.compile(rb'<workforce race="([a-z]+)" capacity="(\d+)"')
# A module ware names its macro in a <component ref=...> child. The negative
# lookahead stops at the next ware *definition*; production recipes inside a
# ware are also <ware ...> elements, so "<ware " alone would stop too early.
_MODULE_WARE = re.compile(r'<ware id="([^"]+)"(?:(?!<ware id=).)*?<component ref="([^"]+_macro)"',
                          re.S)


_WARE_BLOCK = re.compile(r'<ware id="(module_[^"]+)"(.*?)</ware>', re.S)
_COMPONENT_REF = re.compile(r'<component ref="([^"]+_macro)"')
_PRICE = re.compile(r'<price min="\d+" average="\d+" max="(\d+)"')
_PRICE_ALL = re.compile(r'<price min="(\d+)" average="(\d+)" max="(\d+)"')
_LICENCE = re.compile(r'<restriction licence="([^"]+)"')
_OWNER = re.compile(r'<owner faction="([^"]+)"')


def build_modules(x4_dir: Path = X4_DIR) -> dict[str, dict]:
    """Every station module macro: its class, its blueprint ware, its storage.

    Storage capacity is not in the savegame; a station only says which modules
    it is built from. The macro file holds `<cargo max=... tags=...>`, and the
    ware that is bought as a blueprint is a different name again
    (`module_tel_stor_container_s_01` for `storage_tel_s_container_01_macro`),
    linked only through libraries/wares.xml.
    """
    modules: dict[str, dict] = {}
    for cat in archives(x4_dir):
        index = read_index(cat)
        with open(cat.with_suffix(".dat"), "rb") as blob:
            for name, (offset, size) in index.items():
                match = _MODULE_FILE.search(name)
                if not match:
                    continue
                blob.seek(offset)
                data = blob.read(size)
                cls = _CLASS.search(data)
                cargo = {}
                for amount, tags in _CARGO.findall(data):
                    for tag in tags.decode().split():
                        cargo[tag] = cargo.get(tag, 0) + int(amount)
                workforce = _WORKFORCE.search(data)
                modules[match.group(1)] = {"class": cls.group(1).decode() if cls else None,
                                           "ware": None, "cargo": cargo,
                                           "workforce": ({"race": workforce.group(1).decode(),
                                                          "capacity": int(workforce.group(2))}
                                                         if workforce else None)}
    wares = b"".join(extract_all(x4_dir, "libraries/wares.xml")).decode("utf-8", "replace")
    for ware, macro in _MODULE_WARE.findall(wares):
        if macro in modules and ware.startswith("module_"):
            modules[macro]["ware"] = ware
    # Who sells the blueprint, under which licence, for how much. The blueprint
    # menu charges a module's maxprice (menu_trader_blueprintsorlicences.lua),
    # and the factions listed as owners are the ones whose representatives
    # offer it.
    for match in _WARE_BLOCK.finditer(wares):
        ware, body = match.group(1), match.group(2)
        ref = _COMPONENT_REF.search(body)
        if not ref or ref.group(1) not in modules:
            continue
        entry = modules[ref.group(1)]
        price = _PRICE.search(body)
        licence = _LICENCE.search(body)
        entry["owners"] = sorted(set(_OWNER.findall(body)))
        entry["licence"] = licence.group(1) if licence else None
        entry["maxprice"] = int(price.group(1)) if price else None
    return modules


def modules(rebuild: bool = False) -> dict[str, dict]:
    """The module table from cache, built on first use; empty without the game."""
    if MODULES.exists() and not rebuild:
        return json.loads(MODULES.read_text(encoding="utf-8"))
    try:
        table = build_modules()
    except OSError:
        return {}
    MODULES.parent.mkdir(parents=True, exist_ok=True)
    MODULES.write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
    return table


def capacity(module_macros: list[str]) -> dict[str, int]:
    """Storage per cargo type (container, solid, liquid) for a list of modules."""
    table = modules()
    total: dict[str, int] = {}
    for macro in module_macros:
        for tag, amount in (table.get(macro) or {}).get("cargo", {}).items():
            total[tag] = total.get(tag, 0) + amount
    return total


SHIPS = Path(__file__).parent / "data" / "ships.json"
_SHIP_FILE = re.compile(r"assets/units/size_[a-z]+/macros/(ship_[^/]+_macro)\.xml$")
_HULL = re.compile(rb'<hull max="(\d+)"')


def build_ships(x4_dir: Path = X4_DIR) -> dict[str, dict]:
    """Every ship macro's maximum hull. The save stores only the current value
    (<hull value="7658.075"/>), and only when the ship is damaged."""
    table: dict[str, dict] = {}
    for cat in archives(x4_dir):
        index = read_index(cat)
        with open(cat.with_suffix(".dat"), "rb") as blob:
            for name, (offset, size) in index.items():
                match = _SHIP_FILE.search(name)
                if not match:
                    continue
                blob.seek(offset)
                hull = _HULL.search(blob.read(size))
                table[match.group(1)] = {"hull": int(hull.group(1)) if hull else None}
    return table


def ships(rebuild: bool = False) -> dict[str, dict]:
    if SHIPS.exists() and not rebuild:
        return json.loads(SHIPS.read_text(encoding="utf-8"))
    try:
        table = build_ships()
    except OSError:
        return {}
    SHIPS.parent.mkdir(parents=True, exist_ok=True)
    SHIPS.write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
    return table


WARES = Path(__file__).parent / "data" / "wares.json"
_ANY_WARE = re.compile(r'<ware id="([^"]+)"([^>]*)>(.*?)</ware>', re.S)
_PRODUCTION = re.compile(r'<production ([^>]*)>(.*?)</production>', re.S)
_INPUT = re.compile(r'<ware ware="([^"]+)" amount="(\d+)"')


def build_wares(x4_dir: Path = X4_DIR) -> dict[str, dict]:
    """Every ware: transport type, volume, prices, and its recipes.

    One recipe per production method (default, teladi, paranid, ...), because a
    station's modules decide which one it runs, and a Teladi food line eats
    different inputs from an Argon one. Work units are wares too: what a
    station's workforce consumes is the recipe of workunit_busy and _idle.
    """
    table: dict[str, dict] = {}
    for part in extract_all(x4_dir, "libraries/wares.xml"):
        text = part.decode("utf-8", "replace")
        for ware, head, body in _ANY_WARE.findall(text):
            attrs = dict(_ATTR.findall(head))
            price = _PRICE_ALL.search(body)
            recipes = {}
            for prod_head, prod_body in _PRODUCTION.findall(body):
                p = dict(_ATTR.findall(prod_head))
                primary = prod_body.split("<primary>", 1)[1].split("</primary>", 1)[0] \
                    if "<primary>" in prod_body else ""
                recipes[p.get("method", "default")] = {
                    "time": float(p.get("time", 0)), "amount": int(p.get("amount", 0)),
                    "inputs": {w: int(n) for w, n in _INPUT.findall(primary)}}
            table.setdefault(ware, {
                "transport": attrs.get("transport"),
                "volume": int(attrs["volume"]) if attrs.get("volume", "").isdigit() else None,
                "minprice": int(price.group(1)) if price else None,
                "avgprice": int(price.group(2)) if price else None,
                "maxprice": int(price.group(3)) if price else None,
                "recipes": recipes,
            })
    return table


def wares(rebuild: bool = False) -> dict[str, dict]:
    if WARES.exists() and not rebuild:
        return json.loads(WARES.read_text(encoding="utf-8"))
    try:
        table = build_wares()
    except OSError:
        return {}
    WARES.parent.mkdir(parents=True, exist_ok=True)
    WARES.write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
    return table


def consumed_by(products: list[str], table: dict | None = None) -> set[str]:
    """Every ware a station making `products` may eat: the inputs of every
    method of every product, plus what a workforce eats. Deliberately the
    widest reading, because switching off a ware a station needs stalls it."""
    table = table if table is not None else wares()
    out: set[str] = set()
    for ware in list(products) + ["workunit_busy", "workunit_idle"]:
        for recipe in (table.get(ware) or {}).get("recipes", {}).values():
            out |= set(recipe.get("inputs", {}))
    return out


LICENCES = Path(__file__).parent / "data" / "licences.json"
_FACTION_BLOCK = re.compile(r'<faction id="([^"]+)"(.*?)</faction>', re.S)
_LICENCE_TAG = re.compile(r"<licence [^>]*>")
_ATTR = re.compile(r'(\w+)="([^"]*)"')


def build_licences(x4_dir: Path = X4_DIR) -> dict[str, dict]:
    """What each faction asks for each licence: reputation, precursor, price.

    From libraries/factions.xml. Reputation is on the save's own scale, -1 to 1
    (ceremonyfriend at 0.01, ceremonyally at 0.1). Most licences carry no price:
    they come with a promotion ceremony, which the player attends in person, so
    the agent cannot buy them. A faction block lists its definitions first;
    entries without any of the three attributes are something else and skipped.
    """
    table: dict[str, dict] = {}
    for part in extract_all(x4_dir, "libraries/factions.xml"):
        text = part.decode("utf-8", "replace")
        for faction, body in _FACTION_BLOCK.findall(text):
            for tag in _LICENCE_TAG.findall(body):
                attrs = dict(_ATTR.findall(tag))
                if not ({"minrelation", "precursor", "price"} & set(attrs)):
                    continue
                kinds = table.setdefault(faction, {})
                kinds.setdefault(attrs["type"], {
                    "minrelation": float(attrs["minrelation"]) if "minrelation" in attrs else None,
                    "precursor": attrs.get("precursor"),
                    "price": int(attrs["price"]) if "price" in attrs else None,
                })
    return table


def licences(rebuild: bool = False) -> dict[str, dict]:
    if LICENCES.exists() and not rebuild:
        return json.loads(LICENCES.read_text(encoding="utf-8"))
    try:
        table = build_licences()
    except OSError:
        return {}
    LICENCES.parent.mkdir(parents=True, exist_ok=True)
    LICENCES.write_text(json.dumps(table, indent=1, sort_keys=True), encoding="utf-8")
    return table


# Sectors belonging to a scenario rather than the living universe. The Timelines
# missions reuse real sector names, so 92 display names in this table belong to
# more than one macro and "Ianamus Zura IV" can mean either the sector the
# player flies through or a mission copy of it. Reading the wrong one produced a
# confident and entirely wrong answer about where to build a station.
SCENARIO_PREFIXES = ("timelines_", "scenario_", "test_", "basegame_map_tutorial")


def pretty(macro: str | None, names: dict[str, str] | None = None) -> str:
    """Readable name if known, otherwise the macro itself.

    Macro to name is unambiguous; the reverse is not, and nothing here should do
    the reverse. A scenario sector is marked, so a name that appears twice can
    still be told apart at a glance.
    """
    if not macro:
        return "?"
    names = names if names is not None else load()
    label = names.get(macro.lower(), macro)
    if macro.lower().startswith(SCENARIO_PREFIXES):
        return f"{label} (scenario)"
    return label


def main() -> int:
    # The Windows console runs on cp1252; game names are UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="(re)build the cache")
    parser.add_argument("--lookup", help="look up a single macro")
    parser.add_argument("--modules", action="store_true",
                        help="(re)build the station module table")
    args = parser.parse_args()

    if args.modules:
        ships(rebuild=True)
        wares(rebuild=True)
        licences(rebuild=True)
        table = modules(rebuild=True)
        print(f"{len(table)} module macros in {MODULES}, "
              f"{sum(1 for m in table.values() if m['ware'])} with a blueprint ware")
        return 0

    names = load(rebuild=args.build)
    if args.lookup:
        print(pretty(args.lookup, names))
    else:
        print(f"{len(names)} names in {CACHE}")
        for macro, label in list(names.items())[:15]:
            print(f"  {macro:<40} {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
