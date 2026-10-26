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


def _holdings(assets: list[dict]) -> tuple[int, int, int]:
    """Money on our stations' and build storages' accounts, and their stock at
    the game's minimum and average ware prices (libraries/wares.xml).

    Player money alone misjudged every run in which a station grew: the
    finished expansion gave KYV-745 room, the store filled by a third, and
    the game drew the station's budget from the player. A rules-only run
    showed 1.37 million per game hour in credits and 2.07 with its stock at
    minimum prices, against 1.82 for the game alone (2026-10-21).
    """
    import gamedata
    wares = gamedata.wares()
    accounts = low = mid = 0
    for a in assets:
        if a.get("cls") not in ("station", "buildstorage"):
            continue
        accounts += int(float((a.get("account") or {}).get("amount") or 0))
        for ware, n in (a.get("cargo") or {}).items():
            low += n * (wares.get(ware) or {}).get("minprice", 0)
            mid += n * (wares.get(ware) or {}).get("avgprice", 0)
    return accounts, int(low), int(mid)


def _sellable_stock(assets: list[dict], known: list[dict]) -> int:
    """Our stock at minimum prices, each ware counted only up to what the
    stations we know ask to buy (plan 6.1: stock nobody buys is not worth).

    The warm rules-only run turned 37,000 silicon into wafers and sold them:
    credits rose by 18 % while net worth at minimum prices fell, because
    silicon counted at 111 Cr a unit with only 11,600 asked for.
    """
    import gamedata
    wares = gamedata.wares()
    demand: dict[str, int] = {}
    for k in known:
        for o in k.get("offers", []):
            if o.get("side") == "buy":
                demand[o.get("ware")] = demand.get(o.get("ware"), 0) + int(o.get("amount") or 0)
    held: dict[str, int] = {}
    for a in assets:
        if a.get("cls") in ("station", "buildstorage"):
            for w, n in (a.get("cargo") or {}).items():
                held[w] = held.get(w, 0) + n
    return int(sum(min(n, demand.get(w, 0)) * (wares.get(w) or {}).get("minprice", 0)
                   for w, n in held.items()))


def _modules_value(stations: list[dict]) -> int:
    """Our stations' modules at the minimum price of their module wares: what
    an expansion added, which the cards before 2026-10-21 counted only as a
    number of modules."""
    import gamedata
    wares, modules = gamedata.wares(), gamedata.modules()
    return int(sum((wares.get((modules.get(m) or {}).get("ware") or "") or {}).get("minprice", 0)
                   for s in stations for m in (s.get("modules") or [])))


def _modules_cost(stations: list[dict]) -> int:
    """Our stations' modules at what building them takes: the module ware's
    construction resources at their minimum price, as stock is counted.

    The module ware's own minimum price runs two to three times above that
    (a microchip module 4.12 million, its resources about 2), so a run that
    built expensive modules scored high whether they earned or not: lean2
    built fifteen microchip modules, losing money at the prices it knew, and
    led the rules runs after it by 25 % in net worth while trailing them in
    credits and accounts."""
    import gamedata
    wares, modules = gamedata.wares(), gamedata.modules()

    def cost(macro: str) -> float:
        ware = (modules.get(macro) or {}).get("ware") or ""
        recipe = ((wares.get(ware) or {}).get("recipes") or {}).get("default") or {}
        return sum(n * ((wares.get(w) or {}).get("minprice") or 0) for w, n in (recipe.get("inputs") or {}).items())
    return int(sum(cost(m) for s in stations for m in (s.get("modules") or [])))


def score(state: dict) -> dict:
    meta, player = state["meta"], state["player"]
    assets = state["assets"]
    ships = [a for a in assets if a["cls"] in SHIP_CLASSES]
    # An escape pod is what is left of a lost ship, not a ship that can work.
    working = [s for s in ships if sitrep.ship_type(s.get("macro")) != "escape pod"]
    stations = [a for a in assets if a["cls"] == "station"]
    storages = [a for a in assets if a["cls"] == "buildstorage"]
    now = meta.get("playtime_s") or 0
    accounts, stock_min, stock_avg = _holdings(assets)
    modules_value = _modules_value(stations)
    modules_cost = _modules_cost(stations)
    stock_sellable = _sellable_stock(assets, state.get("known_stations", []))
    return {
        "save": meta.get("save_name"),
        "game_hours": round(now / 3600, 2),
        "credits": player.get("money") or 0,
        "accounts": accounts,
        "stock_min": stock_min,
        "stock_avg": stock_avg,
        "modules_value": modules_value,
        "stock_sellable": stock_sellable,
        # Net worth with stock counted only up to what known buyers ask for.
        "net_sellable": (player.get("money") or 0) + accounts + stock_sellable + modules_value,
        # What the empire holds in money, wares and modules, at the prices the
        # game never goes below. Ships are not in it.
        "net_worth": (player.get("money") or 0) + accounts + stock_min + modules_value,
        # The same with modules at what they cost to build (`_modules_cost`):
        # the measure from 2026-10-25 on; net_worth stays for older cards.
        "modules_cost": modules_cost,
        "net_worth_cost": (player.get("money") or 0) + accounts + stock_min + modules_cost,
        "stations": len(stations),
        "modules": sum(len(s.get("modules") or []) for s in stations),
        "ships": len(working),
        "roles": dict(sorted(Counter(sitrep.role_of(s) for s in working).items())),
        "idle": sum(1 for s in working if sitrep.role_of(s) == "IDLE"),
        "failing": len(sitrep.failing_ships(working, now)),
        "builds": sum((b.get("build") or {}).get("in_progress", 0)
                      + (b.get("build") or {}).get("queued", 0) for b in storages),
        # Paid for at a wharf and not delivered. Not in the net worth, as ships
        # are not: shown because 22.7 M Cr sat there unseen in one run.
        "on_order": sum(o.get("paid") or 0 for o in state.get("ships_on_order") or []),
        "fleet": sorted(s["code"] for s in working if s.get("code")),
    }


ROWS = ("game_hours", "credits", "accounts", "stock_min", "stock_avg", "stock_sellable", "modules_value",
        "modules_cost", "net_worth", "net_worth_cost", "net_sellable",
        "stations", "modules", "ships", "idle", "failing", "builds", "on_order")


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
