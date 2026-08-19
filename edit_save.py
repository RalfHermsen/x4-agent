"""Edits a value in an X4 savegame, writing the result to a new save file.

Deliberately narrow and deliberately non-destructive: it never overwrites the
source, it writes a new save next to it, so the original stays loadable. Use it
to set up a situation you want to test rather than playing towards it.

Right now it does one thing: set a station manager's management skill. Skills in
the save run 1 to 15 and the game shows them as 0 to 5 stars, so three points
make one star (measured across 101,543 skill entries in a late-game save).

Usage:
    python edit_save.py --manager-skill 9 --station KYV-745
    python edit_save.py --manager-skill 9 --station KYV-745 --out save_008
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
from pathlib import Path

from save_parser import latest_save

SKILL_POINTS_PER_STAR = 3


def next_save_name(folder: Path) -> str:
    """A save_NNN name that is not taken yet."""
    used = {p.name for p in folder.glob("save_*.xml.gz")}
    for n in range(1, 1000):
        name = f"save_{n:03d}"
        if f"{name}.xml.gz" not in used:
            return name
    raise RuntimeError("no free save slot found")


def set_save_name(xml: str, label: str) -> str:
    """Rename the save so it is recognisable in the load menu.

    Without this the copy keeps the original's display name and you end up
    guessing which of two identical-looking entries is the edited one.
    """
    return re.sub(r'(<save name=")[^"]*(")', lambda m: m.group(1) + label + m.group(2),
                  xml, count=1)


def set_manager_skill(xml: str, station_code: str, value: int) -> tuple[str, str]:
    """Set the management skill of the manager of one station.

    Anchors on the station's code, then on its manager post, then on that NPC's
    skills element. Anchoring matters: `management="3"` occurs thousands of
    times in a save and replacing the wrong one is silent and untraceable.
    """
    station = re.search(rf'<component[^>]*code="{re.escape(station_code)}"[^>]*>', xml)
    if not station:
        raise LookupError(f"station {station_code} not found in this save")

    post = re.search(r'<post id="manager" component="(\[[^\]]+\])"/>',
                     xml[station.end():station.end() + 200_000])
    if not post:
        raise LookupError(f"{station_code} has no manager post")
    manager_id = post.group(1)

    npc = re.search(rf'<component[^>]*id="{re.escape(manager_id)}"[^>]*>', xml)
    if not npc:
        raise LookupError(f"manager component {manager_id} not found")

    window = xml[npc.end():npc.end() + 4000]
    skills = re.search(r'(<skills[^>]*?management=")(\d+)(")', window)
    if not skills:
        raise LookupError("that manager has no management skill entry")

    before = skills.group(2)
    patched = window[:skills.start()] + skills.group(1) + str(value) + skills.group(3) \
        + window[skills.end():]
    return xml[:npc.end()] + patched + xml[npc.end() + 4000:], before


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", nargs="?", help="source save; default is the newest")
    parser.add_argument("--station", required=True, help="station ID code, e.g. KYV-745")
    parser.add_argument("--manager-skill", type=int, required=True,
                        help="new management value, 1 to 15 (3 points per star)")
    parser.add_argument("--out", help="name of the new save, without extension")
    parser.add_argument("--label", help="display name shown in the load menu")
    args = parser.parse_args()

    if not 1 <= args.manager_skill <= 15:
        parser.error("management skill runs from 1 to 15")

    source = Path(args.save) if args.save else latest_save()
    print(f"source: {source}")

    xml = gzip.open(source, "rt", encoding="utf-8", errors="replace").read()
    patched, before = set_manager_skill(xml, args.station, args.manager_skill)
    label = args.label or f"{args.station} manager skill {args.manager_skill}"
    patched = set_save_name(patched, label)

    name = args.out or next_save_name(source.parent)
    target = source.parent / f"{name}.xml.gz"
    if target.exists():
        parser.error(f"{target} already exists; pick another --out")

    with gzip.open(target, "wt", encoding="utf-8") as handle:
        handle.write(patched)

    stars_before = int(before) // SKILL_POINTS_PER_STAR
    stars_after = args.manager_skill // SKILL_POINTS_PER_STAR
    print(f"manager of {args.station}: management {before} -> {args.manager_skill} "
          f"({stars_before} -> {stars_after} stars)")
    print(f"written: {target}  (shows as \"{label}\" in the load menu)")
    print("The original is untouched. Load the new save in game to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
