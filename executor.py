"""Translates validated planner actions into commands the in-game bridge accepts.

This is the last layer before anything reaches the game, and it is deliberately
narrow. Three separate gates stand between a model's idea and your empire:

1. `planner.check_actions()` already dropped actions referring to things that do
   not exist or are not ours.
2. This module only translates action types that the Mission Director side can
   actually execute. Everything else stays advice, no matter how confident the
   model was.
3. The caller decides whether to send at all (advise vs execute mode).

The executable vocabulary grows only when the matching MD command has been
written and verified against the game's own schemas. `describe()` reports what
that currently is, and the planner prompt is built from it, so the model is told
what its body can actually do.

Usage:
    from executor import to_commands
    commands, skipped = to_commands(validated_actions)
"""

from __future__ import annotations

from typing import Callable

from schemas import TradeRule


def _explore(action) -> str:
    """set_behaviour(explore) -> the MD command that issues the vanilla Explore order."""
    return f"explore {action.ship_ref}"


def _autotrade(action) -> str:
    """set_behaviour(autotrade) -> the vanilla TradeRoutine order, on its defaults.

    A ware whitelist cannot travel through the pipe, because the Mission
    Director cannot parse strings. Rather than silently dropping the model's
    whitelist, `_blocked_reason` refuses the action when one was given.
    """
    return f"autotrade {action.ship_ref}"


def _automine(action) -> str:
    """set_behaviour(automine) -> the vanilla MiningRoutine order."""
    return f"automine {action.ship_ref}"


# Wares the in-game bridge can build production for. The Mission Director has
# no ware-by-name lookup, so every ware needs an explicit comparison there, and
# now also the macro of the module that produces it; this list must stay in step
# with the one in bridge/.../x4_agent_bridge.xml.
#
# Shorter than it was: graphene and hullparts were listed while the bridge only
# had a ware for them and no module, which was harmless only because the whole
# expansion path was silently doing nothing.
EXPANDABLE_WARES = ("energycells", "water", "refinedmetals", "siliconwafers")


def _expand(action) -> str:
    """expand_station -> add production for a ware to an existing station."""
    return f"expand {action.station_id} {action.ware}"


def _budget(action) -> str:
    """set_budget -> raise a station's operating budget to a level."""
    return f"budget {action.station_id} {action.level}"


# How far a manual price may sit from what the station asks today. A model that
# misreads the report can otherwise put an end product at 3 credits, and a
# station cheerfully sells its stock at that price.
PRICE_BAND = (0.5, 2.0)


def _price(action) -> str:
    """set_price -> a manual price override, handled on the Lua side."""
    return (f"price {action.station_id} {action.ware} {action.side} "
            f"{int(round(action.price))}")


def _price_out_of_band(action, state: dict) -> str | None:
    station = next((a for a in state.get("assets", [])
                    if a.get("code") == action.station_id), None)
    if not station:
        return None
    current = next((o.get("price") for o in station.get("offers", [])
                    if o.get("ware") == action.ware
                    and o.get("side") == action.side), None)
    if not current:
        return (f"{action.station_id} has no {action.side} offer for "
                f"{action.ware} to price against")
    low, high = current * PRICE_BAND[0], current * PRICE_BAND[1]
    if not low <= action.price <= high:
        return (f"{action.price:.0f} Cr is outside the sane band "
                f"{low:.0f}-{high:.0f} Cr around the current {current:.0f} Cr")
    return None


# The whole-container form: a rule that applies to everything the station
# trades rather than to one ware. The model reaches for these words when it
# means "all wares", and the game addresses that case with an empty ware id.
ALL_WARES = {"all", "any", "-", "*", ""}


def _trade_rule(action) -> str:
    """set_trade_rule -> who a station is allowed to trade with, on the Lua side.

    `open_market` restores the empire default rather than opening the station up
    unconditionally. On a game where no default has been set those are the same
    thing, and where one has been set, following it is the honest reversal.
    """
    ware = "-" if action.ware.lower() in ALL_WARES else action.ware
    mode = "own" if action.rule == TradeRule.own_faction_only else "default"
    return f"traderule {action.station_id} {ware} {action.side} {mode}"


