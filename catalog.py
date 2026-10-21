"""The action catalog: situations in the save, each with only the actions that
can be carried out now (tasks/plan-catalog-2026-10.md, items 5.2 and 5.3).

Every cycle Python recognises situations in the parsed save and puts next to
each one the options that would be carried out if chosen, every detail filled
in: which ship, which station, which wharf and ship macro. The model only
decides per situation: which option, or none. Each option is put through the
same checks a proposal goes through (`planner.check_actions` and the
executor's gates), so an option is never refused afterwards.

One gate is lifted on purpose: "already busy, not overriding". It exists
because a proposal made without looking at a ship's orders could undo work in
progress. A catalog situation shows the ship's current order, and choosing to
change it is the decision. Everything else stays: roles, blueprints, money,
duplicates, "already in effect".

Situations Python already acts on by itself every cycle stay out of the
catalog: repricing, repairs below 70 % hull, feeding a build storage, hiring a
builder, revisiting stations, satellites, idle fighters on patrol.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import executor
import sitrep
from save_parser import SHIP_CLASSES

# Which production uses up a mined input: refined metals from ore, silicon
# wafers from silicon, water from ice (libraries/wares.xml). The bridge can
# expand a station with all three.
CONSUMER_OF = {"ore": "refinedmetals", "silicon": "siliconwafers", "ice": "water"}
# Ship macros carry the race in their name; a wharf builds its own race's
# ships. Factions whose wharfs are not known to build a given race are left
# out rather than guessed.
RACE = {"argon": "arg", "antigone": "arg", "hatikvah": "arg",
        "paranid": "par", "holyorder": "par", "trinity": "par",
        "teladi": "tel", "ministry": "tel",
        "split": "spl", "freesplit": "spl",
        "terran": "ter", "pioneers": "ter"}
# Orders that already are the answer to a threat: a ship on them stays.
GUARDING = {"ProtectStation", "ProtectPosition", "ProtectShip", "Patrol"}
# Orders of a ship answering an attack itself (ids from the game's aiscripts).
# The first catalog run with 5.6 offered "clear CVT-715's Attack" for a
# defender fighting in our home sector, and it was taken six times.
FIGHTING = {"Attack", "AttackInRange", "Attack_Player", "PlayerAttack", "Flee"}
UNKNOWN_ROUTE = 99             # what purchases.jumps returns without a path
MAX_SITUATIONS = 10            # per report, risk first
MAX_DANGER = 4                 # of which at most this many about ships at risk
SHIP_CAP = 3_000_000           # the most one bought M ship may cost
CAPITAL_FLOOR = 5_000_000      # below this after the reserve, money is not idle
PURCHASE_GAP = 3600            # game seconds between two ship purchases
BOUGHT = "[x4-agent lua] ORDER: bought"   # the purchase verb's logbook line
MAX_OPTIONS = 4


@dataclass
class Option:
    text: str
    command: str
    before: list[str] = field(default_factory=list)   # sent first, in order


@dataclass
class Situation:
    key: str                   # entry and subject, stable across cycles
    text: str
    options: list[Option] = field(default_factory=list)


# ---------------------------------------------------------------- helpers

def _assets(state: dict) -> dict[str, dict]:
    return {a.get("code"): a for a in state.get("assets", []) if a.get("code")}


def _ships(state: dict) -> list[dict]:
    occupied = state.get("player", {}).get("occupied_ship")
    return [a for a in state.get("assets", [])
            if a.get("cls") in SHIP_CLASSES and a.get("code") != occupied
            and sitrep.ship_type(a.get("macro")) != "escape pod"]


def _stations(state: dict) -> list[dict]:
    return [a for a in state.get("assets", []) if a.get("cls") == "station"]


def _order(ship: dict) -> str:
    return sitrep._first_order(ship) or "no orders"


def _through_gates(action: dict, state: dict) -> str | None:
    """The command an action would become, or None if any check refuses it."""
    import planner
    from schemas import PlannerResponse
    plan = PlannerResponse.model_validate({
        "assessment": "", "updated_goals": [],
        "actions": [{**action, "rationale": "catalog option"}]})
    ok, rejected = planner.check_actions(plan, state)
    if rejected or not ok:
        return None
    commands, skipped = executor.to_commands(ok, state, allow_busy=True)
    if skipped or len(commands) != 1:
        return None
    return commands[0]


def _option(text: str, action: dict, state: dict, clear: bool = False) -> Option | None:
    """An option if the action passes the gates. With `clear`, a ship that is
    carrying out an order of its own gets `clear` first, or the new order
    queues behind it (see `_holding`)."""
    command = _through_gates(action, state)
    if not command:
        return None
    held = _holding(action.get("ship_ref"), state) if clear else None
    return Option(text, command, [f"clear {action['ship_ref']}"] if held else [])


def _holding(code: str | None, state: dict) -> str | None:
    """The order a ship is carrying out that would hold up a new one.

    A new order lands behind the running one, and a MoveWait without a timeout
    never ends: VSR-185 and KGZ-352 came into the 73-hour save on one, and
    every catalog choice for them did nothing. A paid repair is not cleared
    (the money is gone once it is), nor a guarding order (it is the answer).
    """
    from types import SimpleNamespace
    if not code:
        return None
    order = executor._busy_with(SimpleNamespace(ship_ref=code), state)
    return None if order in ("Repair", *GUARDING, *FIGHTING) else order


def _where(sector: str | None) -> str:
    import gamedata
    return gamedata.pretty(sector, gamedata.load()) if sector else "an unknown sector"


def _combat(ship: dict) -> bool:
    macro = (ship.get("macro") or "").lower()
    return any(h in macro for h in executor.COMBAT_HINTS)


def _spare(state: dict) -> float:
    from purchases import RESERVE
    return (state.get("player", {}).get("money") or 0) * (1 - RESERVE)


def _bought_recently(state: dict) -> bool:
    """A ship bought within the last PURCHASE_GAP game seconds, by the purchase
    verb's own logbook line in the save."""
    now = state.get("meta", {}).get("playtime_s", 0.0)
    return any(text and text.startswith(BOUGHT) and now - t < PURCHASE_GAP
               for t, text in state.get("logbook", []))


