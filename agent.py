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
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import executor
import memory
import planner
import sitrep as sitrep_mod
from save_parser import latest_save, parse_save
from schemas import PlannerResponse

# Longest the model may stay silent while nothing changes. Goals are written for
# "the next hours", so a quiet half hour costs nothing, and a forced run now and
# then catches whatever the fingerprint does not look at.
MAX_QUIET = float(os.environ.get("X4_AGENT_MAX_QUIET", "1800"))


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


def cycle(model: str | None = None, save: Path | None = None) -> dict:
    """Run one full cycle. Returns everything the caller might want to log."""
    model = model or planner.DEFAULT_MODEL
    target = save or latest_save()

    state = parse_save(target)

    # What the agent remembers: goals it set itself last time, and whether the
    # commands it sent actually changed anything. Both go into the report, so
    # the model plans with continuity and can see its own failures.
    remembered = memory.load()
    failures = memory.check(remembered, state)
    failures += memory.check_fleet(remembered, state, sitrep_mod.ship_type)
    report = sitrep_mod.build(state, goals=remembered.get("goals"),
                              failures=failures,
                              refused=remembered.get("refused"))

    # Skip the model when nothing it would look at has changed. The arithmetic
    # below (repricing, fleet focus) still runs: it is cheap, and prices move.
    fingerprint = _fingerprint(state, failures, remembered.get("goals"),
                               remembered.get("refused"))
    quiet_for = time.time() - remembered.get("last_model_run", 0)
    model_ran, quiet_reason = True, None
    if fingerprint == remembered.get("fingerprint") and quiet_for < MAX_QUIET:
        model_ran = False
        quiet_reason = (f"nothing the planner looks at changed; last model run "
                        f"{quiet_for:.0f}s ago, forced after {MAX_QUIET:.0f}s")

    if model_ran:
        analysis, reason_s = planner.reason(
            report, planner.GUIDELINES.read_text(encoding="utf-8"), model)
        plan, extract_s = planner.extract(analysis, report, model)
        remembered["fingerprint"] = fingerprint
        remembered["last_model_run"] = time.time()
    else:
        analysis, reason_s, extract_s = "", 0.0, 0.0
        plan = PlannerResponse(assessment=f"Model not run: {quiet_reason}.",
                               updated_goals=remembered.get("goals", []))
    ok, rejected = planner.check_actions(plan, state)
    commands, skipped = executor.to_commands(ok, state)

    # Repricing runs every cycle whether the model thought of it or not. Buyers
    # appear and are filled within minutes, so a price is only ever right for a
    # little while, and the model spent whole cycles on other things while stock
    # sold a third under the market. Anything the model did decide about a ware
    # wins: this only fills the silence.
    # Aim the trade fleet at whatever is crowding the warehouse, and hand the
    # ships back when nothing is. Deterministic for the same reason pricing is:
    # which ware takes the most room is a sum, not a judgement.
    commands += executor.focus_fleet(state)

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
    commands += [c for c in executor.repricing(state)
                 if c.rsplit(" ", 1)[0] not in priced]

    commands, repeats = memory.drop_repeats(remembered, commands)

    remembered["goals"] = plan.updated_goals or remembered.get("goals", [])
    memory.record(remembered, commands)
    if model_ran:
        # A silent cycle proposed nothing, so it refused nothing; recording
        # that would wipe what the model was last told.
        memory.record_refusals(remembered, rejected + skipped)
    memory.save(remembered)

    return {
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
