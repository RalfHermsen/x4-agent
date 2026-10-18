"""The scorecard: what an empire is worth at one moment, from its savegame.

Every change to the agent is judged by this, not by how its log reads: same
baseline save, same game hours, compare. Without it "better" is an opinion.

It counts what the sitrep counts, through the same functions, so a ship that
the report calls idle is idle here too.

Usage:
    python score.py <save>
    python score.py --compare <before> <after>
    python score.py --all            # every save in the profile, one line each
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import sitrep
from save_parser import SHIP_CLASSES, documents_dir, parse_save


def score(state: dict) -> dict:
    meta, player = state["meta"], state["player"]
    assets = state["assets"]
    ships = [a for a in assets if a["cls"] in SHIP_CLASSES]
    # An escape pod is what is left of a lost ship, not a ship that can work.
    working = [s for s in ships if sitrep.ship_type(s.get("macro")) != "escape pod"]
    stations = [a for a in assets if a["cls"] == "station"]
    storages = [a for a in assets if a["cls"] == "buildstorage"]
    now = meta.get("playtime_s") or 0
    return {
        "save": meta.get("save_name"),
        "game_hours": round(now / 3600, 2),
        "credits": player.get("money") or 0,
        "stations": len(stations),
        "modules": sum(len(s.get("modules") or []) for s in stations),
        "ships": len(working),
        "roles": dict(sorted(Counter(sitrep.role_of(s) for s in working).items())),
        "idle": sum(1 for s in working if sitrep.role_of(s) == "IDLE"),
        "failing": len(sitrep.failing_ships(working, now)),
        "builds": sum((b.get("build") or {}).get("in_progress", 0)
                      + (b.get("build") or {}).get("queued", 0) for b in storages),
        "fleet": sorted(s["code"] for s in working if s.get("code")),
    }


ROWS = ("game_hours", "credits", "stations", "modules", "ships", "idle",
        "failing", "builds")


def render(card: dict) -> str:
    lines = [f"# {card['save']}"]
    lines += [f"  {row:<11} {card[row]:>14,}" for row in ROWS]
    lines.append("  roles       " + ", ".join(f"{r} {n}" for r, n in card["roles"].items()))
    return "\n".join(lines)


def compare(before: dict, after: dict) -> str:
    width = max(len(str(before["save"])), len(str(after["save"])), 12)
    lines = [f"{'':<12} {before['save']:>{width}} {after['save']:>{width}} {'change':>14}"]
    for row in ROWS:
        a, b = before[row], after[row]
        lines.append(f"{row:<12} {a:>{width},} {b:>{width},} {b - a:>+14,}")
    roles = sorted(set(before["roles"]) | set(after["roles"]))
    for role in roles:
        a, b = before["roles"].get(role, 0), after["roles"].get(role, 0)
        lines.append(f"  {role:<10} {a:>{width},} {b:>{width},} {b - a:>+14,}")
    # Gone is not the same as destroyed: sold and returned look the same in a
    # save. The list says what is no longer there and nothing more.
    gone = sorted(set(before["fleet"]) - set(after["fleet"]))
    new = sorted(set(after["fleet"]) - set(before["fleet"]))
    lines.append(f"ships gone ({len(gone)}): {', '.join(gone) or 'none'}")
    lines.append(f"ships new ({len(new)}): {', '.join(new) or 'none'}")
    return "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("save", nargs="?")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.compare:
        before, after = (score(parse_save(Path(p))) for p in args.compare)
        print(compare(before, after))
    elif args.all:
        root = documents_dir() / "Egosoft" / "X4"
        saves = sorted(root.glob("*/save/*.xml.gz"), key=lambda p: p.stat().st_mtime)
        failed = 0
        for path in saves:
            try:
                card = score(parse_save(path))
            except Exception as exc:  # noqa: BLE001 - one bad save must not stop the run
                failed += 1
                print(f"{path.name:<45} FAILED: {type(exc).__name__}: {exc}")
                continue
            print(f"{path.name:<45} " + "  ".join(f"{r} {card[r]:,}" for r in ROWS))
        return 1 if failed else 0
    elif args.save:
        print(render(score(parse_save(Path(args.save)))))
    else:
        parser.error("give a save, --compare BEFORE AFTER, or --all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