def _trade_rule_pointless(action, state: dict) -> str | None:
    """A rule on a ware the station does not trade changes nothing."""
    if action.ware.lower() in ALL_WARES:
        return None
    station = next((a for a in state.get("assets", [])
                    if a.get("code") == action.station_id), None)
    if not station:
        return None
    sides = ("buy", "sell") if action.side == "both" else (action.side,)
    for offer in station.get("offers", []):
        if offer.get("ware") == action.ware and offer.get("side") in sides:
            return None
    return (f"{action.station_id} does not {action.side} {action.ware}, "
            f"so a trade rule on it changes nothing")


# Just under the best bid: enough to be the obvious seller without giving margin
# away. And a floor on how many buyers must be known before a price is allowed
# to come down.
UNDERCUT = 0.98
MIN_BUYERS_TO_CUT = 2
# How far a price must be off before it is worth a command. Bids drift by a
# credit or two between cycles, and without a deadband refined metals was
# repriced five times in an hour, 204 to 203 to 202, on a pipe that takes one
# command every two seconds. Chasing the last credit costs more than it earns.
PRICE_DEADBAND = 0.02
# A ware is only worth aiming the fleet at if there is at least this much of it
# in cubic metres, roughly one full load for a medium freighter. Below that the
# fleet arrives, empties it in one trip and the other eighteen ships have come
# for nothing.
WORTH_A_TRIP = 8000
# Stock measured against the demand we can actually see, because that is the
# question: is there more of this than the market in front of us wants? Storage
# share was the wrong yardstick. It put 361,345 energy cells at 8% of the
# warehouse, alongside the ore and ice they are stored with, and concluded that
# the largest pile on the station was not worth discounting.
#
# Past the first figure we undercut everyone to pull outside traders in; past
# the second we merely stop being the most expensive supplier in the region.
DUMP_SHARE = 2.0
MATCH_SHARE = 0.5


def _oversupply(known: list[dict], ware: str, stock: int) -> float:
    """How many times over we could fill every order we can see."""
    demand = sum(o.get("desired") or 0 for station in known
                 for o in station.get("offers", [])
                 if o.get("ware") == ware and o.get("side") == "buy")
    if not demand:
        return float("inf") if stock else 0.0
    return stock / demand


