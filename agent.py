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
import sys
from pathlib import Path

import executor
import memory
import planner
import sitrep as sitrep_mod
from save_parser import latest_save, parse_save


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
                              failures=failures)

    analysis, reason_s = planner.reason(
        report, planner.GUIDELINES.read_text(encoding="utf-8"), model)
    plan, extract_s = planner.extract(analysis, report, model)
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
