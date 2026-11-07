"""Send commands by hand to the running agent, on record (tasks/plan-2026-11.md, 0.5).

The host sends what is appended to logs/outbox.txt. Appended by hand, a command
left no trace in the run's own folder, and the next diagnosis missed it: on
2026-11-06 a hand `moveto` left a guard destroyer waiting by a hive while the
rules were blamed. This appends to the outbox and writes the same lines, with the
time and the reason, to hand.log in the newest run folder.

    py -3.14 hand.py --why "the nest is on the map now" "raid D cluster_13_sector001_macro go khaak"
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent
OUTBOX = REPO / "logs" / "outbox.txt"
RUNS = REPO / "out" / "experiments"


def send(commands: list[str], why: str, outbox: Path = OUTBOX, runs: Path = RUNS) -> Path | None:
    """Append `commands` to the outbox and to hand.log of the newest run; that log, if any."""
    commands = [c.strip() for c in commands if c.strip()]
    outbox.parent.mkdir(parents=True, exist_ok=True)
    with outbox.open("a", encoding="utf-8") as handle:
        handle.writelines(c + "\n" for c in commands)
    # Run folders start with their date; "seta-baseline-session" sorts after them all
    # and took start9r's first hand line.
    newest = max((d for d in runs.glob("*") if d.is_dir() and d.name[:8].isdigit()),
                 key=lambda d: d.name, default=None)
    if newest is None:
        return None
    log = newest / "hand.log"
    stamp = f"{datetime.now():%H:%M:%S}"
    with log.open("a", encoding="utf-8") as handle:
        handle.writelines(f"[{stamp}] {c}    # {why}\n" for c in commands)
    return log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--why", required=True, help="the reason, as it would go into a lesson")
    parser.add_argument("commands", nargs="+")
    args = parser.parse_args()
    log = send(args.commands, args.why)
    print(f"{len(args.commands)} sent" + (f", on record in {log}" if log else ", no run folder to record in"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
