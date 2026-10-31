"""A strategist's plan, carried out by the rules (tasks/plan-strategy-2026-10.md).

The plan says where each station should be by the end of a few game hours:
how many production modules of which ware, how many miners and traders work
for it and how many combat ships defend it (`schemas.Strategy`). The rules do the rest: `standing.grow` builds
toward the modules, `fleet` assigns and buys toward the ships, `blueprints`
buys the blueprint a planned module needs and the ship and equipment
blueprints the plan names. A ship whose blueprint we hold is built at a wharf
of ours rather than bought (`own_build`). Every gate they go through still
applies, and without a plan nothing here does anything.

For now the plan comes from a file, X4_STRATEGY_FILE, read every cycle so it
can be changed while a run goes on; a strategist model will write the same
thing. Either way it lives in the agent's memory under "strategy".
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from schemas import Strategy

STRATEGY_FILE = os.environ.get("X4_STRATEGY_FILE")


def load(data: dict, state: dict) -> list[str]:
    """Take the plan from X4_STRATEGY_FILE into memory when it has changed.
    Returns a line for the report when the file cannot be used."""
    if not STRATEGY_FILE:
        return []
    try:
        text = Path(STRATEGY_FILE).read_text(encoding="utf-8")
        plan = Strategy.model_validate_json(text).model_dump()
    except (OSError, ValueError) as exc:
        return [f"strategy file not used: {str(exc)[:200]}"]
    if (data.get("strategy") or {}).get("plan") != plan:
        data["strategy"] = {"plan": plan, "since": (state.get("meta") or {}).get("playtime_s") or 0,
                            "source": Path(STRATEGY_FILE).name}
    return []


def goals(data: dict) -> dict[str, dict]:
    """Station code -> its goal, from the plan in memory; empty without one."""
    return ((data.get("strategy") or {}).get("plan") or {}).get("stations") or {}


def built(st: dict, ware: str) -> int:
    """How many modules for this plan entry the station has standing.

    A production ware counts every production module that makes it, of any
    race; storage, docks and habitats count by their kind, of any size.
    """
    import economics
    import executor
    mods = st.get("modules") or []
    if ware in ("wharf", "wharf_l", "maintenance"):
        return mods.count(executor.EXPANSION_MODULES[ware][0])
    if ware == "defence":
        return sum(1 for m in mods if m.startswith("defence_"))
    if ware == "dock":
        return sum(1 for m in mods if m.startswith("dockarea_"))
    if ware.startswith("storage_"):
        return sum(1 for m in mods if re.match(rf"storage_[a-z]+_[sml]_{ware[len('storage_'):]}_", m))
    if ware.startswith("habitation_"):
        return sum(1 for m in mods if m.startswith(f"hab_{ware[len('habitation_'):]}_"))
    return sum(1 for m in mods if economics.product_of(m) == ware)


def next_builds(st: dict, data: dict) -> list[str] | None:
    """The plan entries this station is still short of, in the plan's order.
    None when the plan says nothing about the station's modules, so the
    margin ranking decides as before; an empty list when every target stands."""
    goal = goals(data).get(st.get("code"))
    if not goal or not goal.get("build"):
        return None
    return [ware for ware, n in goal["build"].items() if built(st, ware) < n]


def blueprints(state: dict, data: dict) -> list[str]:
    """The blueprint of a planned module we do not hold is bought, one errand
    at a time, through the purchase job every blueprint goes through (it
    buys the licence first where one is needed). Called by agent.py with the
    other job commands, as `standing.connectors` is."""
    import executor
    import gamedata
    import purchases
    if data.get("purchases"):
        return []
    held = set((state.get("player") or {}).get("blueprints") or [])
    modules = gamedata.modules()
    stations = {a.get("code"): a for a in state.get("assets", []) if a.get("cls") == "station"}
    for code, goal in goals(data).items():
        for ware in goal.get("build") or {}:
            if ware not in executor.EXPANSION_MODULES:
                continue
            # The stores the bridge adds with it too: a gas module without the
            # liquid store's blueprint would never be built.
            for macro in executor.modules_needed(stations.get(code) or {}, ware):
                bp = (modules.get(macro) or {}).get("ware")
                if bp and bp not in held:
                    first, _ = purchases.start(data, bp, state)
                    if first:
                        return purchases.first_commands(data, bp, first, state)
    for ware in ((data.get("strategy") or {}).get("plan") or {}).get("blueprints") or []:
        if ware not in held:
            first, _ = purchases.start(data, ware, state)
            if first:
                return purchases.first_commands(data, ware, first, state)
    return []


def offers(state: dict, data: dict) -> list[str]:
    """Once per faction and tag: what the factions that sell a blueprint the
    plan names list under its tag, and under thrusters, which no faction owns
    in wares.xml (gamedata.build_blueprints). The bridge logs it (`offers`);
    nothing is bought."""
    import gamedata
    named = ((data.get("strategy") or {}).get("plan") or {}).get("blueprints") or []
    known = {st.get("owner") for st in state.get("known_stations", [])}
    done = data.setdefault("standing", {}).setdefault("offers", [])
    out = []
    for ware in named:
        entry = gamedata.blueprints().get(ware) or {}
        tags = [t for t in entry.get("tags") or [] if t != "equipment"] + ["thruster"]
        for faction in entry.get("owners") or []:
            for tag in tags:
                key = f"{faction} {tag}"
                if faction in known and key not in done:
                    done.append(key)
                    out.append(f"offers {key}")
    return out


def own_build(state: dict, pattern: str, size: str = "m") -> str | None:
    """`buildship` at a wharf of ours, for the first race whose blueprint of
    this ship we hold, with an engine and a thruster blueprint of its size.

    Our wharf builds from the blueprints we hold (x4agent.lua,
    build_own_ship): engine, thruster, shields, weapons and turrets, each
    where a blueprint of ours fits the slot. The ship menu takes no order
    with the engine or thruster slot empty (helper.lua, allowempty), and
    ship7-camp's first order went in with no thruster: none was ours. A
    generic thruster has no owner in wares.xml; the factions' representatives
    list it (`offers`), and the purchase job finds its sellers there. The same
    brake as a purchase: one an hour, none while a ship of the kind is on
    order or idle, and not at a wharf where one of ours has waited too long.
    Nothing is built until the wharf has a ship trader (`standing.shiptraders`).
    """
    import catalog
    import executor
    import sitrep
    held = set((state.get("player") or {}).get("blueprints") or [])
    for part in ("engine_", "thruster_"):
        if not any(w.startswith(part) and f"_{size}_" in w for w in held):
            return None
    if catalog._bought_recently(state):
        return None
    stuck, coming = catalog._orders(state)
    kind = sitrep.ship_type(pattern.format(race="arg"))
    if kind in coming or catalog._idle_ship(state, kind):
        return None
    macro = next((pattern.format(race=race) for race in sorted(set(catalog.RACE.values()))
                  if pattern.format(race=race).removesuffix("_macro") in held), None)
    bay = executor.EXPANSION_MODULES["wharf_l" if size == "l" else "wharf"][0]
    wharf = next((st for st in catalog._stations(state)
                  if bay in (st.get("modules") or [])
                  and st.get("code") not in stuck), None)
    if not (macro and wharf):
        return None
    return f"buildship {wharf['code']} {macro} {sitrep.ship_name(macro)}"


def _size(pattern: str) -> str:
    """"ship_{race}_l_destroyer_01_a_macro" -> "l"."""
    return pattern.split("_")[2]


def _working(code: str, role: str) -> set[tuple[str, str]]:
    """What `executor.serves` says of a ship that counts toward `role` at `code`.

    A trader lent to the station's build storage goes back to trading when the
    build is done (`executor.feed_build_storages`), so it is still one of the
    station's traders. Counted as gone, it was bought again: ship7-camp ended
    with six freighters at GKL-870's build storage and two trading, for a plan
    of two.
    """
    import executor
    groups = {executor.STATION_GROUPS[role]}
    if role == "trade":
        groups.add(executor.STATION_GROUPS["buildstorage"])
    return {(code, group) for group in groups}


def fleet(state: dict, data: dict) -> list[str]:
    """Miners, traders and defenders toward the plan's numbers for each station.

    A free ship of the kind (no commander, no orders, not on an errand) is
    assigned first; with none, one is bought at the nearest wharf we know,
    under the catalog's brake of one purchase per game hour. One purchase a
    cycle at most, so the next cycle sees what the first bought. A ship whose
    blueprint we hold is built at a wharf of ours (`own_build`); one whose
    blueprint the plan names waits until every blueprint the plan names is
    ours, or the faction's ship would be bought while the errand is out."""
    import catalog
    import executor
    import purchases
    import sitrep
    plan = goals(data)
    if not plan:
        return []
    errand = purchases.ships_in_use(data)
    free = [s for s in catalog._ships(state)
            if (s.get("assignment") or {}).get("group") is None and s.get("code") not in errand
            and sitrep.role_of(s) == "IDLE"]
    held = set((state.get("player") or {}).get("blueprints") or [])
    named = set(((data.get("strategy") or {}).get("plan") or {}).get("blueprints") or [])
    races = sorted(set(catalog.RACE.values()))
    out, bought = [], False
    for code, goal in plan.items():
        wants = [("mine", kind, n, f"{kind} miner", f"ship_{{race}}_m_miner_{kind}_01_a_macro",
                  lambda s, kind=kind: executor._miner_kind(s.get("macro")) == kind)
                 for kind, n in (goal.get("miners") or {}).items()]
        wants.append(("trade", None, goal.get("traders") or 0, "container freighter",
                      "ship_{race}_m_trans_container_01_a_macro",
                      lambda s: sitrep.ship_type(s.get("macro")) in executor.FREIGHTERS))
        # Any combat ship of ours defends; a new one is an M frigate, which
        # our S/M wharf builds with the M engine, thruster and turrets whose
        # blueprints we hold.
        wants.append(("defend", None, goal.get("defenders") or 0, "frigate",
                      "ship_{race}_m_frigate_01_a_macro", catalog._combat))
        # Against an XL an M frigate is lost (ship7d-camp, ship7e3-camp). The
        # plan's destroyers come from our own L bay only: a faction's capital
        # ship needs its ally ceremony, we hold Teladi's, and we know no Teladi
        # wharf for L.
        wants.append(("defend", None, goal.get("destroyers") or 0, "destroyer",
                      "ship_{race}_l_destroyer_01_a_macro",
                      lambda s: sitrep.ship_type(s.get("macro")) == "destroyer"))
        for role, kind, target, label, pattern, fits in wants:
            have = sum(1 for s in catalog._ships(state) if executor.serves(s, state) in _working(code, role)
                       and fits(s))
            if have >= target:
                continue
            pick = next((s for s in free if fits(s)), None)
            if pick:
                command = catalog._through_gates({"type": "assign_ship", "ship_ref": pick["code"],
                                                  "station_id": code, "role": role}, state)
                if command:
                    out.append(command)
                    free.remove(pick)
                    continue
            if not bought:
                own = own_build(state, pattern, _size(pattern))
                waiting = (not own and named - held
                           and any(pattern.format(race=r).removesuffix("_macro") in named for r in races))
                options = ([] if (own or waiting or _size(pattern) != "m")
                           else catalog._buy_options(state, ((label, pattern),)))
                if own or options:
                    out.append(own or options[0].command)
                    bought = True
    return out


