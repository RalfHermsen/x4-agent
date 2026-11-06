"""One cycle on a save, sending nothing: what a run started from it would do first.

tasks/plan-2026-11.md, 0.1. start9k's first cycle assigned the guard of 30 home
because its leader was no longer recognised, and that was seen only after the
restart. experiment.py runs this before every run and does not start one whose
first cycle trips a check of invariants.py; by hand:

    py -3.14 dryrun.py <save.xml.gz> [--memory <memory.json>] [--out <report.txt>]

The memory is a copy (empty when none is given, as a new run's is today); the
environment's X4_RULES_ONLY and X4_STRATEGY_FILE apply as in a run. Exit code 3
when a check names something, 0 otherwise.
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("save", type=Path)
    parser.add_argument("--memory", type=Path, help="the memory to start from; a copy is used")
    parser.add_argument("--out", type=Path, help="write the report here as well")
    args = parser.parse_args()
    store = Path(tempfile.mkdtemp(prefix="x4-dryrun-")) / "memory.json"
    if args.memory and args.memory.exists():
        shutil.copy(args.memory, store)
    # Before the import: memory binds its store then.
    os.environ["X4_AGENT_MEMORY"] = str(store)
    os.environ.setdefault("X4_RULES_ONLY", "1")
    import agent
    result = agent.cycle(save=args.save, sends=False)
    found = [f for f in result["failures"] if f.startswith("INVARIANT:")]
    claimed = [f for f in result["failures"] if f.startswith("CLAIMED:")]
    report = (agent.render(result) + "\n\n# CHECKS (invariants.py)\n" + ("\n".join(found) or "    none")
              + "\n\n# ORDERS DROPPED, THE SHIP ANOTHER RULE'S (standing.commands)\n"
              + ("\n".join(claimed) or "    none"))
    print(report)
    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
    shutil.rmtree(store.parent, ignore_errors=True)
    return 3 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
