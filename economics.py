"""What a production module costs and earns, for every ware the game makes.

The ground a strategist stands on when it sets goals for hours of play: which
chain to build next is a question of what one more module costs, what it earns
at the prices we know, how long it takes to pay back, and whether anyone buys
what it makes. The game's files give the first (the module's own build recipe,
its blueprint price, the production recipe per race); the save gives the rest,
and only what the player knows (`catalog`'s market helpers read the stations
the player has discovered).

Usage: py -3.14 economics.py <save> [--all]
"""
from __future__ import annotations

import re
import sys
from collections import Counter

import catalog
import gamedata


def product_of(macro: str) -> str | None:
    """'prod_gen_hullparts_macro' -> 'hullparts'; None for recyclers."""
    m = re.fullmatch(r"prod_([a-z]+)_(.+)_macro", macro)
    if not m or "recycler" in m.group(2):
        return None
    return m.group(2)


def build_cost(module_ware: str | None, table: dict) -> int:
    """The module's construction resources at their average price: what its
    build storage will have to buy (the module ware's own recipe)."""
    recipe = ((table.get(module_ware) or {}).get("recipes") or {}).get("default") or {}
    cost = sum(n * ((table.get(w) or {}).get("avgprice") or 0) for w, n in (recipe.get("inputs") or {}).items())
    return int(cost or (table.get(module_ware) or {}).get("avgprice") or 0)


def _best_ask(state: dict, ware: str) -> float | None:
    """The lowest price a station we know sells this ware at, if one does."""
    prices = [o["price"] for k in state.get("known_stations", []) for o in k.get("offers", [])
              if o.get("ware") == ware and o.get("side") == "sell" and o.get("price")
              and (o.get("amount") or 0) > 0]
    return min(prices) if prices else None


def game_plans(ware: str) -> dict[str, dict[str, int]]:
    """The game's own station plans that make this ware, as module counts per
    plan: the 9.0 single-ware prefabs NPC factions build from
    (`arg_hullparts_prefab_06` and so on, libraries/constructionplans.xml).
    How much storage, habitation and docking the designers put next to a
    number of production modules."""
    out = {}
    for raw in gamedata.extract_all(gamedata.X4_DIR, "libraries/constructionplans.xml"):
        for pid, body in re.findall(r'<plan id="([^"]+)"[^>]*>(.*?)</plan>', raw.decode("utf-8", "replace"), re.S):
            mods = Counter(re.findall(r'macro="([^"]+)"', body))
            if "prefab" in pid and any(product_of(m) == ware for m in mods):
                out[pid] = dict(mods)
    return out


def economics(state: dict) -> list[dict]:
    """One row per production module, by payback time, quickest first."""
    table, modules = gamedata.wares(), gamedata.modules()
    owned = set((state.get("player") or {}).get("blueprints") or [])
    stations = catalog._stations(state)
    made = {line.get("ware") for st in stations for line in st.get("production") or []}
    held: dict[str, int] = {}
    for st in stations:
        for w, n in (st.get("cargo") or {}).items():
            held[w] = held.get(w, 0) + n
    rows = []
    for macro, entry in sorted(modules.items()):
        ware = product_of(macro) if entry.get("class") == "production" else None
        recipes = ((table.get(ware) or {}).get("recipes") or {}) if ware else {}
        recipe = recipes.get(catalog.RECIPE_RACE.get(macro.split("_")[1], "")) or recipes.get("default")
        if not recipe or not recipe.get("time"):
            continue
        cycles = 3600 / recipe["time"]
        sell = catalog._best_buy(state, ware)
        price = sell or (table.get(ware) or {}).get("avgprice") or 0
        inputs = []
        for w, n in (recipe.get("inputs") or {}).items():
            # Made by us: what we give up by eating it. Bought: what a seller
            # we know asks, or the game's average price when we know none.
            cost = (catalog._input_cost(state, w, held, table) if w in made
                    else _best_ask(state, w) or (table.get(w) or {}).get("avgprice") or 0)
            inputs.append({"ware": w, "per_hour": n * cycles, "we_make": w in made, "cost": cost})
        margin = recipe["amount"] * cycles * price - sum(i["per_hour"] * i["cost"] for i in inputs)
        build = build_cost(entry.get("ware"), table)
        blueprint = 0 if entry.get("ware") in owned else (entry.get("maxprice") or 0)
        demand = catalog._demand(state, ware)
        rows.append({
            "ware": ware, "macro": macro, "per_hour": recipe["amount"] * cycles,
            "price": price, "priced_by": "buyer" if sell else "average",
            "margin_per_hour": margin, "build_cost": build, "blueprint": blueprint,
            "licence": entry.get("licence"),
            "payback_hours": (build + blueprint) / margin if margin > 0 else None,
            # A blueprint is bought once for every module of its kind after it.
            "payback_hours_built": build / margin if margin > 0 else None,
            "demand": demand, "demand_hours": demand / (recipe["amount"] * cycles),
            # What we hold already, in hours of one module's output: KYV-745
            # sat on 22,000 wafers while wafers topped this list.
            "held_hours": held.get(ware, 0) / (recipe["amount"] * cycles),
            "inputs": inputs})
    return sorted(rows, key=lambda r: (r["payback_hours"] is None, r["payback_hours"] or 0))


def main() -> int:
    from save_parser import parse_save
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = economics(parse_save(sys.argv[1]))
    shown = rows if "--all" in sys.argv else rows[:25]
    print(f"{'ware':<24}{'margin/h':>11}{'build':>12}{'blueprint':>12}{'payback h':>11}{'w/o bp':>8}"
          f"{'demand h':>10}{'held h':>8}  priced by  inputs we buy")
    for r in shown:
        bought = ", ".join(i["ware"] for i in r["inputs"] if not i["we_make"]) or "-"
        payback = f"{r['payback_hours']:.1f}" if r["payback_hours"] is not None else "never"
        built = f"{r['payback_hours_built']:.1f}" if r["payback_hours_built"] is not None else "-"
        print(f"{r['ware'] + ' (' + r['macro'].split('_')[1] + ')':<24}{r['margin_per_hour']:>11,.0f}"
              f"{r['build_cost']:>12,}{r['blueprint']:>12,}{payback:>11}{built:>8}{r['demand_hours']:>10.1f}"
              f"{r['held_hours']:>8.1f}  {r['priced_by']:<9}  {bought}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
