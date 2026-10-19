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


def _option(text: str, action: dict, state: dict) -> Option | None:
    command = _through_gates(action, state)
    return Option(text, command) if command else None


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


def _buy_options(state: dict, roles: tuple[tuple[str, str], ...]) -> list[Option]:
    """Ships to buy at the two nearest wharfs we know that build M ships.

    `roles` pairs a description with a macro pattern ("solid miner",
    "ship_{race}_m_miner_solid_01_a_macro"). Only a wharf's own race's ship,
    only with a known route, and nothing below the capital floor. The price
    is the wharf's; the cap is a ceiling, and the buy verb refuses above it.

    At most one purchase per game hour. The first catalog run in the game
    offered the same freighter every cycle and the model took it every
    cycle: two ships in six minutes, on course for forty in two hours.
    """
    import gamedata
    from purchases import _graph, jumps
    spare = _spare(state)
    if spare < CAPITAL_FLOOR or _bought_recently(state):
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
    production that uses them, or miners selling elsewhere for a while.
    Storage modules would help both, and the bridge cannot build them yet.
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
            for ship in ships:
                kind = executor._miner_kind(ship.get("macro"))
                if kind and any(w in executor.MINABLE.get(kind, ()) for w in inputs) \
                        and (ship.get("assignment") or {}).get("group") is not None:
                    candidates.append((f"take miner {ship['code']} off the station onto automine for a while",
                                       {"type": "set_behaviour", "ship_ref": ship["code"], "behaviour": "automine"}))
            if products:
                hulls = executor.CARRIES.get(transport, ())
                for ship in ships:
                    if sitrep.ship_type(ship.get("macro")) in hulls \
                            and (ship.get("assignment") or {}).get("group") is None:
                        candidates.append((f"assign {ship['code']} to {st['code']} as trader",
                                           {"type": "assign_ship", "ship_ref": ship["code"],
                                            "station_id": st["code"], "role": "trade"}))
            options = [o for o in (_option(t, a, state) for t, a in candidates) if o]
            text = (f"{st['code']} {transport} storage is {share * 100:.0f} % full "
                    f"({', '.join(wares[:4]) or 'unknown wares'}). The agent cannot build storage modules yet.")
            if options:
                out.append(Situation(f"storage:{st['code']}:{transport}", text, options[:MAX_OPTIONS]))
    return out


def under_fire(state: dict) -> list[Situation]:
    """A ship attacked recently, as the report's UNDER ATTACK section lists it."""
    out = []
    now = state.get("meta", {}).get("playtime_s", 0.0)
    stations = [s for s in _stations(state) if s.get("modules")]
    for ship in _ships(state):
        hit = ship.get("attack") or {}
        if not hit or hit.get("method") in sitrep.HARMLESS_ATTACKS or now - hit["time"] > sitrep.ATTACK_MEMORY:
            continue
        if _order(ship) in GUARDING:
            continue  # it is already defending; being shot at is its job
        code, kind = ship["code"], sitrep.ship_type(ship.get("macro"))
        candidates = []
        if _combat(ship):
            candidates += [(f"bring {code} home: assign it to {s['code']} as defender",
                            {"type": "assign_ship", "ship_ref": code, "station_id": s["code"], "role": "defend"})
                           for s in stations]
        elif "scout" in kind:
            candidates.append((f"send {code} to explore somewhere else",
                               {"type": "set_behaviour", "ship_ref": code, "behaviour": "explore"}))
        options = [o for o in (_option(t, a, state) for t, a in candidates) if o]
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
        candidates = []
        if _combat(ship):
            candidates += [(f"bring {code} home: assign it to {s['code']} as defender",
                            {"type": "assign_ship", "ship_ref": code, "station_id": s["code"], "role": "defend"})
                           for s in stations]
        elif "scout" in kind:
            candidates.append((f"send {code} to explore somewhere else",
                               {"type": "set_behaviour", "ship_ref": code, "behaviour": "explore"}))
        options = [o for o in (_option(t, a, state) for t, a in candidates) if o]
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
        if not executor._exploring_nothing(ship):
            continue
        option = _option(f"send {ship['code']} to an unseen sector",
                         {"type": "set_behaviour", "ship_ref": ship["code"], "behaviour": "explore"}, state)
        if option:
            out.append(Situation(f"explore:{ship['code']}",
                                 f"{ship['code']} is exploring the sector it is already in.", [option]))
    return out


def idle_capital(state: dict) -> list[Situation]:
    """Money above the reserve that nothing is using: concrete ships to buy,
    a freighter or a solid miner of the wharf's own race, nearest wharf first.

    Not while a ship of ours waits for work the catalog can give it: the
    ships we have go to work before more are bought, a bought one included,
    since it arrives without orders.
    """
    if idle_ships(state):
        return []
    options = _buy_options(state, (("container freighter", "ship_{race}_m_trans_container_01_a_macro"),
                                   ("solid miner", "ship_{race}_m_miner_solid_01_a_macro")))
    if not options:
        return []
    return [Situation("capital", f"{_spare(state):,.0f} Cr above the reserve is not being used.",
                      options[:MAX_OPTIONS])]


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
            buys = _buy_options(state, ((f"{kind} miner", f"ship_{{race}}_m_miner_{kind}_01_a_macro"),))
            options = (assigns[:2] + buys[:2])[:MAX_OPTIONS]
            if options:
                out.append(Situation(
                    f"short:{code}:{ware}",
                    f"{code} is low on {ware} ({have} of {target}, {100 * have / target:.0f} %). "
                    f"{ware} is mined, not bought; {len(own)} of our {len(fleet)} {kind} miner(s) "
                    f"work for {code}.", options))
    return out


# Risk first, then what blocks production, then money, then idle hands.
ENTRIES = (under_fire, in_hostile_space, storage_full, mined_shortage, no_budget,
           idle_capital, idle_ships, covered_ground)
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
    situation or an option that does not exist is reported, never guessed.
    """
    import action_lines
    answers, unreadable = action_lines.decisions(analysis)
    commands, notes = [], [f"could not read the decision: {line}" for line in unreadable]
    answered, chosen = set(), 0
    for number, option, _ in answers:
        if not 1 <= number <= len(found):
            notes.append(f"S{number} is not a situation in this report")
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
        if command not in commands:
            commands.append(command)
    counts = {"situations": len(found), "options": sum(len(s.options) for s in found),
              "chosen": chosen, "none": len(answered) - chosen,
              "unanswered": len(found) - len(answered), "unreadable": len(notes),
              "other": len(action_lines.other_lines(analysis))}
    return commands, notes, counts
