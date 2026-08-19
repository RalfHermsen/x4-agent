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


def pretty(macro: str | None, names: dict[str, str] | None = None) -> str:
    """Readable name if known, otherwise the macro itself."""
    if not macro:
        return "?"
    names = names if names is not None else load()
    return names.get(macro.lower(), macro)


def main() -> int:
    # The Windows console runs on cp1252; game names are UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="(re)build the cache")
    parser.add_argument("--lookup", help="look up a single macro")
    args = parser.parse_args()

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
