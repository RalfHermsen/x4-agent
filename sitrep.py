"""Condenses the parsed save state into a compact situation report.

Anything that can be computed is computed here: the model receives conclusions,
not raw data. Trade margins, idle ships and missing inputs are all derived
deterministically, so they do not belong in the LLM.

Usage:
    python sitrep.py --latest
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import executor
import gamedata
from save_parser import SHIP_CLASSES, latest_save, parse_save

# An order the game itself sets as a fallback means "doing nothing useful".
IDLE_ORDERS = {"Wait", None}

# Above this many ships we aggregate per role instead of naming every ship.
# Measured: 220 ships listed individually is a 40 kB sitrep, over 10k tokens.
DETAIL_LIMIT = 12

# Maximum number of trade lines per station in the report.
OFFER_LIMIT = 12

# A ship's role shows in its running order, not in its macro name. Measured on a
# save with 220 ships: Escort 115, Assist 92, MiningRoutine 6,
# TradeRoutine/Middleman 2, SectorExplorer 1, Wait 3.
ROLE_BY_ORDER = (
    ("miner", ("Mining",)),
    ("trader", ("Trade", "Middleman", "Supply", "Distribute")),
    ("explorer", ("Explor", "Scout", "Survey")),
    ("combat", ("Escort", "Assist", "Protect", "Attack", "Intercept", "Defend",
                "Patrol", "Bombard")),
)


def _first_order(ship: dict) -> str | None:
    return ship["orders"][0]["order"] if ship["orders"] else None


def role_of(ship: dict) -> str:
    order = _first_order(ship)
    if order in IDLE_ORDERS:
        return "IDLE"
    for role, prefixes in ROLE_BY_ORDER:
        if any(p.lower() in order.lower() for p in prefixes):
            return role
    return "other"


def by_role(ships: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for ship in ships:
        groups.setdefault(role_of(ship), []).append(ship)
    return groups


def _offers_by_ware(stations: list[dict]) -> dict[str, dict[str, list[tuple]]]:
    """Collect per ware who buys and who sells, with price and stock."""
    index: dict[str, dict[str, list[tuple]]] = {}
    for station in stations:
        for offer in station["offers"]:
            if offer["price"] is None:
                continue
            slot = index.setdefault(offer["ware"], {"buy": [], "sell": []})
            slot[offer["side"]].append(
                (offer["price"], offer["amount"] or 0, station["code"])
            )
    return index


def trade_margins(stations: list[dict], limit: int = 10) -> list[dict]:
    """Where can we buy cheap and sell dearer, within what we know?

    "sell" is the station selling, so our buying side; "buy" is the station
    buying, so our selling side.
    """
    out = []
    for ware, sides in _offers_by_ware(stations).items():
        sellers = [s for s in sides["sell"] if s[1] > 0]      # must have stock
        buyers = sides["buy"]
        if not sellers or not buyers:
            continue
        buy_at = min(sellers)                                  # lowest buy price
        sell_to = max(buyers)                                  # highest sell price
        margin = sell_to[0] - buy_at[0]
        if margin <= 0:
            continue
        out.append({
            "ware": ware,
            "buy_price": buy_at[0], "buy_from": buy_at[2], "available": buy_at[1],
            "sell_price": sell_to[0], "sell_to": sell_to[2],
            "margin": round(margin, 2),
        })
    out.sort(key=lambda row: row["margin"], reverse=True)
    return out[:limit]


# How long a ship must have been failing before it is worth reporting. Orders
# fail transiently all the time (a target taken by somebody else, a dock briefly
# full) and recover by themselves, so reporting every failure the moment it
# happens would drown the report in noise. The game timestamps each failure, so
# this is measured rather than sampled: no need to look only every few cycles.
FAILING_FOR = 5 * 60.0


def failing_ships(ships: list[dict], now: float) -> list[tuple]:
    """Ships the game itself says cannot carry out their order.

    X4 writes the reason next to the orders, in plain English. Two conditions
    count, and both were seen on the same pair of miners: the current order
    carries `failed="1"`, or the ship has given up and fallen back to its
    default order while a recent failure explains why.

    A stale failure on a ship that is working again is ignored, which is why
    this asks about the ship's current state rather than just the presence of a
    failure record.
    """
    out = []
    for ship in ships:
        failures = ship.get("failures")
        if not failures:
            continue
        current = (ship.get("orders") or [{}])[0]
        stuck = current.get("failed") or _first_order(ship) in IDLE_ORDERS
        if not stuck:
            continue
        last = failures[-1]
        age = now - last["time"]
        if age < FAILING_FOR:
            continue
        out.append((ship["code"], last["order"], last["message"], age,
                    ship.get("cargo") or {}))
    out.sort(key=lambda item: -item[3])
    return out


def build_lines(state: dict) -> list[str]:
    """What our build storages are doing, and what is holding them up.

    A build storage is a separate object with its own account, so a station can
    be rich while the build beside it is broke and waiting. Neither the station
    nor the build says anything about it: the build simply does not progress.
    Reporting the balance, the queue and what is still on order turns "nothing
    is happening" into something the model can act on.
    """
    lines = []
    for asset in state.get("assets", []):
        if asset.get("cls") != "buildstorage":
            continue
        build = asset.get("build") or {}
        if not (build.get("queued") or build.get("in_progress")):
            continue
        money = asset.get("account", {}).get("amount")
        money = f"{int(money):,} Cr".replace(",", ".") if money else "NO MONEY"
        lines.append(f"  {asset['code']}: {build.get('in_progress', 0)} build(s) running, "
                     f"{build.get('queued', 0)} queued, account {money}")
        wanted = [(o["ware"], o["amount"]) for o in asset.get("offers", [])
                  if o.get("side") == "buy" and o.get("amount")]
        if wanted:
            lines.append("    still buying: "
                         + ", ".join(f"{amount} {ware}" for ware, amount in sorted(wanted)))
        held = asset.get("cargo") or {}
        if held:
            lines.append("    delivered so far: "
                         + ", ".join(f"{a} {w}" for w, a in sorted(held.items())))
    return lines


def build(state: dict, goals: list[str] | None = None,
          failures: list[str] | None = None) -> str:
    meta, player = state["meta"], state["player"]
    assets = state["assets"]
    ships = [a for a in assets if a["cls"] in SHIP_CLASSES]
    stations = [a for a in assets if a["cls"] == "station"]
    known = state["known_stations"]
    # Sectors are called cluster_19_sector001_macro in the save. The model has
    # no use for macros, so translate them using the game data.
    names = gamedata.load()

    lines: list[str] = []
    add = lines.append

    add("# SITUATION")
    add(f"Playtime: {meta.get('playtime_s', 0):.0f}s. Capital: "
        f"{player.get('money', 0):,} Cr.")
    add(f"Owned: {len(stations)} station(s), {len(ships)} ship(s).")

    if stations:
        add("")
        add("# OWN STATIONS")
        for st in stations:
            add(f"{st['code']} ({st['macro']}) in "
                f"{gamedata.pretty(st['place'].get('sector'), names)}")
            # The account element carries min, max and amount only once they are
            # non-zero: X4 omits empty attributes. An account element with just
            # an id therefore means no operating budget at all, which is the
            # difference between a manager that can buy and one that cannot.
            acct = st.get("account") or {}
            if acct:
                amount = int(acct.get("amount", 0) or 0)
                expected = int(acct.get("min", 0) or 0)
                if expected:
                    share = amount / expected * 100
                    warn = ("  TOO LOW: a manager needs money to open purchase "
                            "orders" if share < 20 else "")
                    add(f"  operating budget {amount:,} Cr of "
                        f"{expected:,} recommended ({share:.0f}%).{warn}")
                else:
                    add("  operating budget: none set. "
                        "TOO LOW: a manager needs money to open purchase orders")

            mgr = st.get("manager")
            if mgr and mgr.get("management_raw") is not None:
                stars = mgr["management_stars"]
                warn = ("  TOO LOW: a station needs about 3 stars of management "
                        "for 3 jumps of trade range" if stars < 3 else "")
                add(f"  manager {mgr['code']}: management {stars} "
                    f"star{'' if stars == 1 else 's'} "
                    f"({mgr['management_raw']}/15).{warn}")
            for line in st.get("production", []):
                short = ", ".join(f"{amount} {ware}"
                                  for ware, amount in (line["short_of"] or {}).items())
                # A production line exists from the moment its module is
                # planned, so say "line", not "produces".
                add(f"  production line: {line['ware']}"
                    + (f", short {short}" if short else ""))
            for offer in st["offers"][:OFFER_LIMIT]:
                verb = "buys" if offer["side"] == "buy" else "sells"
                need = ""
                if offer["side"] == "buy" and offer["desired"]:
                    short = offer["desired"] - (offer["amount"] or 0)
                    if short > 0:
                        need = f", short {short}"
                add(f"  {verb} {offer['ware']} at {offer['price']:.0f} Cr "
                    f"(stock {offer['amount']}{need})")
            if len(st["offers"]) > OFFER_LIMIT:
                add(f"  ... and {len(st['offers']) - OFFER_LIMIT} other wares")

    add("")
    add(f"# FLEET ({len(ships)} ships)")
    if len(ships) <= DETAIL_LIMIT:
        for sh in ships:
            order = _first_order(sh)
            status = "IDLE" if order in IDLE_ORDERS else order
            where = (f"docked at {sh['docked_at']}" if sh["connection"] == "dock"
                     else f"in {gamedata.pretty(sh['place'].get('sector'), names)}")
            extra = f", {', '.join(sh['software'])}" if sh["software"] else ""
            add(f"{sh['code']} {sh['cls']} ({sh['macro']}): {status}, {where}{extra}")
    else:
        # Above the detail limit, aggregate per role. Listing a fleet of 220
        # ships individually cost 40 kB of sitrep; the model gains nothing from
        # it and it crowds out the rest of the report.
        for role, group in sorted(by_role(ships).items(),
                                  key=lambda kv: -len(kv[1])):
            orders = Counter(_first_order(sh) or "none" for sh in group)
            spread = ", ".join(f"{o} {n}" for o, n in orders.most_common(3))
            examples = ", ".join(sh["code"] for sh in group[:3] if sh["code"])
            add(f"{role:<9} {len(group):>4}   {spread}")
            add(f"{'':>14}examples: {examples}")

    add("")
    add("# KNOWN MARKET")
    add(f"Stations known to us that belong to other factions: {len(known)}.")
    margins = trade_margins(known + stations)
    if margins:
        add("Best margins within what we know (per unit):")
        for row in margins:
            add(f"  {row['ware']}: buy {row['buy_price']:.0f} at {row['buy_from']} "
                f"(stock {row['available']}) -> sell {row['sell_price']:.0f} "
                f"at {row['sell_to']}, margin {row['margin']:.0f} Cr")
    else:
        add("No profitable buy-sell pair known. Exploration needed.")

    # For every shortage, can anyone we know actually supply it? A shortage with
    # no known seller is a different problem from a shortage with one: the first
    # calls for exploration, the second for a delivery. Without this distinction
    # the model keeps ordering a trader to fetch something nobody sells, and the
    # game answers "no trades found in allowed sectors", which never reaches the
    # planner.
    sellers = {ware: [s for s in sides["sell"] if s[1] > 0]
               for ware, sides in _offers_by_ware(known).items()}

    idle = [s["code"] for s in ships if _first_order(s) in IDLE_ORDERS]
    failing = failing_ships(ships, state.get("meta", {}).get("playtime_s", 0.0))
    shortages = [(st["code"], o["ware"], o["desired"] - (o["amount"] or 0))
                 for st in stations for o in st["offers"]
                 if o["side"] == "buy" and o["desired"]
                 and o["desired"] > (o["amount"] or 0)]

    # An idle miner is a different problem from an idle freighter: it may be
    # idle because nothing we own wants what it can dig up. The game accepts the
    # assignment and then gives the ship no work, which from the outside looks
    # like the order never arrived.
    wanted = {o["ware"] for st in stations for o in st["offers"]
              if o.get("side") == "buy"}
    stuck_miners = []
    for ship in ships:
        if _first_order(ship) not in IDLE_ORDERS:
            continue
        kind = executor._miner_kind(ship.get("macro"))
        if kind and not (wanted & executor.MINABLE[kind]):
            stuck_miners.append((ship["code"], kind))

    if goals:
        add("")
        add("# STANDING GOALS (set by you in an earlier cycle)")
        for goal in goals:
            add(f"  {goal}")

    if failures:
        # An order that was sent but did not take effect. Saying so beats
        # silently planning as if it had worked, which is what happened before
        # this existed.
        add("")
        add("# LAST CYCLE DID NOT TAKE EFFECT")
        for failure in failures:
            add(f"  {failure}")

    # Where we could buy a ship. Nothing in the report said this before, so the
    # model could reason its way to "we need more miners" and no further.
    yards = [st for st in state.get("known_stations", []) if st.get("builds")]
    if yards:
        add("")
        add("# SHIPYARDS WE KNOW")
        for yard in yards:
            add(f"  {yard['code']} ({yard.get('owner')}) builds "
                f"{', '.join(c.upper() for c in yard['builds'])} class ships, in "
                f"{gamedata.pretty(yard['place'].get('sector'), names)}")

    construction = build_lines(state)
    if construction:
        add("")
        add("# CONSTRUCTION IN PROGRESS")
        for line in construction:
            add(line)

    add("")
    add("# ATTENTION")
    for code, order, message, age, cargo in failing:
        # What it is holding turns "something is wrong" into a specific
        # problem: a miner sitting on 900 ore nobody buys needs a buyer, not a
        # new order.
        holding = (" It is holding "
                   + ", ".join(f"{amount} {ware}"
                               for ware, amount in sorted(cargo.items()))
                   + ".") if cargo else ""
        add(f"{code} has been unable to carry out {order} for "
            f"{age / 60:.0f} minutes. The game says: \"{message}\"{holding}")
    if idle:
        add(f"Idle ships: {', '.join(idle)}.")
    for code, kind in stuck_miners:
        add(f"{code} is an idle {kind} miner, and no station of ours buys "
            f"anything it can mine ({', '.join(sorted(executor.MINABLE[kind]))}). "
            f"Assigning it to a station will leave it idle.")
    # Miners we own, by what they can extract. A shortage of a minable ware is a
    # fleet problem, not a market problem, and telling the two apart is the
    # difference between "explore for a seller" and "buy another miner".
    miners = {kind: [s["code"] for s in ships
                     if executor._miner_kind(s.get("macro")) == kind]
              for kind in executor.MINABLE}

    for code, ware, short in shortages:
        kind = next((k for k, wares in executor.MINABLE.items() if ware in wares), None)
        supply = sellers.get(ware) or []
        if kind:
            # This branch exists because the report used to send the model
            # exploring for a seller of ore. Ore is not sold, it is dug up.
            fleet = miners[kind]
            add(f"{code} needs {short} {ware}. {ware} is mined, not bought: "
                f"we have {len(fleet)} {kind} miner(s)"
                + (f" ({', '.join(fleet)})" if fleet else "")
                + ". A shortage this size is answered with more mining ships, "
                  "not with a trader or an explorer.")
        elif supply:
            best = min(supply)
            add(f"{code} needs {short} {ware}; {best[2]} sells it at "
                f"{best[0]:.0f} Cr (stock {best[1]}).")
        else:
            add(f"{code} needs {short} {ware}, and NO station we know sells it. "
                f"A trader cannot fix this; the map has to be explored first.")
    if not idle and not shortages and not failing:
        add("Nothing.")

    return "\n".join(lines)


def main() -> int:
    # The Windows console runs on cp1252; game names are UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", nargs="?")
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    target = latest_save() if args.latest else Path(args.save)
    print(build(parse_save(target)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