def repricing(state: dict) -> list[str]:
    """Price commands that follow mechanically from the market, without the model.

    Pricing to just under the best known bid is arithmetic, not strategy, and
    the model kept forgetting to do it: prices drift every few minutes as buyers
    appear and are filled, and a cycle spent elsewhere is a cycle selling at the
    wrong price. The policy stays in guidelines.md; only the sum happens here.

    Raising is always safe. Cutting is not: a lone lowball bid says more about
    how little of the map we have seen than about the ware, and cutting to meet
    it can hand over a third of the value. So a cut needs at least two known
    buyers, and everything else is left to the model to argue about.
    """
    import sitrep

    known = state.get("known_stations", [])
    bids = sitrep.best_bids(known)
    volumes = _volumes()
    out = []
    for station in state.get("assets", []):
        if station.get("cls") != "station":
            continue
        stock = station.get("cargo") or {}

        for offer in station.get("offers", []):
            if offer.get("side") != "sell" or not offer.get("price"):
                continue
            bid = bids.get(offer["ware"])
            if not bid:
                continue
            top, _, _, buyers = bid

            # Two prices matter, and for a long time only one of them was used.
            #
            # Just under the best bid is right when we deliver: our own ships
            # take the goods to the buyer and collect the top price. But it also
            # made this station the most expensive supplier in the region on
            # five wares out of six, and no trader in the game buys from the
            # dearest seller. Measured: microchips asked at 1,154 while eight
            # other suppliers asked between 805 and 1,044, and every single
            # reservation on the station was one of our own freighters loading.
            # Nobody came.
            #
            # So where somebody else sells the same ware, match them. The middle
            # of the field, not the bottom: undercutting the cheapest starts a
            # race that ends at the floor, and we still want the margin when our
            # own ships do the delivering.
            # How aggressive to be depends on whether we can shift the stuff
            # ourselves. Our own ships collect the top price by delivering, so
            # on a ware that flows there is no reason to discount. On a ware
            # that is piling up faster than twenty freighters can move it, the
            # cheapest throughput available is somebody else's ship, and that
            # only arrives if we are worth the trip.
            # Undercut the cheapest supplier we can see, on everything.
            #
            # This is a deliberate trade of margin for throughput. Pricing just
            # under the best bid earns the most per unit but only when our own
            # ships do the delivering, and it made this station the dearest
            # seller in the region on five wares out of six: every open sale was
            # one of our own freighters loading, and no outside trader ever
            # came. Cheap throughput is somebody else's ship, and it only shows
            # up if we are worth the trip.
            #
            # The station's marginal cost is near zero anyway: mined inputs and
            # its own energy. Almost any price is profit; an unsold pile is not.
            rivals = _rival_prices(known, offer["ware"])
            target = int(min(rivals) * UNDERCUT) if rivals else int(top * UNDERCUT)

            if abs(target - offer["price"]) < offer["price"] * PRICE_DEADBAND:
                continue
            if target < offer["price"] and buyers < MIN_BUYERS_TO_CUT:
                continue
            out.append(f"price {station['code']} {offer['ware']} sell {target}")
    return out


# Wares the bridge can point a ship at. Same limit as expansion: MD needs one
# comparison per ware, so the list is explicit on both sides.
SELLABLE = ("energycells", "water", "refinedmetals", "siliconwafers",
            "sunriseflowers", "microchips", "smartchips")
# Above this share of the station's stored volume, one ware is crowding out the
# rest and the whole trade fleet goes after it.
CROWDING = 0.35


def _volumes() -> dict:
    import json
    path = __import__("pathlib").Path(__file__).parent / "data" / "ware_volumes.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _rival_prices(known: list[dict], ware: str) -> list[float]:
    """What everyone else we can see is asking for the same ware, with stock."""
    return [o["price"] for station in known for o in station.get("offers", [])
            if o.get("ware") == ware and o.get("side") == "sell"
            and (o.get("amount") or 0) > 0 and o.get("price")]


def restart_explorers(state: dict, tried: dict) -> tuple[list[str], list[str]]:
    """Send explorers that are exploring nothing somewhere real.

    The report says plainly that a scout is sweeping ground we have seen, and
    the model still spent cycle after cycle on other things. Re-issuing an order
    to a ship that is demonstrably idle-in-disguise is not a judgement call, so
    it does not need one.

    Tried once each. If a ship comes back still exploring its own sector, the
    bridge could find nothing unknown within fifteen jumps and asking again will
    not change that; it is reported as a fact instead, which is a different
    problem and needs a different answer.
    """
    stuck = [a for a in state.get("assets", []) if _exploring_nothing(a)]
    send, exhausted = [], []
    for ship in stuck:
        code = ship["code"]
        if tried.get(code):
            exhausted.append(f"{code} found nothing unknown within reach even after "
                             f"being sent out again. The map around it is explored.")
        else:
            tried[code] = True
            send.append(f"explore {code}")
    # Ships that got moving are no longer stuck, so let them be tried again later.
    for code in list(tried):
        if code not in {a["code"] for a in stuck}:
            del tried[code]
    return send, exhausted


