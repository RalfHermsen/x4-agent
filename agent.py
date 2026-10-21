"""One full agent cycle: read state, plan, validate, translate to commands.

This ties the pieces together without knowing anything about pipes. The bridge
imports `cycle()` and sends whatever commands come out; running this file
directly does the same work and prints the result without touching the game,
which makes it testable without X4 running.

State still comes from the newest savegame. The live pipe currently carries only
capital and game time, which is not enough to plan on. That is the next thing to
close, and it is the reason the advice can lag behind a fast-moving game.

Usage:
    python agent.py                 # advise: plan and show, send nothing
    python agent.py --show-sitrep
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import action_lines
import catalog
import executor
import memory
import planner
import purchases
import sitrep as sitrep_mod
import standing
from save_parser import latest_save, parse_save
from schemas import PlannerResponse

# Longest the model may stay silent while nothing changes. Goals are written for
# "the next hours", so a quiet half hour costs nothing, and a forced run now and
# then catches whatever the fingerprint does not look at.
MAX_QUIET = float(os.environ.get("X4_AGENT_MAX_QUIET", "1800"))

# A scripted planner for in-game evals: a JSON file holding a list of planner
# responses, one per cycle, used instead of the two model calls. A test of an
# action in the running game must not depend on talking a model into
# proposing it. After the list runs out, cycles plan nothing.
SCRIPT = os.environ.get("X4_AGENT_SCRIPT")
# The action catalog (catalog.py, tasks/plan-catalog-2026-10.md): the model
# decides between prepared options instead of writing actions. Off unless set.
CATALOG = os.environ.get("X4_CATALOG") == "1"
# The rules-only arm of a measurement (plan-catalog 5.7): every Python rule
# runs, the model is never asked. What it adds is then what the model adds.
RULES_ONLY = os.environ.get("X4_RULES_ONLY") == "1"
# Leaves the station prices to the game's own managers. The rules-only run of
# 2026-10-20 earned 1.37 million per game hour against 1.77 to 1.88 for the
# game alone, bought nothing, and changed a price 214 times, about as often
# up as down; this arm measures whether the prices are the difference.
NO_PRICING = os.environ.get("X4_NO_PRICING") == "1"


def _scripted(remembered: dict) -> PlannerResponse:
    steps = json.loads(Path(SCRIPT).read_text(encoding="utf-8"))
    index = remembered.get("script_index", 0)
    remembered["script_index"] = index + 1
    if index < len(steps):
        return PlannerResponse.model_validate(steps[index])
    return PlannerResponse(assessment="Script finished.",
                           updated_goals=remembered.get("goals", []))


def _fingerprint(state: dict, failures: list[str], goals: list[str],
                 refused: list[dict]) -> str:
    """What the planner would see, reduced to what would change its mind.

    397 of 1,511 live cycles sent nothing at all, and most of them were the
    model re-reading an unchanged empire. Rounding is deliberate: stock moves
    every second, and a model call for every unit sold is the same waste.

    Stock is rounded to a tenth of what the station's trade offer asks for,
    because that is the number the offers are sized against; storage capacity
    is not parsed yet. Money to five percent, on a log scale, so a rich empire
    is not re-planned for pocket change.

    A refusal is news to the model, so the refused proposals count, but not
    how often: with the count in, a model that keeps re-proposing would never
    go quiet, and going quiet is the point.
    """
    ships, stations = [], []
    for a in state.get("assets", []):
        if (a.get("cls") or "").startswith("ship"):
            first = (a.get("orders") or [{}])[0]
            ships.append((a.get("code"), first.get("order"), first.get("state"),
                          (a.get("place") or {}).get("sector"), a.get("docked_at"),
                          json.dumps(a.get("attack") or {}, sort_keys=True)))
        elif a.get("cls") in ("station", "buildstorage"):
            for o in a.get("offers", []):
                want = o.get("desired") or 0
                level = round(10 * (o.get("amount") or 0) / want) if want else o.get("amount")
                stations.append((a.get("code"), o.get("ware"), o.get("side"), level))
            build = a.get("build") or {}
            stations.append((a.get("code"), "build", build.get("queued"),
                             build.get("in_progress")))
    money = state.get("player", {}).get("money") or 0
    snapshot = {
        "ships": sorted(map(list, ships)),
        "stations": sorted(map(list, stations), key=str),
        "money": int(math.log(money) / math.log(1.05)) if money > 0 else 0,
        "known_stations": len(state.get("known_stations", [])),
        "failures": sorted(failures),
        "goals": goals or [],
        "refused": sorted(r["proposal"] for r in refused or []),
    }
    return hashlib.sha1(json.dumps(snapshot, sort_keys=True, default=str)
                        .encode()).hexdigest()


def cycle(model: str | None = None, save: Path | None = None, force: bool = False,
          sends: bool = True) -> dict:
    """Run one full cycle. Returns everything the caller might want to log.

    `sends` says whether the caller will send the commands. The host passes
    False in advise mode; then the cycle plans as usual but remembers nothing
    of what it would have done (memory.DID_KEYS), and the panel says "would
    send" instead of "sent".
    """
    model = model or planner.DEFAULT_MODEL
    target = save or latest_save()

    state = parse_save(target)

    # What the agent remembers: goals it set itself last time, and whether the
    # commands it sent actually changed anything. Both go into the report, so
    # the model plans with continuity and can see its own failures.
    remembered = memory.load()
    before = copy.deepcopy(remembered)
    failures = memory.check(remembered, state)
    failures += memory.check_fleet(remembered, state, sitrep_mod.ship_type)
    failures += memory.track_expansions(remembered, state)
    failures += memory.game_refusals(remembered, state)
    failures += executor.transport_shortage(state)
    job_commands, job_lines = purchases.advance(remembered, state)
    failures += job_lines
    # When each explore order went out, in game time: the bridge's logbook line
    # appears only once the game has carried it out, and a save taken before
    # that showed the scout on seen ground again (executor._exploring_nothing).
    state["sent_at"] = remembered.get("sent_at", {})
    found = catalog.situations(state) if CATALOG else []
    report = sitrep_mod.build(state, goals=remembered.get("goals"),
                              failures=failures,
                              refused=remembered.get("refused"),
                              situations=catalog.render(found))

    # Skip the model when nothing it would look at has changed. The arithmetic
    # below (repricing, fleet focus) still runs: it is cheap, and prices move.
    fingerprint = _fingerprint(state, failures, remembered.get("goals"),
                               remembered.get("refused"))
    quiet_for = time.time() - remembered.get("last_model_run", 0)
    model_ran, quiet_reason = True, None
    if fingerprint == remembered.get("fingerprint") and quiet_for < MAX_QUIET and not force:
        model_ran = False
        quiet_reason = (f"nothing the planner looks at changed; last model run "
                        f"{quiet_for:.0f}s ago, forced after {MAX_QUIET:.0f}s")
    if RULES_ONLY:
        model_ran, quiet_reason = False, "rules only: the model is not asked (X4_RULES_ONLY)"

    if SCRIPT:
        model_ran, quiet_reason = True, None
        analysis, reason_s, extract_s = "scripted planner", 0.0, 0.0
        plan = _scripted(remembered)
    elif model_ran and CATALOG:
        analysis, reason_s = planner.reason(
            report, planner.GUIDELINES.read_text(encoding="utf-8"), model, catalog=True)
        chosen, notes, _ = catalog.decide(found, analysis)
        failures += notes
        plan = PlannerResponse(assessment=action_lines.summary_from(analysis) or "Decided.",
                               updated_goals=action_lines.goals_from(analysis), actions=[])
        extract_s = 0.0
        remembered["fingerprint"] = fingerprint
        remembered["last_model_run"] = time.time()
    elif model_ran:
        analysis, reason_s = planner.reason(
            report, planner.GUIDELINES.read_text(encoding="utf-8"), model)
        # The parser reads what it can; call 2 only gets the rest.
        plan, extract_s = planner.translate(analysis, report, model)
        remembered["fingerprint"] = fingerprint
        remembered["last_model_run"] = time.time()
    else:
        analysis, reason_s, extract_s = "", 0.0, 0.0
        plan = PlannerResponse(assessment=f"Model not run: {quiet_reason}.",
                               updated_goals=remembered.get("goals", []))
    ok, rejected = planner.check_actions(plan, state)
    jobs = [a for a in ok if a.type in executor.JOB_ACTIONS]
    ok = [a for a in ok if a.type not in executor.JOB_ACTIONS]
    commands, skipped = executor.to_commands(ok, state)
    # Options chosen from the catalog were checked when they were offered.
    commands += [c for c in (chosen if CATALOG and model_ran and not SCRIPT else []) if c not in commands]
    for action in jobs:
        if action.type == "sell_ship":
            first, reason = executor.plan_sale(action, state)
        elif action.type == "purchase":
            first, reason = executor.plan_ship_purchase(action, state)
        elif action.type == "haul":
            # Haul and loop are one command each; the ship stays its own,
            # nothing to track over cycles beyond the cargo in the next save.
            first, reason = executor.plan_haul(action, state, purchases.ships_in_use(remembered))
            if first and action.repeat:
                job_commands.append(first)
                first = f"loop {first.split()[1]}"
        else:
            first, reason = purchases.start(remembered, action.ware, state)
        if reason:
            skipped.append((action, reason))
        else:
            job_commands.append(first)

    # Repricing runs every cycle whether the model thought of it or not. Buyers
    # appear and are filled within minutes, so a price is only ever right for a
    # little while, and the model spent whole cycles on other things while stock
    # sold a third under the market. Anything the model did decide about a ware
    # wins: this only fills the silence.
    # Aim the trade fleet at whatever is crowding the warehouse, and hand the
    # ships back when nothing is. Deterministic for the same reason pricing is:
    # which ware takes the most room is a sum, not a judgement.
    commands += executor.focus_fleet(state)
    # A build that cannot pay stops buying. Topping it up is a sum.
    commands += executor.funding(state, remembered.setdefault("funded", {}))
    # A station making a ware itself should not also pay NPCs for it.
    commands += executor.own_production_buys(state)
    # A build waits for whoever brings its wares; one of ours brings them.
    commands += executor.feed_build_storages(state, remembered.setdefault("feeders", {}))
    # Settings and errands that are arithmetic, each sent once (standing.py).
    commands += standing.commands(state, remembered)

    # Explorers that are exploring the sector they are already in are reported,
    # not re-tasked. Sending them out automatically killed five scouts in an
    # afternoon: every one that actually went somewhere new was destroyed, and
    # the only survivor was the ship that never left its own sector.
    #
    # The mistake was treating it as arithmetic. Which ware fills a hold and
    # what a rival charges are sums. Whether to send an 80,000 Cr ship into
    # space nobody has surveyed is a question about risk, and risk is policy.
    _, exhausted = executor.restart_explorers(
        state, remembered.setdefault("explore_retried", {}), send=False)
    failures += exhausted

    priced = {c.rsplit(" ", 1)[0] for c in commands if c.startswith("price ")}
    commands += [c for c in ([] if NO_PRICING else executor.repricing(state))
                 if c.rsplit(" ", 1)[0] not in priced]

    # A ship on an errand belongs to its job until released: nothing else may
    # give it an order meanwhile, Python's own arithmetic included. A ship the
    # player reserved (3.8) gets nothing at all, and the refusal says why. Nor
    # does the ship the player sits in: an order flies it, and the player with
    # it, wherever the order goes. Hauls, sales and the standing rules already
    # skipped it; the model's own proposals did not.
    errand = purchases.ships_in_use(remembered)
    reserved = set(remembered.get("reserved", []))
    occupied = state.get("player", {}).get("occupied_ship")
    kept = []
    for c in commands:
        words = c.split()
        if len(words) > 1 and words[1] in reserved:
            failures.append(f"not sent, {words[1]} is reserved by the player: {c}")
            continue
        if len(words) > 1 and occupied and words[1] == occupied:
            failures.append(f"not sent, {words[1]} is the ship the player sits in: {c}")
            continue
        if not (len(words) > 1 and words[1] in errand):
            kept.append(c)
    commands = kept
    commands += job_commands

    commands, repeats = memory.drop_repeats(remembered, commands)

    remembered["goals"] = plan.updated_goals or remembered.get("goals", [])
    memory.record(remembered, commands)
    sent_at = remembered.setdefault("sent_at", {})
    for c in commands:
        if c.startswith("explore "):
            sent_at[c] = state.get("meta", {}).get("playtime_s", 0.0)
    memory.start_expansions(remembered, commands, state,
                            lambda ware: executor.EXPANSION_MODULES.get(ware, ("?", False))[0])
    if model_ran:
        # A silent cycle proposed nothing, so it refused nothing; recording
        # that would wipe what the model was last told.
        memory.record_refusals(remembered, rejected + skipped)
    if not sends:
        for key in memory.DID_KEYS:
            if key in before:
                remembered[key] = before[key]
            else:
                remembered.pop(key, None)
    memory.save(remembered)

    return {
        "panel": panel_lines(remembered, commands, failures, sent=sends),
        "save": target,
        "sitrep": report,
        "analysis": analysis,
        "plan": plan,
        "valid": ok,
        "rejected": rejected,
        "commands": commands,
        "repeats": repeats,
        "skipped": skipped,
        "failures": failures,
        "goals": remembered["goals"],
        "seconds": reason_s + extract_s,
        "model_ran": model_ran,
        "quiet_reason": quiet_reason,
    }


def panel_lines(remembered: dict, commands: list[str], failures: list[str],
                sent: bool = True) -> list[str]:
    """What the in-game panel shows after a cycle (3.9): at most 30 lines."""
    label = "sent" if sent else "would send"
    lines = [f"goal: {g}" for g in remembered.get("goals", [])[:3]]
    lines += [f"{label}: {c}" for c in commands[:12]]
    lines += [f"note: {f}" for f in failures[:12]]
    return [line[:120] for line in lines][:30]


def render(result: dict) -> str:
    lines = [f"# CYCLE ({result['seconds']:.1f}s, save {result['save'].name})", "",
             result["plan"].assessment, ""]

    lines.append(f"# COMMANDS TO SEND ({len(result['commands'])})")
    lines += [f"    {c}" for c in result["commands"]] or ["    none"]

    if result.get("repeats"):
        lines.append("")
        lines.append("# ALREADY SET (not re-sent)")
        lines += [f"    {c}" for c in result["repeats"]]

    if result["skipped"]:
        lines.append("")
        lines.append("# ADVICE ONLY (not executable yet)")
        for action, why in result["skipped"]:
            lines.append(f"    {action.type}: {why}")
            lines.append(f"        {action.rationale}")

    if result["rejected"]:
        lines.append("")
        lines.append("# REJECTED (semantic check)")
        for action, why in result["rejected"]:
            lines.append(f"    {action.type}: {why}")

    lines.append("")
    lines.append(f"executable vocabulary: {executor.describe()}")
    return "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", nargs="?")
    parser.add_argument("--model", default=planner.DEFAULT_MODEL)
    parser.add_argument("--show-sitrep", action="store_true")
    parser.add_argument("--show-reasoning", action="store_true")
    args = parser.parse_args()

    result = cycle(args.model, Path(args.save) if args.save else None)
    if args.show_sitrep:
        print(result["sitrep"], end="\n\n")
    if args.show_reasoning:
        print("# REASONING\n" + result["analysis"], end="\n\n")
    print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
