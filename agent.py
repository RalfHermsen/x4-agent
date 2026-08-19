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
import planner
import sitrep as sitrep_mod
from save_parser import latest_save, parse_save


def cycle(model: str | None = None, save: Path | None = None) -> dict:
    """Run one full cycle. Returns everything the caller might want to log."""
    model = model or planner.DEFAULT_MODEL
    target = save or latest_save()

    state = parse_save(target)
    report = sitrep_mod.build(state)

    analysis, reason_s = planner.reason(
        report, planner.GUIDELINES.read_text(encoding="utf-8"), model)
    plan, extract_s = planner.extract(analysis, report, model)
    ok, rejected = planner.check_actions(plan, state)
    commands, skipped = executor.to_commands(ok)

    return {
        "save": target,
        "sitrep": report,
        "analysis": analysis,
        "plan": plan,
        "valid": ok,
        "rejected": rejected,
        "commands": commands,
        "skipped": skipped,
        "seconds": reason_s + extract_s,
    }


def render(result: dict) -> str:
    lines = [f"# CYCLE ({result['seconds']:.1f}s, save {result['save'].name})", "",
             result["plan"].assessment, ""]

    lines.append(f"# COMMANDS TO SEND ({len(result['commands'])})")
    lines += [f"    {c}" for c in result["commands"]] or ["    none"]

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
