"""Start, load and stop X4 without a person at the keyboard.

X4Mcp (an X4Native extension, see tasks/plan-2026-10.md 2.0) is the hand on
the keyboard once the game runs: it loads saves and quits the game over HTTP on
127.0.0.1:7779. It cannot start the game, because it only exists once the game
does. This script does that part, and wraps the rest so a harness has one
command per step.

Usage:
    python launch_game.py                 # start X4, wait until X4Mcp answers
    python launch_game.py --load save_007 # load a save, wait until it is in
    python launch_game.py --status
    python launch_game.py --stop          # quit through the game, wait for exit

Every wait prints a line while it waits and gives up with a non-zero exit
after its timeout, so a harness never hangs silently.

The game is started through Steam's URL handler, which is what was proven to
work on 2026-10-18; Steam must be running. Stopping never kills the process:
a kill while the game writes a save corrupts that save, and the harness
depends on saves.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

APP_ID = "392160"
MCP = os.environ.get("X4_MCP_URL", "http://127.0.0.1:7779")
PROGRESS_EVERY = 15


def _health() -> bool:
    try:
        with urllib.request.urlopen(f"{MCP}/health", timeout=2) as response:
            return b'"ok"' in response.read()
    except (urllib.error.URLError, OSError):
        return False


def call(tool: str, arguments: dict | None = None, timeout: float = 60) -> str:
    """One MCP tools/call; returns the text, raises on a tool error."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments or {}}}).encode()
    request = urllib.request.Request(f"{MCP}/mcp", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        reply = json.loads(response.read())
    if "error" in reply:
        raise RuntimeError(f"{tool}: {reply['error'].get('message')}")
    result = reply["result"]
    text = " ".join(part.get("text", "") for part in result.get("content", []))
    if result.get("isError"):
        raise RuntimeError(f"{tool}: {text}")
    return text


def restore_window() -> bool:
    """Bring a minimized game window back; True if it was minimized.

    X4 stands still while minimized: no state messages, no saves, no game
    time. A catalog run lost 24 minutes that way on 2026-10-19, waiting for
    a save the game was not going to write.
    """
    if sys.platform != "win32":
        return False
    import ctypes
    user32 = ctypes.windll.user32
    window = user32.FindWindowW(None, "X4")
    if not window or not user32.IsIconic(window):
        return False
    user32.ShowWindow(window, 9)   # SW_RESTORE
    user32.SetForegroundWindow(window)
    return True


def running() -> bool:
    if sys.platform != "win32":
        return False
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq X4.exe", "/NH"],
                         capture_output=True, text=True)
    return "X4.exe" in out.stdout


def wait(what: str, done, timeout: float) -> bool:
    start = time.monotonic()
    last = start
    while not done():
        now = time.monotonic()
        if now - start > timeout:
            print(f"[launch] gave up waiting for {what} after {timeout:.0f}s")
            return False
        if now - last >= PROGRESS_EVERY:
            print(f"[launch] still waiting for {what} ({now - start:.0f}s)")
            last = now
        time.sleep(2)
    print(f"[launch] {what} after {time.monotonic() - start:.0f}s")
    return True


def launch(timeout: float) -> int:
    if _health():
        print("[launch] X4Mcp already answers, nothing to start")
        return 0
    if running():
        print("[launch] X4 is running but X4Mcp does not answer; see "
              "x4native/x4native.log in the X4 profile folder")
        return 2
    os.startfile(f"steam://rungameid/{APP_ID}")  # noqa: S606 - fixed URL, no input
    print("[launch] start requested through Steam")
    if not wait("X4Mcp to answer", _health, timeout):
        print("[launch] if X4 is running, the extension did not load: read "
              "x4native/x4native.log in the X4 profile folder")
        return 1
    return 0


def load(name: str, timeout: float) -> int:
    reply = call("load_game", {"name": name})
    print(f"[launch] load_game: {reply}")
    if not reply.startswith("ok"):
        return 1
    # The menu answers is_game_loaded=false while the save loads, so a short
    # settle before polling avoids reading the menu's answer as the result.
    time.sleep(5)
    loaded = lambda: _health() and call("is_game_loaded").strip() == "true"
    return 0 if wait(f"{name} to load", loaded, timeout) else 1


def stop(timeout: float) -> int:
    if not running():
        print("[launch] X4 is not running")
        return 0
    if _health():
        print(f"[launch] shutdown_game: {call('shutdown_game')}")
    else:
        print("[launch] X4Mcp does not answer; not killing the game, quit it by hand")
        return 1
    return 0 if wait("X4 to exit", lambda: not running(), timeout) else 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--load", metavar="SAVE")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()

    if args.status:
        up = _health()
        loaded = call("is_game_loaded").strip() if up else "unknown"
        print(f"X4 running: {running()}  X4Mcp: {'up' if up else 'down'}  "
              f"game loaded: {loaded}")
        return 0
    if args.stop:
        return stop(args.timeout)
    if args.load:
        if not _health():
            code = launch(args.timeout)
            if code:
                return code
        return load(args.load, args.timeout)
    return launch(args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
