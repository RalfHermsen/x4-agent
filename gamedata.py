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
# A module ware names its macro in a <component ref=...> child. The negative
# lookahead stops at the next ware *definition*; production recipes inside a
# ware are also <ware ...> elements, so "<ware " alone would stop too early.
_MODULE_WARE = re.compile(r'<ware id="([^"]+)"(?:(?!<ware id=).)*?<component ref="([^"]+_macro)"',
                          re.S)


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
                modules[match.group(1)] = {"class": cls.group(1).decode() if cls else None,
                                           "ware": None, "cargo": cargo}
    wares = b"".join(extract_all(x4_dir, "libraries/wares.xml")).decode("utf-8", "replace")
    for ware, macro in _MODULE_WARE.findall(wares):
        if macro in modules and ware.startswith("module_"):
            modules[macro]["ware"] = ware
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