def _idle_ship(state: dict, kind: str | None = None) -> str | None:
    """A ship of ours with no orders and no commander, of `kind` if given.

    An idle ship holds the purchase of another of its kind, whether or not
    the catalog has work for it: the brake used to count only idle ships with
    options, so six solid miners with nothing to mine did not stop the next
    one being bought. Only its own kind: an idle scout does nothing about a
    methane shortage, and holding the liquid miner for it took the one
    purchase the 16 saves need off the table.
    """
    return next((s["code"] for s in _ships(state) if sitrep.role_of(s) == "IDLE"
                 and (s.get("assignment") or {}).get("group") is None
                 and (kind is None or sitrep.ship_type(s.get("macro")) == kind)), None)


def _room(station: dict, ware: str) -> bool:
    """The station's store for this ware's transport type is below FULL."""
    import gamedata
    table = gamedata.wares()
    transport = (table.get(ware) or {}).get("transport")
    return executor.storage_fill(station, table).get(transport, 0.0) < executor.FULL


def _buy_options(state: dict, roles: tuple[tuple[str, str], ...]) -> list[Option]:
    """Ships to buy at the two nearest wharfs we know that build M ships.

    `roles` pairs a description with a macro pattern ("solid miner",
    "ship_{race}_m_miner_solid_01_a_macro"). Only a wharf's own race's ship,
    only with a known route, and nothing below the capital floor. The price
    is the wharf's; the cap is a ceiling, and the buy verb refuses above it.

    At most one purchase per game hour. The first catalog run in the game
    offered the same freighter every cycle and the model took it every
    cycle: two ships in six minutes, on course for forty in two hours. And
    no ship of a kind of which one of ours is idle (`_idle_ship`). Only the
    entries that show a need call this (5.6): a shortage of a mined ware,
    products piling up with no freighter free.
    """
    import gamedata
    from purchases import _graph, jumps
    spare = _spare(state)
    if spare < CAPITAL_FLOOR or _bought_recently(state):
        return []
    roles = tuple((role, pattern) for role, pattern in roles
                  if not _idle_ship(state, sitrep.ship_type(pattern.format(race="arg"))))
    if not roles:
        return []
    home = next((a for a in _stations(state) if a.get("modules")), None)
    if not home:
        return []
    graph, ships = _graph(), gamedata.ships()
    sector = (home.get("place") or {}).get("sector")
    yards = sorted((k for k in state.get("known_stations", [])
                    if "m" in (k.get("builds") or []) and RACE.get(k.get("owner"))
                    and jumps(graph, sector, (k.get("place") or {}).get("sector")) < UNKNOWN_ROUTE),
                   key=lambda k: jumps(graph, sector, (k.get("place") or {}).get("sector")))
    cap = int(min(SHIP_CAP, spare))
    options = []
    for yard in yards[:2]:
        race = RACE[yard["owner"]]
        hops = jumps(graph, sector, (yard.get("place") or {}).get("sector"))
        for role, pattern in roles:
            macro = pattern.format(race=race)
            if macro in ships:
                options.append(Option(
                    f"buy an M {role} at {yard['code']} ({yard['owner']}, {hops} jumps), at most {cap:,} Cr",
                    f"buyship {yard['code']} {yard['owner']} {macro} x4-agent-m {cap}"))
    return options