def focus_fleet(state: dict) -> list[str]:
    """Aim every assigned trader at one ware, and say which.

    Two things can be wrong with a warehouse, and they want opposite answers.

    **It is blocked.** One ware has taken so much room that the lines behind it
    stall. Then the only thing that matters is shifting that ware, whatever it
    is worth: a stopped production line earns nothing at all.

    **It is merely full.** Nothing is stuck, there is just more stock than the
    fleet can move. Then the question is not what takes the most space but what
    pays best for the space it takes, because every trip is a choice about what
    to leave behind.

    Measured at 53 hours: water at 9 Cr per cubic metre against microchips at
    54. A fleet hauling water earns a sixth of what the same ships earn hauling
    chips. The first version of this only ever looked at volume, so it would
    have sent nineteen freighters after the cheapest cargo on the station.
    """
    volumes = _volumes()
    if not volumes:
        return []

    for station in state.get("assets", []):
        if station.get("cls") != "station":
            continue
        stock = station.get("cargo") or {}
        offers = {o["ware"]: o for o in station.get("offers", [])
                  if o.get("side") == "sell"}
        room = {w: n * volumes.get(w, 0) for w, n in stock.items()
                if w in offers and w in SELLABLE and volumes.get(w)}
        total = sum(room.values())
        if not total:
            continue

        group = _trade_group(state)
        traders = [a for a in state.get("assets", [])
                   if (a.get("assignment") or {}).get("group") == group]
        if not traders:
            continue

        blocking, taken = max(room.items(), key=lambda kv: kv[1])
        if taken / total >= CROWDING:
            return [f"sellware {a['code']} {blocking}" for a in traders]

        # Nothing is blocked. Go for the best paying cargo instead, but only
        # among wares there is enough of to be worth a trip: pointing the fleet
        # at 40 units of something valuable wastes eighteen of nineteen ships.
        worth = {w: (offers[w].get("price") or 0) / volumes[w]
                 for w, m3 in room.items() if m3 >= WORTH_A_TRIP}
        if not worth:
            return [f"autotrade {a['code']}" for a in traders
                    if _default_order(a) == "TradeRoutine_Basic"]

        best = max(worth, key=worth.get)
        return [f"sellware {a['code']} {best}" for a in traders]
    return []


def _default_order(ship: dict) -> str | None:
    for order in ship.get("orders") or []:
        if order.get("default"):
            return order.get("order")
    return None


def _trade_group(state: dict) -> int | None:
    """Which subordinate group number means 'trade' on our stations."""
    for station in state.get("assets", []):
        for index, role in ((station.get("assignment") or {}).get("groups") or {}).items():
            if role == "trade":
                return int(index)
    return None


def _assign(action) -> str:
    """assign_ship -> attach a ship to one of our stations as trader or miner."""
    return f"assign {action.ship_ref} {action.station_id} {action.role}"


# Which wares can actually be mined, and with what. Straight from the game's own
# libraries/wares.xml, where these carry the "minable" tag alongside "solid" or
# "liquid". Water is not in the list: it is produced, not mined.
MINABLE = {
    "solid": {"ore", "silicon", "ice", "nividium"},
    "liquid": {"hydrogen", "helium", "methane"},
}


def _miner_kind(macro: str | None) -> str | None:
    """solid or liquid, from the ship macro (…_miner_solid_… / …_miner_liquid_…)."""
    for kind in MINABLE:
        if macro and f"miner_{kind}" in macro:
            return kind
    return None


def _mining_pointless(action, state: dict) -> str | None:
    """Reject sending a miner to a station that wants nothing it can mine.

    The game accepts the assignment happily and then gives the ship nothing to
    do: two solid miners sat docked for a night because their station buys only
    energycells and water, and neither is a mineral. From the outside that looks
    like the order never arrived.
    """
    if getattr(action, "role", None) != "mine":
        return None

    ship = next((a for a in state.get("assets", [])
                 if a.get("code") == action.ship_ref), None)
    station = next((a for a in state.get("assets", [])
                    if a.get("code") == action.station_id), None)
    if not ship or not station:
        return None

    kind = _miner_kind(ship.get("macro"))
    if not kind:
        return f"{action.ship_ref} is not a mining ship"

    wanted = {o["ware"] for o in station.get("offers", []) if o.get("side") == "buy"}
    if wanted & MINABLE[kind]:
        return None
    return (f"{action.station_id} buys nothing a {kind} miner can supply "
            f"(it wants {', '.join(sorted(wanted)) or 'nothing'}), so the ship "
            f"would sit idle")


