# Session log

What happened, in order, so a later session does not have to reconstruct it from
the commit history. Newest last.

## 2026-08-19: from nothing to an agent that acts

Phase 1 (read-only): `save_parser` streaming a savegame with lxml `iterparse`,
`sitrep` condensing it, `planner` asking a local model under `guidelines.md`.
The two-call pattern was introduced the same day, after a single constrained
call silently collapsed every action to `hold`.

Phase 2: the named-pipe round trip, built on `sn_mod_support_apis`. Game to pipe
to Python and back, proved with a quicksave triggered from outside the game.

Phase 3: the executable vocabulary grew to `assign_ship`, `set_behaviour`
(explore, autotrade, automine), `set_budget` and `expand_station`, each with the
MD side written against the game's own schemas. Four validation gates were added
in the order their failures appeared: does it exist, is it ours, is it already
true, is the ship busy.

Diagnosed along the way: a station that would not buy its inputs turned out to
have a one-star manager and a zero operating budget, and X4 stores neither in a
way that looks like a value. See lessons L1 and L3.

## 2026-08-20: the Lua layer, and finding out it had never run

Established that prices and trade rules are settable after all, in Lua rather
than MD, which reversed a documented conclusion from the day before. Built the
Lua side of the bridge: MD forwards what it cannot parse, Lua takes the command
apart and calls the same functions the station configuration menu calls.

Added `set_price`, then `set_trade_rule`. The latter turned out to need an
empire-level rule object created first, so the agent creates exactly one,
`x4-agent: own faction only`, and finds it again by name.

Then tried to verify it and could not. The savegame holds no trade rules, the
Lua layer had no way to report anything, and `DebugError` writes to a log file
the game does not produce unless launched for it. Building the feedback channel
came first: `log()` raises a UI event, MD writes it to the player logbook, the
logbook lands in the savegame. A manual command path (`logs/outbox.txt`) was
added at the same time, because until then the only way into the game was to
talk the model into proposing something.

With those in place the real fault was visible: the Lua file's init had never
run at all, so both verbs written that day, and the one written the day before,
had been dead the whole time. Cause and fix in lesson L8. Confirmed working the
same evening, with `[x4-agent lua] file loaded` and `ready, handling: price,
tradeware, traderule` in the logbook.

Also that day: ships that cannot carry out their orders are now reported with
the game's own failure message and how long it has been going on, which came out
of a question about the two miners that could not sell what they mined.
