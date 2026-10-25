"""A strategist's plan, carried out by the rules (tasks/plan-strategy-2026-10.md).

The plan says where each station should be by the end of a few game hours:
how many production modules of which ware, how many miners and traders work
for it (`schemas.Strategy`). The rules do the rest: `standing.grow` builds
toward the modules, `fleet` assigns and buys toward the ships, `blueprints`
buys the blueprint a planned module needs. Every gate they go through still
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
    mods = st.get("modules") or []
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
    for goal in goals(data).values():
        for ware in goal.get("build") or {}:
            macro = (executor.EXPANSION_MODULES.get(ware) or (None,))[0]
            bp = (modules.get(macro) or {}).get("ware") if macro else None
            if bp and bp not in held:
                first, _ = purchases.start(data, bp, state)
                if first:
                    return purchases.first_commands(data, bp, first, state)
    return []


def fleet(state: dict, data: dict) -> list[str]:
    """Miners and traders toward the plan's numbers for each station.

    A free ship of the kind (no commander, no orders, not on an errand) is
    assigned first; with none, one is bought at the nearest wharf we know,
    under the catalog's brake of one purchase per game hour. One purchase a
    cycle at most, so the next cycle sees what the first bought."""
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
    out, bought = [], False
    for code, goal in plan.items():
        wants = [("mine", kind, n, f"{kind} miner", f"ship_{{race}}_m_miner_{kind}_01_a_macro",
                  lambda s, kind=kind: executor._miner_kind(s.get("macro")) == kind)
                 for kind, n in (goal.get("miners") or {}).items()]
        wants.append(("trade", None, goal.get("traders") or 0, "container freighter",
                      "ship_{race}_m_trans_container_01_a_macro",
                      lambda s: sitrep.ship_type(s.get("macro")) in executor.FREIGHTERS))
        for role, kind, target, label, pattern, fits in wants:
            group = executor.STATION_GROUPS[role]
            have = sum(1 for s in catalog._ships(state) if executor.serves(s, state) == (code, group)
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
                options = catalog._buy_options(state, ((label, pattern),))
                if options:
                    out.append(options[0].command)
                    bought = True
    return out


def lines(state: dict, data: dict) -> list[str]:
    """The plan and how far each station is, for the report."""
    import catalog
    import executor
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
        have = sum(1 for s in catalog._ships(state) if executor.serves(s, state) == (code, "trade"))
        parts.append(f"traders {have}/{goal.get('traders') or 0}")
        out.append(f"{code}: " + ", ".join(parts)
                   + (f"; the bridge cannot build {', '.join(unknown)}" if unknown else ""))
    return out