def _blocked_reason(action, key) -> str | None:
    """Why this otherwise-executable action still must not be sent."""
    if key == ("expand_station", None):
        ware = getattr(action, "ware", "")
        if ware not in EXPANDABLE_WARES:
            return (f"the bridge cannot build production for {ware!r}; "
                    f"it knows {', '.join(EXPANDABLE_WARES)}")
    if key == ("set_behaviour", "autotrade") and getattr(action, "whitelist", None):
        wares = ", ".join(action.whitelist)
        return (f"whitelist ({wares}) cannot be transmitted; MD cannot parse "
                f"strings, so sending this would ignore half the instruction")
    return None


# (action type, discriminating value) -> command builder.
# The value is whatever second key makes the action executable; None means the
# action type alone is enough.
EXECUTABLE: dict[tuple[str, str | None], Callable] = {
    ("set_behaviour", "explore"): _explore,
    ("set_behaviour", "autotrade"): _autotrade,
    ("assign_ship", None): _assign,
    ("set_behaviour", "automine"): _automine,
    ("set_budget", None): _budget,
    ("expand_station", None): _expand,
    ("set_price", None): _price,
    ("set_trade_rule", None): _trade_rule,
}


def _key(action) -> tuple[str, str | None]:
    if action.type == "set_behaviour":
        return ("set_behaviour", action.behaviour)
    return (action.type, None)


# What an executable action looks like once it has already happened. Without
# this the agent re-sends the same order every cycle, because the plan does not
# change until the world does.
SATISFIED_BY_ORDER = {
    ("set_behaviour", "explore"): "Explore",
    ("set_behaviour", "autotrade"): "TradeRoutine",
    ("set_behaviour", "automine"): "MiningRoutine",
}


def _active_orders(state: dict) -> dict[str, str]:
    """{ship code: current order name} for our own ships.

    `save_parser` sorts the active order first, so this is what the ship is
    actually doing, not the `default="1"` fallback that sits at the front of the
    file.
    """
    out = {}
    for asset in state.get("assets", []):
        if asset.get("code") and asset.get("orders"):
            out[asset["code"]] = asset["orders"][0].get("order")
    return out


def _busy_with(action, state: dict) -> str | None:
    """The real order a ship is already carrying out, if any.

    A ship on nothing but its `default="1"` fallback is free to be tasked.
    A ship running a real order is left alone, whoever gave it: you, its station
    manager, or an earlier cycle of this agent. Overriding it would undo work in
    progress, and there is no way to tell from the savegame who ordered what.

    The game itself exposes `@object.order.$internalorder` for exactly this
    distinction, but only in the running game, not in the save. Until the
    Mission Director side reads that flag, this rule errs on the side of not
    touching anything that is already busy.
    """
    ship = getattr(action, "ship_ref", None)
    if not ship:
        return None
    for asset in state.get("assets", []):
        if asset.get("code") != ship:
            continue
        for order in asset.get("orders", []):
            if not order.get("default"):
                return order.get("order")
    return None


# What each budget level means as a share of the player's money. Must match the
# arithmetic in the bridge, which does the same sum on the game side.
BUDGET_SHARE = {"low": 0.10, "mid": 0.25, "high": 0.50}


