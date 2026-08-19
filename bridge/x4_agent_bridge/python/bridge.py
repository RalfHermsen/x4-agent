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
    X4_AGENT_LOG       file to append each cycle to, default <repo>/logs/agent.log
    X4_OLLAMA_URL      where Ollama lives

**Default is advise.** Nothing reaches the game unless you explicitly set
execute mode. A planning cycle takes around 15 seconds and blocks the read loop
while it runs, which is why it is throttled rather than run on every heartbeat.

Where to watch it: opening the in-game logbook pauses the game, so it is a poor
place to follow the agent. Orders therefore also go to the message ticker, which
does not pause, and the full reasoning goes to the log file, which you can tail
on a second screen.
"""

import os
import sys
import time

from X4_Python_Pipe_Server import Pipe_Server

PIPE_NAME = "x4_agent"

REPO = os.environ.get("X4_AGENT_REPO")
MODE = os.environ.get("X4_AGENT_MODE", "advise").lower()
INTERVAL = float(os.environ.get("X4_AGENT_INTERVAL", "300"))
# Only ask the game for a fresh save if the newest one is older than this. Each
# autosave is tens of megabytes, and asking every cycle put enough pressure on
# the game (and on a synced folder) that saves started failing outright. A save
# a couple of minutes old is fine to plan on.
SAVE_MAX_AGE = float(os.environ.get("X4_AGENT_SAVE_MAX_AGE", "150"))
# Pause between two commands. Without it the pipe drops after the first one.
COMMAND_GAP = float(os.environ.get("X4_AGENT_COMMAND_GAP", "2"))
LOG_PATH = os.environ.get("X4_AGENT_LOG")

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


def log_file():
    if LOG_PATH:
        return LOG_PATH
    return os.path.join(REPO, "logs", "agent.log") if REPO else None


def log_cycle(agent, result) -> None:
    """Append the whole cycle to a file, for watching outside the game."""
    path = log_file()
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        header = "=" * 70
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        parts = [
            "", header, stamp, header,
            result["sitrep"], "",
            "# REASONING", result["analysis"], "",
            agent.render(result), "",
        ]
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(os.linesep.join(parts))
    except Exception as exc:  # noqa: BLE001 - logging must never break the loop
        print(f"[x4-agent] could not write the log: {type(exc).__name__}: {exc}")


def save_age() -> float | None:
    """Seconds since the newest finished savegame, or None if unknown."""
    agent = load_agent()
    if not agent:
        return None
    try:
        return time.time() - agent.latest_save().stat().st_mtime
    except Exception:  # noqa: BLE001 - a missing save must not break the loop
        return None


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

    log_cycle(agent, result)

    commands = result["commands"]
    print(f"[x4-agent] cycle done in {result['seconds']:.1f}s: "
          f"{len(result['valid'])} valid actions, {len(commands)} executable, "
          f"{len(result['rejected'])} rejected")

    if not commands:
        # Nothing to say. Writing "nothing happened" back would put a line in
        # the player's logbook every cycle, which is noise, not information.
        return

    if MODE != "execute":
        print(f"[x4-agent] advise mode, NOT sending: {commands}")
        return

    # Send one at a time, with a pause, and never let one failure swallow the
    # rest. Firing several commands back to back broke the connection: the log
    # showed the first command going out, then "Pipe client garbage collected,
    # restarting", and the remaining commands were simply lost. X4 processes a
    # command before reading the next one, and the matching loop on the game
    # side walks every ship and station, so the pipe is not ready again
    # immediately.
    for command in commands:
        print(f"[x4-agent] sending: {command}")
        try:
            pipe.Write(command)
        except Exception as exc:  # noqa: BLE001 - one lost command is not fatal
            print(f"[x4-agent] send failed for {command!r}: "
                  f"{type(exc).__name__}: {exc}")
            break
        time.sleep(COMMAND_GAP)


def main(args):
    print(f"[x4-agent] bridge starting, pipe {PIPE_NAME}, mode {MODE}")
    if MODE == "execute":
        print("[x4-agent] EXECUTE MODE: validated commands will reach the game")
    print(f"[x4-agent] cycle log: {log_file() or 'disabled'}")
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

        # Ask for a fresh save rather than planning on a stale one, but only if
        # what is on disk has actually gone stale. The cycle then runs when
        # 'saved' comes back. Stamp the clock now either way, so a failed save
        # does not turn into a request on every heartbeat.
        last_cycle = now
        age = save_age()
        if age is not None and age < SAVE_MAX_AGE:
            print(f"[x4-agent] newest save is {age:.0f}s old, planning on that")
            run_cycle(pipe)
            continue
        print("[x4-agent] requesting a savegame before planning")
        pipe.Write("save")
