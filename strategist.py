"""The strategist: a strong model that sets goals for the next game hours.

Strategy step 4 (tasks/plan-strategy-2026-10.md). Every few game hours, or
when there is no plan, the strategist gets a report richer than a cycle's:
each station's modules, stores, stock and account, its miners and traders,
what one more module of each ware costs and earns (`economics.py`), which
wares the bridge can build and which blueprints are held, and how far the
current plan got. It answers with a plan in `schemas.Strategy` form; the
rules carry it out (`strategy.py`), through every gate they always go through.

Through the Claude API only (X4_STRATEGIST_MODEL, key in ANTHROPIC_API_KEY),
because the plan comes back as structured output, validated before it is
stored. The answer's form uses lists where the plan uses maps, since a map
with free keys is not something a JSON schema for structured output is
documented to take; `to_strategy` turns one into the other.
"""
from __future__ import annotations

import os
import time
from typing import Literal

from pydantic import BaseModel, Field

STRATEGIST_MODEL = os.environ.get("X4_STRATEGIST_MODEL")   # e.g. "claude-opus-5-5"
DEFAULT_HORIZON = 3.0                                       # game hours, when a plan names none


class BuildTarget(BaseModel):
    ware: str = Field(description="A ware the bridge can build (see BUILDABLE), or storage_solid, "
                                  "storage_container, dock, habitation_<race>")
    modules: int = Field(description="How many modules of it the station should have in all, "
                                     "counting those it has")


class MinerTarget(BaseModel):
    kind: Literal["solid", "liquid"]
    count: int = Field(description="How many miners of this kind should work for the station")


class StationPlan(BaseModel):
    station: str = Field(description="Station code, e.g. KYV-745")
    build: list[BuildTarget]
    miners: list[MinerTarget]
    traders: int = Field(description="How many freighters should trade for the station")


class StrategistPlan(BaseModel):
    # First, so the reasoning comes before the numbers: last, it came back "x".
    rationale: str = Field(description="Why this plan, in three to six sentences: what the market "
                                       "lacks, what we can supply, what it costs and when it pays back")
    horizon_hours: float = Field(description="Game hours the plan is for, 2 to 6")
    stations: list[StationPlan]


SYSTEM = """You are the strategist of an X4: Foundations empire that is played by
deterministic rules. Every few game hours you set where each station should be
by the end of the next few game hours: how many production modules of which
ware, how many miners of each kind and how many traders work for it. The rules
then build and assign toward those numbers by themselves. They buy a planned
module's blueprint, refuse what cannot be built (no blueprint for sale, no
room on the plot, not enough money), and never sell or demolish anything:
numbers below what a station has change nothing.

What experience and our own runs say:
* Build only where the market has a hole. A station built for profit alone
  saturates its market and then cannot sell; check the known demand and what
  we already hold in hours of a module's output before adding a module.
* Ships are the economy's main sink: wharfs and shipyards wait for hull parts,
  weapon components and the like. Food, medical supplies, energy cells and
  gases the NPC economy usually fills itself.
* A blueprint is paid once for every module of its kind after it; a module's
  own payback is the one without the blueprint.
* Mining silicon depends on the pilots' skill to the fourth power; more
  miners with poor pilots add little. Ore and ice do not care.
* Advanced modules need the selling faction's ally licence; plan them only if
  the report shows the blueprint held or for sale.
* Every purchase of a ship is money out of growth; buy ships only for a
  target that a free ship cannot fill.

The player's own policy follows as GUIDELINES; it has priority over the
advice above where they differ."""


def due(data: dict, state: dict) -> bool:
    """A plan is asked for when there is none, or the last one's horizon has passed."""
    held = data.get("strategy") or {}
    plan = held.get("plan") or {}
    if not plan:
        return True
    now = (state.get("meta") or {}).get("playtime_s") or 0
    return now - (held.get("since") or 0) >= 3600 * (plan.get("horizon_hours") or DEFAULT_HORIZON)


