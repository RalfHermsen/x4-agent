"""Python side of the x4-agent bridge.

Runs inside the X4_Python_Pipe_Server host, which loads this module as soon as
X4 registers it through `md.Pipe_Server_Host.Register_Module`. The shape is
copied from `sn_mod_support_apis/python/Time_API.py`: blocking read, write a
response.

Spike goal: prove the loop closes. X4 sends a minimal state every 30 seconds, we
send back an answer that shows up in the in-game logbook. The planner is
deliberately not wired in yet: if the loop breaks you want to know whether it is
the pipe or the model, not both at once.
"""

import os

from X4_Python_Pipe_Server import Pipe_Server

PIPE_NAME = "x4_agent"

# Set X4_AGENT_TEST_ORDER to a ship's ID code (for example TJL-171) to send one
# real order the first time state arrives. This is the Phase 2 write test: the
# ship should visibly start exploring in game. Leave unset for advice only.
TEST_ORDER_SHIP = os.environ.get("X4_AGENT_TEST_ORDER")


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


def decide(state: dict, previous: dict) -> str | None:
    """Return something to say, or None to stay silent.

    Anything written back lands in the player's logbook, so a reply on every
    heartbeat turns the logbook into a wall of identical lines. Only speak when
    the state actually changed. The planner call goes here later.
    """
    if not state:
        return "bridge: unrecognised message"
    if state.get("money") == previous.get("money"):
        return None
    # Note: player.money from the Mission Director is in hundredths of a credit,
    # unlike the money field in the savegame. Convert at the edge.
    credits = int(state["money"]) / 100 if state.get("money", "").isdigit() else "?"
    return f"bridge ok: capital {credits:,.0f} Cr, planner not connected yet"


def main(args):
    print(f"[x4-agent] bridge starting, pipe {PIPE_NAME}")
    pipe = Pipe_Server(PIPE_NAME)
    pipe.Connect()
    print("[x4-agent] X4 connected")

    previous: dict = {}
    order_sent = False
    while 1:
        message = pipe.Read()
        # Log before filtering out pings. If you only ever see 'state' and never
        # 'ping', the read side is dead while the write side lives, and that
        # distinction is what makes this debuggable.
        print(f"[x4-agent] received: {message}")

        if message == "ping":
            # The Server_Reader pings until connected; no reply expected.
            continue

        state = parse_state(message)

        # Phase 2 write test: one real order, once.
        if state and TEST_ORDER_SHIP and not order_sent:
            command = f"explore {TEST_ORDER_SHIP}"
            print(f"[x4-agent] sending order: {command}")
            pipe.Write(command)
            order_sent = True
            previous = state
            continue

        reply = decide(state, previous)
        previous = state or previous
        if reply:
            pipe.Write(reply)
