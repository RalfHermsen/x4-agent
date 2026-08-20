"""Edits values in an X4 savegame, writing the result to a new save file.

Deliberately narrow and deliberately non-destructive: it never overwrites the
source, it writes a new save next to it, so the original stays loadable. Use it
to set up a situation you want to test rather than playing towards it.

Three edits are supported:

* a station manager's management skill
* the player's credits
* adding blueprints the player owns

Skills in the save run 1 to 15 and the game shows them as 0 to 5 stars, so three
points make one star (measured across 101,543 skill entries in a late-game save).

Usage:
    python edit_save.py --station KYV-745 --manager-skill 9
    python edit_save.py --credits 10000000
    python edit_save.py --add-credits 10000000 --label "10M test"
    python edit_save.py --blueprint module_gen_prod_energycells_01
"""

from __future__ import annotations

import argparse
import gzip
import re
import time
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


def stamp_date(xml: str) -> str:
    """Set the save's timestamp to now.

    The load menu sorts on the date inside the file, not on the file's own
    modification time. Carrying the source's date over meant a freshly written
    save appeared halfway down the list, wedged between the autosaves it was
    copied from, which is genuinely hard to find. This file was written now, so
    saying so is also the honest answer.
    """
    return re.sub(r'(<save name="[^"]*" date=")[0-9]+(")',
                  lambda m: m.group(1) + str(int(time.time())) + m.group(2),
                  xml, count=1)


def read_credits(xml: str) -> int:
    m = re.search(r'<player[^>]*money="(\d+)"', xml)
    if not m:
        raise LookupError("no player money entry found in this save")
    return int(m.group(1))


def set_credits(xml: str, value: int) -> tuple[str, int]:
    """Set the player's credits everywhere they are stored.

    Credits live in two kinds of place: the `money` attribute of the player
    entry in the save header, and the amount on the player faction's account,
    which is referenced from several spots. Changing only the header makes the
    number in the menu disagree with what you can actually spend.

    The faction account is found by id rather than by value, because other
    accounts can hold the same amount by coincidence.
    """
    before = read_credits(xml)

    xml = re.sub(r'(<player[^>]*money=")\d+(")',
                 lambda m: m.group(1) + str(value) + m.group(2), xml, count=1)

    faction = re.search(r'<faction[^>]*id="player"[^>]*>', xml)
    if not faction:
        raise LookupError("no player faction found in this save")
    account = re.search(r'<account id="(\[[^\]]+\])"',
                        xml[faction.end():faction.end() + 4000])
    if not account:
        raise LookupError("the player faction has no account element")

    account_id = re.escape(account.group(1))
    xml, hits = re.subn(rf'(<account id="{account_id}" amount=")\d+(")',
                        lambda m: m.group(1) + str(value) + m.group(2), xml)
    if not hits:
        raise LookupError("the player account carries no amount to change")
    return xml, before


def add_blueprints(xml: str, wares: list[str]) -> tuple[str, list[str]]:
    """Add blueprint entries to the player's owned blueprints.

    They live in a single `<blueprints>` element holding `<blueprint ware=...>`
    children. Blueprints the player already owns are skipped rather than
    duplicated, because the game reads the list as a set and a duplicate would
    just be noise in a file that is hard enough to diff already.
    """
    start = xml.find("<blueprints>")
    if start < 0:
        raise LookupError("no blueprints element found in this save")
    end = xml.find("</blueprints>", start)
    if end < 0:
        raise LookupError("the blueprints element is not closed")

    block = xml[start:end]
    owned = set(re.findall(r'<blueprint ware="([^"]+)"/>', block))
    added = [w for w in wares if w not in owned]
    if not added:
        return xml, []

    entries = "".join(f'<blueprint ware="{w}"/>' for w in added)
    return xml[:end] + entries + xml[end:], added


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
    parser.add_argument("--station", help="station ID code, e.g. KYV-745")
    parser.add_argument("--manager-skill", type=int,
                        help="new management value, 1 to 15 (3 points per star)")
    parser.add_argument("--credits", type=int, help="set the player's credits to this")
    parser.add_argument("--add-credits", type=int, help="add this many credits")
    parser.add_argument("--blueprint", action="append", metavar="WARE",
                        help="add a blueprint, e.g. module_gen_prod_energycells_01; "
                             "repeat for more")
    parser.add_argument("--out", help="name of the new save, without extension")
    parser.add_argument("--label", help="display name shown in the load menu")
    args = parser.parse_args()

    if (args.manager_skill is None and args.credits is None
            and args.add_credits is None and not args.blueprint):
        parser.error("nothing to change; give --manager-skill, --credits, "
                     "--add-credits or --blueprint")
    if args.manager_skill is not None:
        if not args.station:
            parser.error("--manager-skill needs --station")
        if not 1 <= args.manager_skill <= 15:
            parser.error("management skill runs from 1 to 15")

    source = Path(args.save) if args.save else latest_save()
    print(f"source: {source}")

    xml = gzip.open(source, "rt", encoding="utf-8", errors="replace").read()
    changes: list[str] = []

    if args.manager_skill is not None:
        xml, before = set_manager_skill(xml, args.station, args.manager_skill)
        changes.append(f"manager of {args.station}: management {before} -> "
                       f"{args.manager_skill} "
                       f"({int(before) // SKILL_POINTS_PER_STAR} -> "
                       f"{args.manager_skill // SKILL_POINTS_PER_STAR} stars)")

    if args.credits is not None or args.add_credits is not None:
        target = (args.credits if args.credits is not None
                  else read_credits(xml) + args.add_credits)
        xml, before_credits = set_credits(xml, target)
        changes.append(f"credits: {before_credits:,} -> {target:,}")

    if args.blueprint:
        xml, added = add_blueprints(xml, args.blueprint)
        changes.append(f"blueprints added: {', '.join(added)}" if added
                       else "blueprints: all already owned")

    label = args.label or "; ".join(changes)[:60]
    xml = set_save_name(xml, label)
    xml = stamp_date(xml)

    name = args.out or next_save_name(source.parent)
    target_file = source.parent / f"{name}.xml.gz"
    if target_file.exists():
        parser.error(f"{target_file} already exists; pick another --out")

    with gzip.open(target_file, "wt", encoding="utf-8") as handle:
        handle.write(xml)

    for line in changes:
        print(line)
    print(f'written: {target_file}  (shows as "{label}" in the load menu)')
    print("The original is untouched. Load the new save in game to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
