# Working in this repo

Notes for whoever picks this up next, human or model. The `docs/` folder
explains what was learned about X4; this file is about how to work here.

## The one rule

**Nothing is finished until it has been observed in the running game.**

This repo has produced, more than once, a feature that was written, deployed,
committed and described as working while in fact never executing a single line
in the game. Two whole verbs, `price` and `tradeware`, were shipped that way and
sat dead for a day. The code was correct. The loading was not, and nothing in
the pipeline said so.

So: a green test proves the Python half. A log line saying "sending" proves the
pipe. Neither proves the game did anything. Ask for evidence from inside the
game, and if there is no way to get any, build one before building the feature.

Two channels exist for exactly this, and both should be used:

* `logs/outbox.txt` — one command per line, sent on the next heartbeat. This is
  how you try a verb by hand instead of talking the model into proposing it.
* The Lua layer's `log()` raises a UI event that MD writes to the player
  logbook, which lands in the savegame. Grep a fresh save for `[x4-agent lua]`.

## Layout

| Path | What it is |
|------|------------|
| `save_parser.py` | streaming read of the savegame into plain dicts |
| `sitrep.py` | the savegame condensed into something a model can read |
| `planner.py` | two calls to a local model: reason freely, then fill the schema |
| `schemas.py` | the contract between model and executor |
| `executor.py` | the whitelist, and every gate before a command is allowed out |
| `memory.py` | goals, outcomes and settings carried between cycles |
| `agent.py` | one cycle, tying all of the above together |
| `bridge/` | the in-game extension: MD script, Lua layer, Python pipe module |
| `docs/` | findings about X4 itself, written as they were discovered |
| `tasks/` | lessons learned and the session log |

## The split inside `bridge/`

MD does cues, game events, orders, assignments and builds. It has **no string
handling at all**, so it cannot take a command apart; it compares whole strings
it builds itself.

Lua does everything that needs a string or a UI-layer function: prices, trade
rules, ware toggles. MD forwards anything it does not recognise verbatim, so a
new Lua verb needs no change in MD.

The Lua file is loaded through `ui.xml`, the documented route. The MD cue that
also loads it is a fallback and can stay.

## Running it

```
python deploy_bridge.py                       # repo -> game folder
python run_host.py --execute --interval 180   # kills stale hosts, then starts
```

The host imports this repo once, so any change to the Python here needs the host
restarted. Changes under `bridge/` need `deploy_bridge.py` and then a game
reload, or `/refreshmd` and `/reloadui` in the in-game chat window.

## House style

Comments say **why**, not what. Most of the comments in here are the scar from
something that went wrong, and they are the reason it does not go wrong twice.
Match that: if you fix something subtle, leave the evidence behind.

Keep `executor.describe()` the single source of truth for what the agent can do.
The planner prompt is built from it, so the model is never told it can do
something it cannot.
