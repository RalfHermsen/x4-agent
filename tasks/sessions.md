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

## 2026-10-18 evening to 2026-10-19 morning: the rest of the plan, and the first measurement

The evening built what was left of phases 2 to 4 and proved most of it in the
game with no one at the keyboard: blueprint purchases with a docked ship and
release (2.1a), fleet roles under a ship (3.4), repeating orders (3.5), the
player's reservation of a ship (3.8), limits that only raise (4.3), revisits
(4.4), the trade ledger (4.7), resupply (4.10), patrols (4.11) and turret
settings (4.12). Phase 4's verbs for buying and selling ships, hauls and
repairs were built and tested offline.

For 2.4 the runs were made to cover game hours: SETA from MD, which the game
allows only with the item in the player's inventory and the player in a
pilot seat, so the item was added to a copy of the baseline and the player
seated by hand once. One cycle of three minutes then covers about eighteen
game minutes. The first pair, from the small-station start, was stopped:
one usable ship and no known shipyard leave the agent nothing to add. Its
advise run found two bugs: the model proposed exploring with the ship the
player sits in (now refused for every command, L19), and the panel and the
memory treated advise mode as if it sent (now `sends=False`). One look at
the panel by the player proved 3.9.

The measured pair ran on the 73-hour save with 50 million credits, execute
first. Result: nothing measurable, slightly less income per game hour than
the game alone and a freighter lost to pirates (`docs/experiments.md`). The
model's prices and Python's repricing cancel out, and in 117 model cycles it
never proposed spending the money. On the way, 4.1 (a freighter for the
build storage), 4.8 (attack events, with the killer named) and 4.9 (a
repair) were proven. Two things outside the code: the model server had been
running the planner on its CPU since a restart three days earlier, which
made the first cycle take four minutes (fixed by restarting it); and a
backtest of the hosted route spent that key's whole daily budget on the free
tier, which another service shares (L20).

`backtest_extract.py` replays every stored reasoning through the translation
step three ways. A parser that only fills simple action types from words in
the line, and only with codes from that cycle's report, turned 681 numbered
lines into 546 actions with no invented reference; the hosted model could
not be measured within its daily budget.

In the morning's proofs, a ship was bought at a wharf for exactly the logged
price and queued there, a ship was sold for exactly the logged value, and a
repair turned out to have been free: the game's Repair order does not
charge a ship of ours, so the verb now pays like the ship menu (L8i).
Proven again with the payment: 10,159 Cr for FWR-392, hull full one save
later, and a purchase above its cap refused. Not yet: the bought ship was
not built within 100 game minutes (the wharf started nothing), and the
haul's two orders left the queue without running.
