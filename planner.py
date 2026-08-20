"""Planner: sitrep plus guidelines to the local model, in two calls.

Why two calls (see docs/brief.md section 8.1):

With constrained decoding in a single call, the model has to reason and satisfy
the schema at the same time. Measured on 2026-08-19 that produced a silent
failure: the model returned three actions of type "hold" while every attached
rationale described a concrete thing to do. Valid JSON, wrong meaning. An
explicit instruction in the system prompt did not fix it, because under the
grammar constraint the model picks whichever branch demands nothing further.

So: call 1 reasons freely, call 2 turns that reasoning into the schema. The
second call no longer has to think, only to translate.

On top of that sits semantic validation: a schema-valid action can still refer
to a ship that does not exist, or to a station somebody else owns.

Usage:
    python planner.py --latest
    python planner.py --latest --show-reasoning
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

import executor
import sitrep as sitrep_mod
from save_parser import latest_save, parse_save
from schemas import PlannerResponse

# Point these at your own Ollama instance.
OLLAMA_URL = os.environ.get("X4_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("X4_PLANNER_MODEL", "gemma4:26b-a4b-it-qat")
GUIDELINES = Path(__file__).parent / "guidelines.md"

REASON_SYSTEM = """You are the strategic adviser to a player in X4: Foundations.

You are given guidelines and a situation report. Think out loud and arrive at at
most four concrete actions.

- Only name ships, stations and wares that appear literally in the situation
  report. Never invent a code, a ware or a sector.
- Do not do arithmetic; the numbers in the report are already computed.
- For each action, state which ship or station it concerns and which guideline
  justifies it.
- If there is nothing sensible to do, say so explicitly.
- Be concise.

End with one to three standing goals: what this empire is working towards over
the next hours, not this minute. They are carried into the next cycle, so write
them so a later you can tell whether they are done."""

EXTRACT_SYSTEM = """You convert a given analysis into structured actions. You add
nothing and drop nothing; you only translate.

Pick the fitting type per action. Each type needs exactly the fields listed and
nothing more:

- assign_ship    : ship code, station code, role (mine or trade). No ware, no
                   amount, no destination. The station manager works those out.
- set_behaviour  : ship code, behaviour (autotrade / automine / repeat_orders /
                   explore)
- expand_station : station code, ware the station should start producing
- set_budget     : station code, level (low / mid / high)
- set_trade_rule : station code, ware (or "all"), rule (own_faction_only /
                   open_market), side (buy / sell / both)
- set_price      : station code, ware, side (buy/sell), price in credits
- claim_ship     : target code
- purchase       : item, spec, max spend
- build_station  : station type, sector, max spend
- fleet_order    : fleet code, order
- hold           : nothing

Never drop an action because some detail is missing that its type does not ask
for. If the analysis says to assign a miner to a station, that is a complete
assign_ship action even though no ware is named.

Use `hold` only when the analysis says nothing should be done. Never describe an
intended action as `hold`.

Every reference field (ship_ref, station_id, fleet_id, target_id) must be an ID
code copied literally from the situation report, in the form AAA-123. Never a
role word such as "miner", "trader" or "scouts", and never a description. If the
analysis names no specific ship or station for an action, drop that action.

When the analysis describes an intent that fits more than one action type, pick
one the executor can actually carry out. Attaching a ship to one of our stations
so its manager directs it is `assign_ship`, not `set_behaviour`. Currently
executable: %s. The rest is recorded as advice.

Fill `updated_goals` with the standing goals the analysis ends on. If the report
already listed standing goals, carry forward the ones still worth pursuing and
drop the ones that are done. This is the only thing the agent remembers between
cycles, so an empty list throws that memory away."""


def _chat(model: str, messages: list[dict], schema: dict | None,
          temperature: float = 0.2, timeout: float = 600.0) -> tuple[str, float]:
    """One Ollama call. With a schema the output is grammar-constrained."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # Reasoning models (gemma4, qwen3) return empty content without this.
        "think": False,
        # guidelines.md is around 3.5k tokens and the sitrep grows with the
        # game. Ollama truncates silently on overflow, and what falls off the
        # front is exactly the guidelines.
        "options": {"temperature": temperature, "num_ctx": 16384},
    }
    if schema:
        payload["format"] = schema

    start = time.perf_counter()
    response = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    if response.status_code == 400 and "think" in response.text.lower():
        payload.pop("think")
        response = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    response.raise_for_status()

    content = response.json()["message"]["content"]
    if not content.strip():
        raise RuntimeError(f"{model} returned empty content")
    return content, time.perf_counter() - start


def reason(report: str, guidelines: str, model: str) -> tuple[str, float]:
    """Call 1: reason freely, no schema.

    Temperature 0 here too. Sampling made the agent act only sometimes: on an
    unchanged game state one run proposed attaching the trader to the station
    and the next proposed nothing executable at all. An agent that touches a
    live game should be boring and repeatable, so the variance buys nothing.
    """
    return _chat(model, [
        {"role": "system", "content": REASON_SYSTEM},
        {"role": "user", "content": f"# GUIDELINES\n{guidelines}\n\n{report}"},
    ], schema=None, temperature=0.0)


