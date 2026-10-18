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

# A model named "openai:<name>" goes to an OpenAI-compatible endpoint instead
# (LiteLLM, Groq, OpenAI itself), so a hosted model can be measured against the
# local one on the same saves. Reasoning models there take an effort hint.
OPENAI_URL = os.environ.get("X4_OPENAI_URL", "http://localhost:4000/v1")
OPENAI_KEY = os.environ.get("X4_OPENAI_KEY", "")
REASONING_EFFORT = os.environ.get("X4_REASONING_EFFORT", "medium")

# The translation step may run on a different model from the reasoning step.
# It only copies a list into a schema, and the local setup for that is measured
# (docs/contracts.md); the reasoning step is where a bigger model might earn
# its keep. Unset, both calls use the same model, as before.
EXTRACT_MODEL = os.environ.get("X4_EXTRACT_MODEL")

REASON_SYSTEM = """You are the strategic adviser to a player in X4: Foundations.

You are given guidelines and a situation report. Think out loud and arrive at at
most four concrete actions.

- Only name ships, stations and wares that appear literally in the situation
  report. Never invent a code, a ware or a sector.
- Do not do arithmetic; the numbers in the report are already computed.
- For each action, state which ship or station it concerns and which guideline
  justifies it.
- If there is nothing sensible to do, say so explicitly.
- A proposal listed under NOT DONE LAST CYCLE was refused. Do not propose it
  again unless what it was refused for has changed.
- Be concise.

Write the actions as a numbered list under the heading ACTIONS, one line each,
and number them from 1. If there is nothing to do, write "ACTIONS: none".

End with one to three standing goals: what this empire is working towards over
the next hours, not this minute. They are carried into the next cycle, so write
them so a later you can tell whether they are done."""

EXTRACT_SYSTEM = """You convert a given analysis into structured actions. You add
nothing and drop nothing; you only translate.

Pick the fitting type per action. Each type needs exactly the fields listed and
nothing more:

- assign_ship    : ship code, commander code, role. Under one of our stations: mine,
                   trade, defend or buildstorage (supplies the station's build).
                   Under one of our ships: attack, intercept, defend or assist
                   (assist copies the leader's default order). No ware, no amount.
- set_behaviour  : ship code, behaviour (autotrade / automine / repeat_orders /
                   explore)
- expand_station : station code, ware the station should start producing, or
                   habitation to house a workforce
- set_budget     : station code, level (low / mid / high)
- set_trade_rule : station code, ware (or "all"), rule (own_faction_only /
                   open_market), side (buy / sell / both)
- set_price      : station code, ware, side (buy/sell), price in credits
- haul           : ware, from_station (a seller's code from the report), to_station
                   (our station), amount, repeat (true for a standing loop). The
                   ship and the price cap are worked out for you.
- sell_ship      : ship code of ours to sell (a claimed ship we do not need). The
                   shipyard is worked out for you.
- buy_blueprint  : ware, the module blueprint id exactly as the report names it
                   (module_...). Where and with which ship is worked out for you.
- claim_ship     : target code
- purchase       : item, spec, max spend
- build_station  : station type, sector, max spend
- fleet_order    : fleet code, order
- hold           : nothing

You are given a numbered list of decisions and nothing else. Translate the list
and only the list, in the same order.

Never fewer: an action you find hard to type is still an action, and dropping it
silently throws away a decision somebody already made. Never anything that is
not in the list, however sensible it looks.

One numbered point usually becomes one action, but not always: a point naming
two ships is two actions, one per ship. Count decisions, not line numbers.

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
    """One model call. With a schema the output is grammar-constrained."""
    if model.startswith("openai:"):
        return _chat_openai(model[len("openai:"):], messages, schema,
                            temperature, timeout)
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


def _chat_openai(model: str, messages: list[dict], schema: dict | None,
                 temperature: float, timeout: float) -> tuple[str, float]:
    """The same call against an OpenAI-compatible endpoint.

    The schema goes through `response_format`. Whether the server enforces it
    as strictly as Ollama's grammar does depends on the server, which is why
    the translation step is best kept local (X4_EXTRACT_MODEL).
    """
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "reasoning_effort": REASONING_EFFORT,
    }
    if schema:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "PlannerResponse", "schema": schema},
        }
    headers = {"Authorization": f"Bearer {OPENAI_KEY}"} if OPENAI_KEY else {}

    start = time.perf_counter()
    response = httpx.post(f"{OPENAI_URL}/chat/completions", json=payload,
                          headers=headers, timeout=timeout)
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"] or ""
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


ACTIONS_HEADING = "ACTIONS"


def _decisions(analysis: str) -> str:
    """The part of the analysis that says what to do, plus the standing goals.

    The reasoning step is asked to end in a numbered list under ACTIONS, and
    when it does, that list is the entire input to the translation step. If the
    heading is missing the whole analysis is passed instead: a heading the model
    forgot must not silently cost a cycle.
    """
    if ACTIONS_HEADING not in analysis:
        return analysis
    _, _, tail = analysis.partition(ACTIONS_HEADING)
    goals = ""
    for marker in ("STANDING GOALS", "GOALS"):
        if marker in tail:
            tail, _, rest = tail.partition(marker)
            goals = f"\n\nSTANDING GOALS\n{rest}"
            break
    return f"{ACTIONS_HEADING}{tail}{goals}"


def extract(analysis: str, report: str, model: str) -> tuple[PlannerResponse, float]:
    """Call 2: turn the analysis into the schema.

    The prompt names the currently executable action types. That is information,
    not steering: the analysis is unchanged, only the mapping onto a type is
    guided, so an intent the body can perform does not land in a type it cannot.

    Temperature 0 here. This call translates, it does not invent, and sampling
    made the agent inconsistent: the same analysis landed on `assign_ship` one
    run and `set_behaviour(repeat_orders)` the next, so it acted only sometimes.
    """
    model = EXTRACT_MODEL or model
    content, elapsed = _chat(model, [
        {"role": "system", "content": EXTRACT_SYSTEM % executor.describe()},
        {"role": "user", "content": _decisions(analysis)},
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