# ---------------------------------------------------------------- entries

def idle_ships(state: dict) -> list[Situation]:
    """A ship of ours with no orders and no commander earns nothing."""
    out = []
    stations = [s for s in _stations(state) if s.get("modules")]
    for ship in _ships(state):
        if sitrep.role_of(ship) != "IDLE" or (ship.get("assignment") or {}).get("group") is not None:
            continue
        kind = sitrep.ship_type(ship.get("macro"))
        code = ship["code"]
        candidates = []
        if kind in executor.FREIGHTERS or "freighter" in kind:
            candidates += [(f"assign {code} to {s['code']} as trader",
                            {"type": "assign_ship", "ship_ref": code, "station_id": s["code"], "role": "trade"})
                           for s in stations]
            candidates.append((f"put {code} on autotrade",
                               {"type": "set_behaviour", "ship_ref": code, "behaviour": "autotrade"}))
        elif executor._miner_kind(ship.get("macro")):
            candidates += [(f"assign {code} to {s['code']} as miner",
                            {"type": "assign_ship", "ship_ref": code, "station_id": s["code"], "role": "mine"})
                           for s in stations]
            candidates.append((f"put {code} on automine",
                               {"type": "set_behaviour", "ship_ref": code, "behaviour": "automine"}))
        elif "scout" in kind:
            candidates.append((f"send {code} exploring",
                               {"type": "set_behaviour", "ship_ref": code, "behaviour": "explore"}))
        elif _combat(ship):
            candidates += [(f"assign {code} to {s['code']} as defender",
                            {"type": "assign_ship", "ship_ref": code, "station_id": s["code"], "role": "defend"})
                           for s in stations]
        options = [o for o in (_option(t, a, state) for t, a in candidates) if o]
        if options:
            out.append(Situation(f"idle:{code}", f"{code} ({kind}) has no orders and no commander.",
                                 options[:MAX_OPTIONS]))
    return out


def no_budget(state: dict) -> list[Situation]:
    """A station manager without an operating budget opens no purchase orders.

    Only stations with modules: on GKL-870, with none built yet, the budget
    command had no effect and drew no answer, and the model sent it five
    cycles running. Its build is funded by Python (`executor.funding`).
    """
    out = []
    for st in _stations(state):
        acct = st.get("account") or {}
        if acct and int(acct.get("min", 0) or 0):
            continue
        modules = len(st.get("modules") or [])
        if not modules:
            continue
        what = f"{modules} modules"
        options = [o for o in (_option(f"set the budget of {st['code']} to {level}",
                                       {"type": "set_budget", "station_id": st["code"], "level": level},
                                       state) for level in ("low", "mid", "high")) if o]
        if options:
            out.append(Situation(f"budget:{st['code']}",
                                 f"{st['code']} has no operating budget ({what}).", options))
    return out


