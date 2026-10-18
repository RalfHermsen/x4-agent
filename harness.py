"""Prove a bridge verb inside the running game, without a person.

One run: the verb goes out through logs/outbox.txt, then `savegame` writes
the agent's own slot (save_008, never any other), and the fresh save is
searched for the logbook lines the bridge wrote. The evidence is what the
game recorded, not what was sent (tasks/lessons.md L15).

Needs the game running with a save loaded (launch_game.py --load ...) and
the host relaying without planning (run_host.py --no-plan). Never runs in
execute mode: the only commands that reach the game are the ones given here.

Usage:
    python harness.py "price KYV-745 sunriseflowers sell 112"
    python harness.py                       # just save and show the logbook
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
import time
from pathlib import Path

from save_parser import documents_dir

REPO = Path(__file__).parent
OUTBOX = REPO / "logs" / "outbox.txt"
AGENT_SLOT = "save_008"           # keep in step with AGENT_SLOT in x4agent.lua
LOGBOOK = re.compile(r'<entry time="([0-9.]+)"[^>]*text="(\[x4-agent[^"]*)"')


def slot_path() -> Path:
    root = documents_dir() / "Egosoft" / "X4"
    found = sorted(root.glob(f"*/save/{AGENT_SLOT}.xml.gz"))
    if not found:
        raise SystemExit(f"no {AGENT_SLOT} in {root}")
    return found[0]


def send(commands: list[str]) -> None:
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    with OUTBOX.open("a", encoding="utf-8") as handle:
        for command in commands:
            handle.write(command + "\n")


def wait_for_save(path: Path, after: float, timeout: float) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        # The game writes temp_save first and renames, so a changed mtime on
        # the slot means the save is complete.
        if path.exists() and path.stat().st_mtime > after:
            return True
        if int(time.monotonic() - start) % 15 == 0:
            print(f"[harness] waiting for {path.name} ({time.monotonic() - start:.0f}s)")
        time.sleep(1)
    return False


def logbook(path: Path) -> list[tuple[float, str]]:
    """Every [x4-agent] logbook line in a save as (game time, text)."""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        return [(float(m.group(1)), m.group(2))
                for line in handle for m in LOGBOOK.finditer(line)]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="*", help="bridge commands to send first")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--baseline", type=Path,
                        help="the save that was loaded; its logbook lines are not new")
    args = parser.parse_args()

    path = slot_path()
    # New is judged by (game time, text) pairs absent from the slot's previous
    # contents. Not by time alone: the slot may hold a different game further
    # along than the one loaded. Not by text alone: a verb that writes the same
    # line twice must show twice.
    seen = set(logbook(path)) if path.exists() else set()
    if args.baseline:
        seen |= set(logbook(args.baseline))
    before = path.stat().st_mtime if path.exists() else 0
    send(args.command + ["savegame"])
    print(f"[harness] queued: {args.command + ['savegame']}")
    if not wait_for_save(path, before, args.timeout):
        print(f"[harness] {path.name} was not written within {args.timeout:.0f}s; "
              "is the host running with --no-plan and the game loaded?")
        return 1
    new = [(t, text) for t, text in logbook(path) if (t, text) not in seen]
    print(f"[harness] {path.name} written; {len(new)} new logbook line(s):")
    for t, text in new:
        print(f"    {t:>10.1f}  {text}")
    return 0 if new else 1


if __name__ == "__main__":
    raise SystemExit(main())