def lines(state: dict, data: dict) -> list[str]:
    """The plan and how far each station is, for the report."""
    import catalog
    import executor
    import sitrep
    held = data.get("strategy") or {}
    plan = goals(data)
    if not plan:
        return []
    out = [f"set at {held.get('since', 0) / 3600:.1f} h for {held['plan'].get('horizon_hours')} h "
           f"({held.get('source', 'model')}): {held['plan'].get('rationale', '')}"]
    stations = {st.get("code"): st for st in catalog._stations(state)}
    for code, goal in plan.items():
        st = stations.get(code)
        if not st:
            out.append(f"{code}: not one of our stations")
            continue
        parts = [f"{w} {built(st, w)}/{n}" for w, n in (goal.get("build") or {}).items()]
        unknown = [w for w in goal.get("build") or {} if w not in executor.EXPANSION_MODULES]
        for kind, n in (goal.get("miners") or {}).items():
            have = sum(1 for s in catalog._ships(state) if executor.serves(s, state) == (code, "mining")
                       and executor._miner_kind(s.get("macro")) == kind)
            parts.append(f"{kind} miners {have}/{n}")
        have = sum(1 for s in catalog._ships(state) if executor.serves(s, state) in _working(code, "trade"))
        parts.append(f"traders {have}/{goal.get('traders') or 0}")
        have = sum(1 for s in catalog._ships(state)
                   if executor.serves(s, state) in _working(code, "defend") and catalog._combat(s))
        parts.append(f"defenders {have}/{goal.get('defenders') or 0}")
        if goal.get("destroyers"):
            have = sum(1 for s in catalog._ships(state)
                       if executor.serves(s, state) in _working(code, "defend")
                       and sitrep.ship_type(s.get("macro")) == "destroyer")
            parts.append(f"destroyers {have}/{goal['destroyers']}")
        out.append(f"{code}: " + ", ".join(parts)
                   + (f"; the bridge cannot build {', '.join(unknown)}" if unknown else ""))
    return out