def storage_full(state: dict) -> list[Situation]:
    """A store at 90 % or more: what is in it decides what helps.

    Products piling up need more traders; mined inputs piling up need
    production that uses them. Storage modules would help both, and the
    bridge cannot build them yet. Taking miners off the station is not
    offered: `automine` queues a mining order but leaves the ship in the
    station's mining group, so it went on delivering to the full store
    (POS-705, twice, in the first catalog run). That needs a verb that
    releases a ship from its commander first.
    """
    import gamedata
    table = gamedata.wares()
    out = []
    ships = _ships(state)
    for st in _stations(state):
        cargo = st.get("cargo") or {}
        sells = {o["ware"] for o in st.get("offers", []) if o.get("side") == "sell"}
        for transport, share in executor.storage_fill(st, table).items():
            if share < executor.FULL:
                continue
            wares = sorted((w for w in cargo if (table.get(w) or {}).get("transport") == transport),
                           key=lambda w: -cargo[w])
            products = [w for w in wares if w in sells]
            inputs = [w for w in wares if w not in sells]
            candidates = []
            for ware in inputs:
                consumer = CONSUMER_OF.get(ware)
                if consumer:
                    candidates.append((f"expand {st['code']} with {consumer} production, which uses {ware}",
                                       {"type": "expand_station", "station_id": st["code"], "ware": consumer}))
            assigns = 0
            if products:
                hulls = executor.CARRIES.get(transport, ())
                for ship in ships:
                    if sitrep.ship_type(ship.get("macro")) in hulls \
                            and (ship.get("assignment") or {}).get("group") is None:
                        candidates.append((f"assign {ship['code']} to {st['code']} as trader",
                                           {"type": "assign_ship", "ship_ref": ship["code"],
                                            "station_id": st["code"], "role": "trade"}))
                        assigns += 1
            options = [o for o in (_option(t, a, state) for t, a in candidates) if o]
            if products and not assigns and transport == "container":
                # No freighter of ours is free for the products: one bought.
                options += _buy_options(state, (("container freighter",
                                                 "ship_{race}_m_trans_container_01_a_macro"),))[:2]
            text = (f"{st['code']} {transport} storage is {share * 100:.0f} % full "
                    f"({', '.join(wares[:4]) or 'unknown wares'}). The agent cannot build storage modules yet.")
            if options:
                out.append(Situation(f"storage:{st['code']}:{transport}", text, options[:MAX_OPTIONS]))
    return out


def _away_options(ship: dict, stations: list[dict], state: dict) -> list[Option]:
    """Getting a ship out of danger: a fighter home as a defender, a scout
    somewhere else. A fighter already in a station's defence group but held
    by an order of its own gets that order cleared, so it follows its
    assignment; the assignment itself is already in effect."""
    code, kind = ship["code"], sitrep.ship_type(ship.get("macro"))
    candidates = []
    if _combat(ship):
        candidates += [(f"bring {code} home: assign it to {s['code']} as defender",
                        {"type": "assign_ship", "ship_ref": code, "station_id": s["code"], "role": "defend"})
                       for s in stations]
    elif "scout" in kind:
        candidates.append((f"send {code} to explore somewhere else",
                           {"type": "set_behaviour", "ship_ref": code, "behaviour": "explore"}))
    options = [o for o in (_option(t, a, state, clear=True) for t, a in candidates) if o]
    held = _holding(code, state)
    if not options and held and _combat(ship) and (ship.get("assignment") or {}).get("group") is not None:
        options.append(Option(f"clear {code}'s {held} so it follows its assignment", f"clear {code}"))
    return options[:MAX_OPTIONS]


