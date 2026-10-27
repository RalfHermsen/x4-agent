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
# What one plan may add, on top of what stands. In leanstrat-long the plans
# restated totals that grew every horizon and bought nine ships; a plan says
# what to add now, and more than this is cut to it (`to_strategy`).
MODULES_PER_WARE = 2
MODULES_PER_STATION = 4
SHIPS_PER_KIND = 1          # miners of one kind, or traders, per station
HISTORY = 4                 # earlier plans shown with what followed them


class BuildTarget(BaseModel):
    ware: str = Field(description="A ware the bridge can build (see BUILDABLE), or storage_solid, "
                                  "storage_container, dock, habitation_<race>")
    add: int = Field(description=f"How many modules of it to add on top of those standing, at most "
                                 f"{MODULES_PER_WARE}; {MODULES_PER_STATION} at one station in all")


class MinerTarget(BaseModel):
    kind: Literal["solid", "liquid"]
    add: int = Field(description=f"How many miners of this kind to add for the station, 0 to {SHIPS_PER_KIND}")


class StationPlan(BaseModel):
    station: str = Field(description="Station code, e.g. KYV-745")
    build: list[BuildTarget]
    miners: list[MinerTarget]
    traders_add: int = Field(description=f"How many freighters to add for the station, 0 to {SHIPS_PER_KIND}")


class StrategistPlan(BaseModel):
    # First, so the reasoning comes before the numbers: last, it came back "x".
    rationale: str = Field(description="Why this plan, in three to six sentences: what the market "
                                       "lacks, what we can supply, what it costs and when it pays back")
    horizon_hours: float = Field(description="Game hours the plan is for, 2 to 6")
    stations: list[StationPlan]


SYSTEM = f"""You are the strategist of an X4: Foundations empire that is played by
deterministic rules. Without a plan the rules grow each station by the best
margin they know. Every few game hours you say what each station should add
over the next few game hours: production modules of which ware, and miners or
traders only where a station visibly lacks them. A plan goes first while it is
unmet; then the margins decide again. The rules buy a planned module's
blueprint, refuse what cannot be built (no blueprint for sale, no room on the
plot, not enough money), and never sell or demolish anything. One plan adds
at most {MODULES_PER_WARE} modules of a ware and {MODULES_PER_STATION} at a station,
and at most {SHIPS_PER_KIND} miner of each kind and {SHIPS_PER_KIND} trader per
station; more is cut to that. Adding nothing is a valid plan.

What experience and our own runs say:
* In our runs the rules with no plan grew net worth by about 2.3 M per game
  hour; plans that set growing totals and bought nine ships got 1.2. Your
  earlier plans and what followed them are in the report: where they did not
  pay, change course or add less.
* Build only where the market has a hole. A station built for profit alone
  saturates its market and then cannot sell. "demand h" adds up other
  stations' buy offers, which is the room in their stores, not what they take;
  WHAT CHANGED HANDS shows what buyers took and at what price. Trust it over
  demand h, and check what we already hold before adding a module.
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


def _working(state: dict, code: str) -> dict[str, int]:
    """Solid and liquid miners and traders working for a station."""
    import catalog
    import executor
    ships = catalog._ships(state)
    out = {kind: sum(1 for s in ships if executor.serves(s, state) == (code, "mining")
                     and executor._miner_kind(s.get("macro")) == kind) for kind in ("solid", "liquid")}
    out["traders"] = sum(1 for s in ships if executor.serves(s, state) == (code, "trade"))
    return out


def _outcome(state: dict) -> dict:
    """The scorecard figures a plan is judged by afterwards."""
    import score
    card = score.score(state)
    return {k: card[k] for k in ("game_hours", "net_worth_cost", "credits", "accounts", "stock_min",
                                 "modules_cost")}


def _earlier(data: dict) -> list[str]:
    """Earlier plans, how far each got, and what the empire did while it held."""
    out = []
    for h in data.get("strategy_history") or []:
        a, b = h["start"], h["end"]
        hours = max(b["game_hours"] - a["game_hours"], 0.01)

        def rate(key: str) -> str:
            return f"{(b[key] - a[key]) / hours / 1e6:+.2f}"
        out += [f"  set at {a['game_hours']:.1f} h, held {hours:.1f} h: net worth {rate('net_worth_cost')} M/h "
                f"(credits {rate('credits')}, station accounts {rate('accounts')}, stock {rate('stock_min')}, "
                f"modules {rate('modules_cost')})",
                f"    why: {h['rationale'][:400]}"] + [f"    {p}" for p in h["progress"]]
    return out


def _changed_hands(state: dict) -> list[str]:
    """What our stations sold to and bought from others, per game hour of the
    span the save's trade log covers (save_parser._trade_book)."""
    book = state.get("trades") or {}
    span = ((book.get("until") or 0) - (book.get("since") or 0)) / 3600
    if span <= 0:
        return []
    out = []
    for code, wares in sorted((book.get("stations") or {}).items()):
        for ware, e in sorted(wares.items(), key=lambda kv: -(kv[1]["sold_cr"] + kv[1]["bought_cr"]))[:10]:
            parts = [f"sold {e['sold'] / span:,.0f}/h at {e['sold_cr'] / e['sold']:,.0f}" if e["sold"] else "",
                     f"bought {e['bought'] / span:,.0f}/h at {e['bought_cr'] / e['bought']:,.0f}" if e["bought"] else ""]
            out.append(f"  {code} {ware}: " + ", ".join(p for p in parts if p))
    return [f"# WHAT CHANGED HANDS over the last {span:.0f} game hours (the save's trade log: our stations "
            "with other factions, units per game hour at the average price)"] + out