def _budget_already_set(action, state: dict) -> bool:
    """True if the station already holds roughly the budget being asked for.

    Without this the agent re-sends the same budget every single cycle, because
    the plan does not change until the world does. The station's account carries
    `min` in whole credits, and so does the player money in the savegame, so the
    comparison is like for like.
    """
    share = BUDGET_SHARE.get(getattr(action, "level", ""), 0)
    money = (state.get("player") or {}).get("money") or 0
    if not share or not money:
        return False
    target = money * share
    for asset in state.get("assets", []):
        if asset.get("code") != getattr(action, "station_id", None):
            continue
        current = int((asset.get("account") or {}).get("min", 0) or 0)
        return current >= target * 0.9
    return False


def _exploring_nothing(ship: dict) -> bool:
    """True when a ship is exploring the sector it is already in.

    X4 accepts an Explore order aimed at the ship's own sector and carries it
    out for ever, sweeping ground it has already covered. From outside it is
    indistinguishable from real exploring: the order is Explore, the state is
    started, nothing fails. Five ships sat like that twice, and the third gate
    kept refusing to send them anywhere because they were already busy.
    """
    order = (ship.get("orders") or [{}])[0]
    if order.get("order") != "Explore":
        return False
    target = order.get("target_sector")
    return bool(target) and target == (ship.get("place") or {}).get("sector")


def _already_done(action, key, state: dict) -> bool:
    if key == ("set_budget", None):
        return _budget_already_set(action, state)
    wanted = SATISFIED_BY_ORDER.get(key)
    if not wanted or state is None:
        return False
    ship = getattr(action, "ship_ref", None)
    if not ship or _active_orders(state).get(ship) != wanted:
        return False
    if key == ("set_behaviour", "explore"):
        asset = next((a for a in state.get("assets", []) if a.get("code") == ship), None)
        if asset and _exploring_nothing(asset):
            return False   # busy, but with nothing
    return True


def to_commands(actions: list, state: dict | None = None) -> tuple[list[str], list[tuple]]:
    """Split actions into sendable commands and skipped ones with a reason.

    Pass `state` to suppress orders the game is already carrying out. This is
    the third gate: exists, allowed, and not already true.
    """
    commands: list[str] = []
    skipped: list[tuple] = []

    for action in actions:
        key = _key(action)
        builder = EXECUTABLE.get(key)
        if builder is None:
            label = key[0] if key[1] is None else f"{key[0]}({key[1]})"
            skipped.append((action, f"{label} is not executable yet, advice only"))
            continue
        if key == ("set_price", None) and state:
            out_of_band = _price_out_of_band(action, state)
            if out_of_band:
                skipped.append((action, out_of_band))
                continue

        busy = _busy_with(action, state) if state else None
        if busy and not _already_done(action, key, state):
            skipped.append((action, f"already busy with {busy}, not overriding"))
            continue

        blocked = _blocked_reason(action, key)
        if not blocked and key == ("assign_ship", None) and state:
            blocked = _mining_pointless(action, state)
        if not blocked and key == ("set_trade_rule", None) and state:
            blocked = _trade_rule_pointless(action, state)
        if blocked:
            skipped.append((action, blocked))
            continue
        if _already_done(action, key, state):
            skipped.append((action, "already in effect, not re-sent"))
            continue

        command = builder(action)

        # One ship, one order. The model has emitted "put ASO-629 on autotrade"
        # and "assign ASO-629 to KYV-745" in the same plan; sending both would
        # have the second silently undo the first. Priority order decides.
        ship = getattr(action, "ship_ref", None)
        if ship and any(c.split()[1] == ship for c in commands if len(c.split()) > 1):
            skipped.append((action, f"conflicts with an order already queued for {ship}"))
            continue

        if command in commands:
            # The model happily emits the same action twice with different
            # reasons ("buy energycells", "buy water"). One command is enough.
            skipped.append((action, "duplicate of a command already queued"))
            continue
        commands.append(command)

    return commands, skipped


def describe() -> str:
    """What the executor can currently do, for logging and for the README."""
    names = sorted(k[0] if k[1] is None else f"{k[0]}({k[1]})" for k in EXECUTABLE)
    return ", ".join(names)