def under_fire(state: dict) -> list[Situation]:
    """A ship attacked recently, as the report's UNDER ATTACK section lists it."""
    out = []
    now = state.get("meta", {}).get("playtime_s", 0.0)
    stations = [s for s in _stations(state) if s.get("modules")]
    for ship in _ships(state):
        hit = ship.get("attack") or {}
        if not hit or hit.get("method") in sitrep.HARMLESS_ATTACKS or now - hit["time"] > sitrep.ATTACK_MEMORY:
            continue
        if _order(ship) in GUARDING | FIGHTING:
            continue  # it is defending, fighting back or fleeing already
        code, kind = ship["code"], sitrep.ship_type(ship.get("macro"))
        options = _away_options(ship, stations, state)
        if options:
            sector = (ship.get("place") or {}).get("sector")
            out.append(Situation(f"fire:{code}",
                                 f"{code} ({kind}) was attacked {(now - hit['time']) / 60:.0f} minutes ago "
                                 f"in {_where(sector)}; it is on {_order(ship)}.", options[:MAX_OPTIONS]))
    return out


def in_hostile_space(state: dict) -> list[Situation]:
    """A ship of ours away from home in a sector with a major or moderate
    threat (the report's THREATS section), not on a guarding order."""
    out = []
    home = {(s.get("place") or {}).get("sector") for s in _stations(state)}
    stations = [s for s in _stations(state) if s.get("modules")]
    danger = {t["sector"]: t for t in sitrep.threats(state) if t["strength"] != "minor"}
    for ship in _ships(state):
        sector = (ship.get("place") or {}).get("sector")
        if sector not in danger or sector in home or _order(ship) in GUARDING:
            continue
        code, kind = ship["code"], sitrep.ship_type(ship.get("macro"))
        options = _away_options(ship, stations, state)
        if options:
            factions = ", ".join(sorted(danger[sector]["factions"]))
            out.append(Situation(f"danger:{code}",
                                 f"{code} ({kind}) is in {_where(sector)}, where a {danger[sector]['strength']} "
                                 f"threat ({factions}) was seen; it is on {_order(ship)}.",
                                 options[:MAX_OPTIONS]))
    return out


def covered_ground(state: dict) -> list[Situation]:
    """An explorer sweeping the sector it is already in finds nothing new."""
    out = []
    for ship in _ships(state):
        if not executor._exploring_nothing(ship, state):
            continue
        option = _option(f"send {ship['code']} to an unseen sector",
                         {"type": "set_behaviour", "ship_ref": ship["code"], "behaviour": "explore"}, state,
                         clear=True)
        if option:
            out.append(Situation(f"explore:{ship['code']}",
                                 f"{ship['code']} is exploring the sector it is already in, which we "
                                 f"have seen; it finds nothing new there.", [option]))
    return out


def mined_shortage(state: dict) -> list[Situation]:
    """A station low on a ware that is mined, not bought: miners are the answer.

    The report has said so in words since the model went exploring for a
    seller of ore, and the model kept asking for it under OTHER: QDA-703 short
    of methane with no liquid miner, in four of the 16 saves. The options are
    our miners of that kind, those working for nobody first, and one bought.
    Miners in the station's mining group and in its sector are taken to be
    its own already: which commander a subordinate has is not in the save,
    only its group number (save_parser._assignment).
    """
    out = []
    ships = _ships(state)
    for st in _stations(state):
        mining = {int(i) for i, role in ((st.get("assignment") or {}).get("groups") or {}).items()
                  if role == "mining"}
        sector = (st.get("place") or {}).get("sector")
        for code, ware, have, target in sitrep.low_stock([st]):
            kind = next((k for k, wares in executor.MINABLE.items() if ware in wares), None)
            if not kind:
                continue
            fleet = [s for s in ships if executor._miner_kind(s.get("macro")) == kind]
            own = [s for s in fleet if (s.get("assignment") or {}).get("group") in mining
                   and (s.get("place") or {}).get("sector") == sector]
            free = sorted((s for s in fleet if s not in own),
                          key=lambda s: (s.get("assignment") or {}).get("group") is not None)
            assigns = [o for o in (_option(f"assign {s['code']} to {code} as miner (now on {_order(s)})",
                                           {"type": "assign_ship", "ship_ref": s["code"],
                                            "station_id": code, "role": "mine"}, state)
                                   for s in free) if o]
            # A miner bought only with room for what it brings (5.6).
            buys = (_buy_options(state, ((f"{kind} miner", f"ship_{{race}}_m_miner_{kind}_01_a_macro"),))
                    if _room(st, ware) else [])
            options = (assigns[:2] + buys[:2])[:MAX_OPTIONS]
            if options:
                out.append(Situation(
                    f"short:{code}:{ware}",
                    f"{code} is low on {ware} ({have} of {target}, {100 * have / target:.0f} %). "
                    f"{ware} is mined, not bought; {len(own)} of our {len(fleet)} {kind} miner(s) "
                    f"work for {code}.", options))
    return out


