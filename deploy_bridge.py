"""Copies the bridge extension from this repo into the X4 installation.

The repo is the source of truth; the game folder is a deploy target. That keeps
the MD and Lua side in version control, and surviving a reinstall of X4 becomes
a matter of running this again.

Usage:
    python deploy_bridge.py            # copy, and show what happened
    python deploy_bridge.py --remove   # take the extension back out
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from gamedata import X4_DIR

SOURCE = Path(__file__).parent / "bridge" / "x4_agent_bridge"
TARGET = X4_DIR / "extensions" / "x4_agent_bridge"


def check_lowercase(root: Path) -> list[str]:
    """X4 ignores files in md/ that contain uppercase, without any message."""
    md = root / "md"
    if not md.exists():
        return []
    return [p.name for p in md.iterdir() if p.name != p.name.lower()]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()

    if args.remove:
        if TARGET.exists():
            shutil.rmtree(TARGET)
            print(f"removed: {TARGET}")
        else:
            print("nothing to remove")
        return 0

    bad = check_lowercase(SOURCE)
    if bad:
        print(f"ERROR: uppercase in md/: {', '.join(bad)}", file=sys.stderr)
        return 1

    if TARGET.exists():
        shutil.rmtree(TARGET)
    # __pycache__ does not belong in the game folder; the host imports the .py.
    shutil.copytree(SOURCE, TARGET,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    print(f"deployed to {TARGET}")
    for path in sorted(TARGET.rglob("*")):
        if path.is_file():
            print(f"   {path.relative_to(TARGET)}")

    print("\nRemember: the pipe host only loads Python modules from extensions")
    print("listed in vendor/X4_Python_Pipe_Server/permissions.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