def extract(analysis: str, report: str, model: str) -> tuple[PlannerResponse, float]:
    """Call 2: turn the analysis into the schema.

    The prompt names the currently executable action types. That is information,
    not steering: the analysis is unchanged, only the mapping onto a type is
    guided, so an intent the body can perform does not land in a type it cannot.

    Temperature 0 here. This call translates, it does not invent, and sampling
    made the agent inconsistent: the same analysis landed on `assign_ship` one
    run and `set_behaviour(repeat_orders)` the next, so it acted only sometimes.
    """
    content, elapsed = _chat(model, [
        {"role": "system", "content": EXTRACT_SYSTEM % executor.describe()},
        {"role": "user", "content": f"{report}\n\n# ANALYSIS\n{analysis}"},
    ], schema=PlannerResponse.model_json_schema(), temperature=0.0)
    return PlannerResponse.model_validate_json(content), elapsed


# --------------------------------------------------------------------------- #
# semantic validation
# --------------------------------------------------------------------------- #

# Per action field: must the reference be something we own, or is "known" enough?
# "Does this object exist" is not sufficient. The model once proposed assigning
# our own trader to a station belonging to another faction: every reference
# existed, and it was still impossible to execute.
OWNED_FIELDS = ("ship_ref", "station_id", "fleet_id")
KNOWN_FIELDS = ("target_id",)   # claiming and boarding are about other people's things


def owned_refs(state: dict) -> set[str]:
    """Codes of our own ships and stations."""
    return {a["code"] for a in state["assets"] if a["code"]}


def known_refs(state: dict) -> set[str]:
    """Every code we know: our own property plus discovered stations."""
    return owned_refs(state) | {s["code"] for s in state["known_stations"]
                                if s["code"]}


def check_actions(plan: PlannerResponse, state: dict) -> tuple[list, list[tuple]]:
    """Split actions into executable and rejected.

    Two sieves, because schema-valid is not the same as sensible:
    1. does the named object exist?
    2. are you allowed to do this to it? Orders only apply to our own assets.

    In Phase 1 rejected actions are logged; from Phase 2 this is the last filter
    before anything reaches the game.
    """
    owned, known = owned_refs(state), known_refs(state)
    ok, rejected = [], []

    for action in plan.actions:
        problems = []
        for field in OWNED_FIELDS:
            value = getattr(action, field, None)
            if not value:
                continue
            if value not in known:
                problems.append(f"{field}={value} does not exist")
            elif value not in owned:
                problems.append(f"{field}={value} is not ours")
        for field in KNOWN_FIELDS:
            value = getattr(action, field, None)
            if value and value not in known:
                problems.append(f"{field}={value} does not exist")

        if problems:
            rejected.append((action, "; ".join(problems)))
        else:
            ok.append(action)
    return ok, rejected


def render(plan: PlannerResponse, ok: list, rejected: list[tuple],
           model: str, timings: tuple[float, float]) -> str:
    reason_s, extract_s = timings
    lines = [f"# ADVICE ({model}, {reason_s:.1f}s reasoning + "
             f"{extract_s:.1f}s structuring)", "",
             plan.assessment, ""]

    if not plan.actions:
        lines.append("No actions.")
    for action in ok:
        lines.append(f"[{action.priority.value}] {action.type}")
        detail = action.model_dump(exclude={"type", "priority", "rationale"})
        detail = {k: v for k, v in detail.items() if v not in (None, [], "")}
        if detail:
            lines.append(f"    {detail}")
        lines.append(f"    why: {action.rationale}")

    if rejected:
        lines.append("")
        lines.append("# REJECTED (semantic check)")
        for action, why in rejected:
            lines.append(f"    {action.type}: {why}")
            lines.append(f"    was: {action.rationale}")

    if plan.updated_goals:
        lines.append("")
        lines.append("# GOALS FOR THE NEXT CYCLE")
        lines += [f"    {goal}" for goal in plan.updated_goals]
    if plan.watch:
        lines.append("")
        lines.append("# WATCH")
        lines += [f"    {item}" for item in plan.watch]

    lines.append("")
    lines.append(f"confidence: {plan.confidence}")
    return "\n".join(lines)


def main() -> int:
    # The Windows console runs on cp1252; game names and model output are UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", nargs="?")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--show-sitrep", action="store_true")
    parser.add_argument("--show-reasoning", action="store_true")
    args = parser.parse_args()

    target = latest_save() if args.latest else Path(args.save)
    state = parse_save(target)
    report = sitrep_mod.build(state)
    if args.show_sitrep:
        print(report, end="\n\n")

    analysis, reason_s = reason(report, GUIDELINES.read_text(encoding="utf-8"),
                                args.model)
    if args.show_reasoning:
        print("# REASONING\n" + analysis, end="\n\n")

    plan, extract_s = extract(analysis, report, args.model)
    ok, rejected = check_actions(plan, state)
    print(render(plan, ok, rejected, args.model, (reason_s, extract_s)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
