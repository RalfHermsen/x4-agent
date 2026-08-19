"""Python side of the x4-agent bridge.

Runs inside the X4_Python_Pipe_Server host, which loads this module as soon as
X4 registers it through `md.Pipe_Server_Host.Register_Module`. The shape is
copied from `sn_mod_support_apis/python/Time_API.py`: blocking read, write a
response.

The host process is where the agent lives, because it is the process that owns
the pipe. So this module imports the repo and runs a full cycle: read the newest
save, build a sitrep, ask the planner, validate, and translate whatever survives
into commands the Mission Director understands.

Configuration through environment variables, set when launching the host:

    X4_AGENT_REPO      path to the repo (required to do anything but echo)
    X4_AGENT_MODE      "advise" (default) or "execute"
    X4_AGENT_INTERVAL  seconds between planning cycles, default 300
    X4_OLLAMA_URL      where Ollama lives

**Default is advise.** Nothing reaches the game unless you explicitly set
execute mode. A planning cycle takes around 15 seconds and blocks the read loop
while it runs, which is why it is throttled rather than run on every heartbeat.
"""

import os
import sys
import time

from X4_Python_Pipe_Server import Pipe_Server

PIPE_NAME = "x4_agent"

REPO = os.environ.get("X4_AGENT_REPO")
MODE = os.environ.get("X4_AGENT_MODE", "advise").lower()
INTERVAL = float(os.environ.get("X4_AGENT_INTERVAL", "300"))

_agent = None


def load_agent():
    """Import the repo lazily, so a broken setup still leaves the pipe working."""
    global _agent
    if _agent is not None or not REPO:
        return _agent
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    try:
        import agent
        _agent = agent
        print(f"[x4-agent] agent loaded from {REPO}, mode={MODE}, "
              f"interval={INTERVAL:.0f}s")
    except Exception as exc:  # noqa: BLE001 - never take the pipe down over this
        print(f"[x4-agent] could not load the agent from {REPO}: "
              f"{type(exc).__name__}: {exc}")
        _agent = False
    return _agent


def parse_state(message: str) -> dict:
    """'state money=200000 time=19.93' -> {'money': '200000', 'time': '19.93'}"""
    parts = message.split()
    if not parts or parts[0] != "state":
        return {}
    out = {}
    for item in parts[1:]:
        if "=" in item:
            key, _, value = item.partition("=")
            out[key] = value
    return out


def run_cycle(pipe) -> None:
    """Plan once, and send the commands if we are allowed to."""
    agent = load_agent()
    if not agent:
        return

    try:
        result = agent.cycle()
    except Exception as exc:  # noqa: BLE001 - a failed cycle must not kill the loop
        print(f"[x4-agent] cycle failed: {type(exc).__name__}: {exc}")
        return

    commands = result["commands"]
    print(f"[x4-agent] cycle done in {result['seconds']:.1f}s: "
          f"{len(result['valid'])} valid actions, {len(commands)} executable, "
          f"{len(result['rejected'])} rejected")

    if not commands:
        pipe.Write("agent: nothing to execute this cycle")
        return

    if MODE != "execute":
        print(f"[x4-agent] advise mode, NOT sending: {commands}")
        pipe.Write(f"agent (advice only): {'; '.join(commands)}")
        return

    for command in commands:
        print(f"[x4-agent] sending: {command}")
        pipe.Write(command)


def main(args):
    print(f"[x4-agent] bridge starting, pipe {PIPE_NAME}, mode {MODE}")
    if MODE == "execute":
        print("[x4-agent] EXECUTE MODE: validated commands will reach the game")
    load_agent()

    pipe = Pipe_Server(PIPE_NAME)
    pipe.Connect()
    print("[x4-agent] X4 connected")

    last_cycle = 0.0
    while 1:
        message = pipe.Read()
        # Log before filtering out pings. If you only ever see 'state' and never
        # 'ping', the read side is dead while the write side lives, and that
        # distinction is what makes this debuggable.
        print(f"[x4-agent] received: {message}")

        if message == "ping":
            # The Server_Reader pings until connected; no reply expected.
            continue

        # The game just wrote a savegame, so the state on disk is current. This
        # also fires for the player's own saves, which is a sensible moment to
        # replan anyway.
        if message == "saved":
            last_cycle = time.monotonic()
            run_cycle(pipe)
            continue

        if not parse_state(message):
            continue

        now = time.monotonic()
        if now - last_cycle < INTERVAL:
            continue

        # Ask for a fresh save rather than planning on a stale one. The cycle
        # runs when 'saved' comes back. Stamp the clock now so a failed save
        # does not cause a request every heartbeat.
        last_cycle = now
        print("[x4-agent] requesting a savegame before planning")
        pipe.Write("save")
