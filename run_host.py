"""Starts the pipe host, after stopping any host that is already running.

Only one process can own a named pipe. A host left over from an earlier session
holds `\\\\.\\pipe\\x4_python_host`, and the next one dies on startup with
"All pipe instances are busy" and no obvious link to the real cause. That
happened twice, and both times it looked like the agent had stopped working
rather than never having started.

Usage:
    python run_host.py                 # advise mode
    python run_host.py --execute       # orders actually reach the game
    python run_host.py --interval 300
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent
MODULE = "X4_Python_Pipe_Server.Main"


def running_hosts() -> list[int]:
    """PIDs of pipe hosts already running, ours or from an earlier session."""
    if sys.platform != "win32":
        return []
    query = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '*{MODULE}*' }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", query],
                         capture_output=True, text=True)
    return [int(line) for line in out.stdout.split() if line.strip().isdigit()
            if int(line) != os.getpid()]


def stop(pids: list[int]) -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Stop-Process -Id {','.join(map(str, pids))} -Force "
                    "-ErrorAction SilentlyContinue"], capture_output=True)
    time.sleep(1)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="let validated orders reach the game (default: advise only)")
    parser.add_argument("--interval", type=int, default=300,
                        help="seconds between planning cycles")
    parser.add_argument("--ollama", default=os.environ.get("X4_OLLAMA_URL"),
                        help="Ollama base URL")
    args = parser.parse_args()

    stale = running_hosts()
    if stale:
        print(f"stopping {len(stale)} host(s) still holding the pipe: {stale}")
        stop(stale)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "vendor")
    env["X4_AGENT_REPO"] = str(REPO)
    env["X4_AGENT_MODE"] = "execute" if args.execute else "advise"
    env["X4_AGENT_INTERVAL"] = str(args.interval)
    if args.ollama:
        env["X4_OLLAMA_URL"] = args.ollama

    print(f"mode={env['X4_AGENT_MODE']} interval={args.interval}s "
          f"ollama={env.get('X4_OLLAMA_URL', 'localhost')}")
    return subprocess.call([sys.executable, "-u", "-m", MODULE, "-v"], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