def report(state: dict, data: dict) -> str:
    """What the strategist plans on: stations, fleets, economics, what sold,
    earlier plans and what followed, the plan so far."""
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
    for st in catalog._stations(state):
        code = st.get("code")
        mods = st.get("modules") or []
        made = sorted({economics.product_of(m) for m in mods if economics.product_of(m)})
        counts = {w: strategy.built(st, w) for w in made}
        acct = st.get("account") or {}
        fill = executor.storage_fill(st)
        work = _working(state, code)
        top = sorted((st.get("cargo") or {}).items(), key=lambda kv: -kv[1])[:6]
        lines += ["", f"## {code}: {len(mods)} modules; production " +
                  (", ".join(f"{w} x{n}" for w, n in counts.items()) or "none"),
                  f"  dock {'yes' if catalog._has_dock(st) else 'no'}, manager {'yes' if st.get('manager') else 'no'}, "
                  f"account {int(acct.get('amount') or 0):,} Cr of {int(acct.get('min') or 0):,} minimum",
                  f"  stores " + ", ".join(f"{k} {v:.0%}" for k, v in fill.items()),
                  f"  holds " + ", ".join(f"{w} {n:,}" for w, n in top),
                  f"  works for it: solid miners {work['solid']}, liquid miners {work['liquid']}, "
                  f"traders {work['traders']}"]
    orders = state.get("ships_on_order") or []
    if orders:
        lines.append(f"Ships paid for and not delivered: {len(orders)}, "
                     f"{sum(o.get('paid') or 0 for o in orders):,} Cr, at " +
                     ", ".join(sorted({o['wharf'] or '?' for o in orders})))
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
    sold = _changed_hands(state)
    if sold:
        lines += [""] + sold
    earlier = _earlier(data)
    if earlier:
        lines += ["", "# YOUR EARLIER PLANS AND WHAT FOLLOWED (per game hour while each held; net worth is "
                      "money, station accounts, stock at minimum prices and modules at build cost, no ships)"] + earlier
    current = strategy.lines(state, data)
    if current:
        lines += ["", "# CURRENT PLAN AND PROGRESS"] + [f"  {line}" for line in current]
    return "\n".join(lines)


def to_strategy(answer: StrategistPlan, state: dict) -> dict:
    """The model's additions as the plan's totals (schemas.Strategy), validated:
    what stands now plus what it adds, cut to MODULES_PER_WARE,
    MODULES_PER_STATION and SHIPS_PER_KIND."""
    import catalog
    import strategy
    from schemas import Strategy
    stations = {st.get("code"): st for st in catalog._stations(state)}
    goals = {}
    for p in answer.stations:
        st, room = stations.get(p.station) or {}, MODULES_PER_STATION
        build = {}
        for b in p.build:
            add = max(0, min(b.add, MODULES_PER_WARE, room))
            room -= add
            build[b.ware] = strategy.built(st, b.ware) + add
        work = _working(state, p.station)
        goals[p.station] = {"build": build,
                            "miners": {m.kind: work[m.kind] + max(0, min(m.add, SHIPS_PER_KIND)) for m in p.miners},
                            "traders": work["traders"] + max(0, min(p.traders_add, SHIPS_PER_KIND))}
    return Strategy.model_validate({"horizon_hours": answer.horizon_hours, "rationale": answer.rationale,
                                    "stations": goals}).model_dump()


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
    return to_strategy(response.parsed_output, state), usage


def update(state: dict, data: dict, guidelines: str = "") -> list[str]:
    """Ask for a plan when one is due and store it in memory. Report lines back."""
    import strategy
    # A plan file wins: the two writing one memory would undo each other.
    if not STRATEGIST_MODEL or strategy.STRATEGY_FILE or not due(data, state):
        return []
    # The plan that ends goes into the history with how far it got and what
    # the empire did while it held, so the report for the next one shows it.
    now, old = _outcome(state), data.get("strategy") or {}
    history = list(data.get("strategy_history") or [])
    if old.get("plan") and old.get("start"):
        history = (history + [{"rationale": old["plan"].get("rationale") or "",
                               "progress": strategy.lines(state, data)[1:],
                               "start": old["start"], "end": now}])[-HISTORY:]
    try:
        plan, usage = ask(state, {**data, "strategy": None, "strategy_history": history}, guidelines=guidelines)
    except Exception as exc:  # noqa: BLE001 - a failed call keeps the old plan
        return [f"strategist call failed: {type(exc).__name__}: {str(exc)[:200]}"]
    print(usage, flush=True)
    data["strategy_history"] = history
    data["strategy"] = {"plan": plan, "since": (state.get("meta") or {}).get("playtime_s") or 0,
                        "source": f"model {STRATEGIST_MODEL}", "start": now}
    return []