# Risk first, then what blocks production, then idle hands. Money alone is
# not a situation (5.6): a purchase belongs to the need it answers.
ENTRIES = (under_fire, in_hostile_space, storage_full, mined_shortage, no_budget,
           idle_ships, covered_ground)
DANGER = (under_fire, in_hostile_space)


def situations(state: dict) -> list[Situation]:
    """Every situation, in priority order, at most MAX_SITUATIONS of them."""
    out: list[Situation] = []
    seen: set[str] = set()
    for entry in ENTRIES:
        found = entry(state)
        if entry in DANGER:
            found = [s for s in found if s.key.split(":")[1] not in seen]
            room = MAX_DANGER - sum(1 for s in out if s.key.split(":")[0] in ("fire", "danger"))
            found = found[:max(room, 0)]
            seen.update(s.key.split(":")[1] for s in found)
        out += found
    return out[:MAX_SITUATIONS]


# ---------------------------------------------------------------- the report and the answer

def render(found: list[Situation]) -> list[str]:
    """The report's SITUATIONS section, numbered the way the answer refers to it."""
    if not found:
        return []
    lines = ["", "# SITUATIONS (decide each under DECISIONS: `S1: 2` takes option 2 of S1, "
                 "`S1: none` takes none)"]
    for n, situation in enumerate(found, 1):
        lines.append(f"S{n} {situation.text}")
        lines += [f"   {k}. {option.text}" for k, option in enumerate(situation.options, 1)]
    return lines


def decide(found: list[Situation], analysis: str) -> tuple[list[str], list[str], dict]:
    """Commands for the options chosen, notes on answers that do not fit, and counts.

    A situation without an answer counts as none. A line that names no
    situation or an option that does not exist is reported, never guessed,
    and so is a second answer to the same situation: one cycle the model
    wrote S1: 1 to S1: 4 and all four miners left their station.
    """
    import action_lines
    answers, unreadable = action_lines.decisions(analysis)
    commands, notes = [], [f"could not read the decision: {line}" for line in unreadable]
    answered, chosen = set(), 0
    for number, option, _ in answers:
        if not 1 <= number <= len(found):
            notes.append(f"S{number} is not a situation in this report")
            continue
        if number in answered:
            notes.append(f"S{number} answered more than once; only the first answer counts")
            continue
        answered.add(number)
        if option is None:
            continue
        situation = found[number - 1]
        if not 1 <= option <= len(situation.options):
            notes.append(f"S{number} has no option {option}")
            continue
        chosen += 1
        command = situation.options[option - 1].command
        if command.startswith("buyship") and any(c.startswith("buyship") for c in commands):
            notes.append(f"S{number}: one ship purchase per cycle, {command} not sent")
            continue
        for c in situation.options[option - 1].before + [command]:
            if c not in commands:
                commands.append(c)
    counts = {"situations": len(found), "options": sum(len(s.options) for s in found),
              "chosen": chosen, "none": len(answered) - chosen,
              "unanswered": len(found) - len(answered), "unreadable": len(notes),
              "other": len(action_lines.other_lines(analysis))}
    return commands, notes, counts
