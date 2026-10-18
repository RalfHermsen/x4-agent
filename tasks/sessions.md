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

## 2026-10-18: reading the log, and a plan for playing unattended

No code against the game. The six-day live log was read end to end: 1,511
cycles, 3,511 repricing commands from Python against about 900 model
decisions, 757 proposals swallowed by the gates (220 of them "already busy":
the model never hears that a proposal was refused), 397 empty cycles. The
conclusion, and the order of work that follows from it, is in
`tasks/plan-2026-10.md`.

Built for measuring: `planner.py` can send the reasoning call to an
OpenAI-compatible endpoint (`--model openai:<name>`, `X4_OPENAI_URL`,
`X4_OPENAI_KEY`) while `X4_EXTRACT_MODEL` keeps the translation step on the
measured local setup; `evaluate.py` now counts the executor gates too and
ignores the `*.replaced-*` copies `edit_save.py` leaves behind. A comparison
of the local model against a hosted one over every save was started; the
advice per save is under `out/cmp-*`.

Established by reading the game's own Lua: blueprints are bought with
`C.LearnBlueprint` after a separate `TransferPlayerMoneyTo`, gated by
`HasLicence` and the licence's `minrelation`, priced at `avgprice * 10`.
Neither that call nor MD's `add_blueprints` takes money by itself. The house
rules for an honest `blueprint` verb are in the plan.

Also assessed: X4Mcp/X4Native as the hand on the keyboard for unattended
test runs (load a save, reload, chat commands, screenshot, shut down), and the
community's construction plans as hand-designed layouts applied in stages.
Both are Phase 2 of the plan.

Later the same day, building the plan. Phase 1 done (1.1 to 1.8, one commit
each, 36 tests): refusals back in the report, no model call on an unchanged
state, the parser reading blueprints, built modules, capacity, plot and the
station to build storage link, expansion gates and funding, expansion
tracking through five stages, the scorecard, and the model comparison
written up. Phase 2: X4Mcp installed (it needed OpenSSL 3 beside X4.exe),
launch_game.py and harness.py prove verbs in the game with no one at the
keyboard, save_008 is the agent's own save slot. Found on the way: every
Lua command had always run twice (the file is loaded twice), and a
no-plan host still asked for an autosave and overwrote the player's newest
one, restored from saves/reference. Then dockat, docked and blueprint,
proven by buying a Teladi module blueprint for exactly its maxprice.