def report(state: dict, data: dict) -> str:
    """What the strategist plans on: stations, fleets, economics, the plan so far."""
    import catalog
    import economics
    import executor
    import gamedata
    import strategy
    meta, player = state.get("meta") or {}, state.get("player") or {}
    held_bp = set(player.get("blueprints") or [])
    modules = gamedata.modules()
    lines = [f"# EMPIRE at {(meta.get('playtime_s') or 0) / 3600:.1f} game hours",
             f"Credits {player.get('money') or 0:,} Cr."]
    ships = catalog._ships(state)
    for st in catalog._stations(state):
        code = st.get("code")
        mods = st.get("modules") or []
        made = sorted({economics.product_of(m) for m in mods if economics.product_of(m)})
        counts = {w: strategy.built(st, w) for w in made}
        acct = st.get("account") or {}
        fill = executor.storage_fill(st)
        mined = {kind: sum(1 for s in ships if executor.serves(s, state) == (code, "mining")
                           and executor._miner_kind(s.get("macro")) == kind) for kind in ("solid", "liquid")}
        traders = sum(1 for s in ships if executor.serves(s, state) == (code, "trade"))
        top = sorted((st.get("cargo") or {}).items(), key=lambda kv: -kv[1])[:6]
        lines += ["", f"## {code}: {len(mods)} modules; production " +
                  (", ".join(f"{w} x{n}" for w, n in counts.items()) or "none"),
                  f"  dock {'yes' if catalog._has_dock(st) else 'no'}, manager {'yes' if st.get('manager') else 'no'}, "
                  f"account {int(acct.get('amount') or 0):,} Cr of {int(acct.get('min') or 0):,} minimum",
                  f"  stores " + ", ".join(f"{k} {v:.0%}" for k, v in fill.items()),
                  f"  holds " + ", ".join(f"{w} {n:,}" for w, n in top),
                  f"  works for it: solid miners {mined['solid']}, liquid miners {mined['liquid']}, traders {traders}"]
    lines += ["", "# ONE MORE MODULE, at the prices we know (build cost at average prices; "
                  "payback in game hours; demand and holdings in hours of one module's output)",
              "ware | margin/h | build | blueprint | payback | w/o blueprint | demand h | held h | inputs we buy"]
    # Only the module the bridge builds for each ware, not every race's.
    built_by_bridge = {macro for macro, _ in executor.EXPANSION_MODULES.values()}
    for row in economics.economics(state):
        if row["macro"] not in built_by_bridge:
            continue
        pay = f"{row['payback_hours']:.0f}" if row["payback_hours"] is not None else "never"
        own = f"{row['payback_hours_built']:.0f}" if row["payback_hours_built"] is not None else "-"
        buy = ", ".join(i["ware"] for i in row["inputs"] if not i["we_make"]) or "-"
        lines.append(f"{row['ware']} | {row['margin_per_hour']:,.0f} | {row['build_cost']:,} | "
                     f"{'held' if not row['blueprint'] else f'{row['blueprint']:,}'} | {pay} | {own} | "
                     f"{row['demand_hours']:.0f} | {row['held_hours']:.0f} | {buy}")
    lines += ["", "# BUILDABLE (wares and kinds the bridge can build, and whether we can get "
                  "the blueprint: the purchase job's own check of sellers, licences and standing)"]
    import purchases
    for w, (m, _) in executor.EXPANSION_MODULES.items():
        bp = (modules.get(m) or {}).get("ware")
        if bp in held_bp:
            lines.append(f"  {w}: blueprint held")
            continue
        pick, why = purchases.choose(bp, state, {}) if bp else (None, "no blueprint ware")
        lines.append(f"  {w}: " + (f"blueprint for sale by {pick['faction']}, "
                                    f"{(modules.get(m) or {}).get('maxprice') or 0:,} Cr" if pick
                                    else f"blueprint not obtainable now: {why}"))
    current = strategy.lines(state, data)
    if current:
        lines += ["", "# CURRENT PLAN AND PROGRESS"] + [f"  {line}" for line in current]
    return "\n".join(lines)


def to_strategy(answer: StrategistPlan) -> dict:
    """The model's lists as the plan's maps (schemas.Strategy), validated."""
    from schemas import Strategy
    return Strategy.model_validate({
        "horizon_hours": answer.horizon_hours,
        "rationale": answer.rationale,
        "stations": {p.station: {"build": {b.ware: b.modules for b in p.build},
                                 "miners": {m.kind: m.count for m in p.miners},
                                 "traders": p.traders} for p in answer.stations}}).model_dump()


def ask(state: dict, data: dict, model: str | None = None, guidelines: str = "") -> tuple[dict, str]:
    """One strategist call: (plan, usage line). Raises on refusal or a bad answer."""
    import anthropic
    model = model or STRATEGIST_MODEL
    user = f"# GUIDELINES\n{guidelines}\n\n{report(state, data)}" if guidelines else report(state, data)
    start = time.perf_counter()
    response = anthropic.Anthropic(timeout=600).messages.parse(
        model=model, max_tokens=16000, system=SYSTEM,
        messages=[{"role": "user", "content": user}], output_format=StrategistPlan)
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"{model} gave no plan (stop {response.stop_reason})")
    u = response.usage
    usage = (f"[strategist] {model}: {time.perf_counter() - start:.0f}s, in {u.input_tokens}, "
             f"out {u.output_tokens}, stop {response.stop_reason}")
    return to_strategy(response.parsed_output), usage


def update(state: dict, data: dict, guidelines: str = "") -> list[str]:
    """Ask for a plan when one is due and store it in memory. Report lines back."""
    import strategy
    # A plan file wins: the two writing one memory would undo each other.
    if not STRATEGIST_MODEL or strategy.STRATEGY_FILE or not due(data, state):
        return []
    try:
        plan, usage = ask(state, data, guidelines=guidelines)
    except Exception as exc:  # noqa: BLE001 - a failed call keeps the old plan
        return [f"strategist call failed: {type(exc).__name__}: {str(exc)[:200]}"]
    print(usage, flush=True)
    data["strategy"] = {"plan": plan, "since": (state.get("meta") or {}).get("playtime_s") or 0,
                        "source": f"model {STRATEGIST_MODEL}"}
    return []
