# Experiments

Measured runs of the agent in the real game. Each run starts from the same
baseline save, runs unattended for a fixed wall-clock time, saves into the
agent's slot and is compared with the baseline on the scorecard (`score.py`).
Everything a run produced is in `out/experiments/<stamp>-<mode>-<name>/`:
`run.json` (settings and commit), `run.log`, `host.log`, `agent.log` (every
cycle's sitrep, plan and commands), `memory.json`, the final save and
`score.txt`. That folder is not in the repository; this file is the record.

## 2026-10-18: advise against execute, two hours each at six times speed

The plan's 2.4: does the agent play better than the game's own managers?
Advise mode is the control: the agent reads every save and plans, but sends
nothing, so the game's own station managers and ship AI play alone. Execute
mode sends the validated commands. The difference between the two results is
the agent's contribution.

### The first baseline, and why it was dropped

The first pair started from `save_007`, the small-station start: one station,
two ships, 200,000 Cr. Its advise run was stopped after 40 minutes, because
that start leaves the agent almost nothing to play with. One of the two ships
is the one the player sits in, which the agent may not order, so the fleet
is a single freighter; and the player knows no shipyard, so money cannot buy
ships either. What the agent proposed in eleven cycles shows it: exploring
with the player's ship, the one-time settings, once an operating budget for
the station, and a repeating trade route the executor cannot carry out yet.
A test of what the agent adds needs something to add to.

Two things that run did establish:

**Speed, measured.** The first `seta on` reaches the game only after the
first planning cycle, because the host reads nothing while the model runs;
the logbook line written in that frame still shows factor 1. Five minutes
later the next one logs `active 1, available 1, factor 6`, and from then on
one 180-second cycle covered about 1,110 game seconds, a little over six
times real time.

**A guard.** The first cycle proposed `explore TJL-171`, the ship the player
sits in. Advise mode sent nothing, but execute mode would have flown the
player along on an explore order. Hauls, sales, purchases and the standing
rules already skipped that ship; the model's own proposals did not, and the
sitrep called the ship idle. The command filter now refuses any command for
it, and the sitrep calls it the player's own ship (`457500e`, lesson L19).

The player also touched that run by hand: opened the agent's panel once,
which proved 3.9, and reserved ASO-629 from its context menu. Advise sends
nothing, so neither changed the game state.

### Setup

| | |
|---|---|
| Baseline | the frozen 73-hour save: two stations (KYV-745 with 26 modules, GKL-870 still empty), 23 ships (10 container freighters, 7 fighters, 4 solid miners, 2 scouts), 116 known stations, among them five shipyards (M ships at SCY-867, TXT-319 and EQU-824; L and XL at HOW-875 and CXY-258) |
| Changes to it | credits raised from 40.5 million to 50 million (`edit_save.py --credits`), so that buying ships is a real option; the SETA item added (`--inventory inv_timewarp`); the player seated by hand in the fighter NBO-436 in open space, since the game allows time warp only from a ship's controls |
| Frozen as | `saves/reference/baseline_73h_50m.xml.gz`, game time 73.56 h |
| Length | 120 wall-clock minutes per run |
| Order | execute first, then advise: if buying a ship fails, that shows within minutes, not halfway through the night |
| Speed | SETA at factor 6, asked for every five minutes (`experiment.py --seta`) |
| Planner | `gemma4:26b-a4b-it-qat` on a local Ollama server, one cycle every 180 s of wall time |
| Code | `fdb8ccf` for both runs (`run.json`) |

The SETA item and the added credits are test tools: both runs start with
them, and the agent has no verb that touches the item. In the control run
the game's managers do nothing with player money, so the comparison shows
what the agent makes of it: ships bought and put to work, or money spent for
nothing.

### The execute run, 23:38 to 01:38

| | Baseline | After | Change |
|---|---|---|---|
| Game hours | 73.56 | 84.97 | +11.41 |
| Credits | 50,000,000 | 69,251,850 | +19,251,850 |
| Stations, modules | 2, 26 | 2, 26 | none |
| Ships | 23 | 22 | JUN-174 lost |
| Idle, failing | 0, 0 | 0, 0 | none |
| Builds running | 1 | 1 | one step further |

Eleven game hours in two wall hours: 5.7 times real time on average,
including the minutes before the first `seta on` and the saves.

**What it did.** 51 cycles; 212 model actions accepted, 6 refused. 386
commands reached the game: 331 prices, 13 budgets, 10 `sellware`, 7
assignments, 6 explore orders, 6 ledgers, 5 limits, 3 repairs and the
one-time settings. No ship was bought: the model never proposed one, with
50 million at hand and five known shipyards. Its goals at the end were the
storage overflow at KYV-745, satellite coverage and a self-sufficient
production chain.

**Prices went back and forth.** The model raised prices to just under the
best known bid; Python's repricing, which undercuts the cheapest rival
seller by 2 % (`executor.repricing`), lowered them again whenever the model
left a ware alone. That is most of the 331.

**A loss.** JUN-174, one of the ten freighters Python had pointed at
silicon wafers, was attacked twice by Scale Plate Pact pirates and destroyed
in Hewa's Twin II by ZII-143.

**What it proved** (plan items):

* **4.8 early warning.** 30 events reached the host, 23 of them attacks on
  the fighter KGZ-352 by Xenon raiding parties in The Void; the logbook
  names each attacker and its faction, the host planned after each as soon
  as the save was in, and the loss reads `DESTROYED: JUN-174 by ZII-143
  (Scale Plate Pact)`.
* **4.1 build storage.** `ORDER: SBA-383 now supplies the build storage of
  KYV-745`; in the final save SBA-383 sits in KYV-745's group 4, whose role
  is `tradeforbuildstorage`, and the build moved from waiting for resources
  to waiting for its construction vessel.
* **4.9 repair.** Three priority repair orders sent KGZ-352 to SCY-867. Its
  hull was 2,183 in the baseline and full in the final save (the game writes
  a hull value only for a damaged ship). There was no payment, found the
  next morning: the game's Repair order does not charge a ship of ours (the
  transfer is commented out in `order.repair.xml`, because the ship menu
  pays up front), so that repair was free. The verb now pays the yard's
  repair price before the order exists. The free repair is small against
  the 19 million either run earned, but the execute run had it and the
  control did not.

**What went wrong on the way.** The model server had been running the
planner on its CPU since a restart three days earlier: the first cycle took
245 s. After a restart of the model server the planner ran on the GPU again
and a cycle took 16 s (median); one cycle failed during that restart. The
timings in `docs/contracts.md` were taken on 2026-10-18, after that
restart, and are almost certainly CPU timings too: 100 to 316 s per save
there, against 16 s per cycle here on the GPU.

### The advise run, 01:41 to 03:41

Same baseline, same length, code `fdb8ccf` (the advise-mode fix below came
after it). 65 cycles, 264 model actions, nothing sent. As advice it had 237
prices, 20 budgets, 11 assignments, 10 `sellware`, 8 explore orders and 6
fleet roles. 59 attack events reached the host, 29 of them on KGZ-352 in The
Void; no ship was lost.

### Comparison

| | Advise: the game alone | Execute: with the agent |
|---|---|---|
| Game hours run | 10.92 | 11.41 |
| Credits gained | 19,322,351 | 19,251,850 |
| Credits per game hour | 1.77 million | 1.69 million |
| Ships at the end | 23 | 22 |
| Stations, modules, builds | unchanged | unchanged, one build a step further |
| Commands sent | 0 | 386 |

**The agent added nothing measurable.** Per game hour the game alone earned
about 5 % more, and the agent lost a freighter. One pair of runs cannot
separate that from chance, so the honest reading is: no sign of a
contribution, and no sign of a large harm.

Why, from the logs:

* **Its actions cancel out.** Most of what the agent sends is prices, and
  two parts of it disagree about them: the model raises to just under the
  best bid, Python's repricing cuts to just under the cheapest rival. The
  earlier comparison already found both models spending most actions on
  prices although the guidelines leave pricing to Python.
* **It does not use the money.** 50 million and five known shipyards, and in
  117 model cycles across both runs (52 and 65) not one purchase, expansion
  or blueprint was proposed.
  The station's goals talk about storage overflow and production chains,
  and the actions stay at prices.
* **The one decision with weight cost a ship.** Ten freighters were pointed
  at silicon wafers (Python's `focus_fleet`, because silicon wafers crowded
  the store); one of them met pirates on a trade run and was destroyed.
  Whether the focus put it there is not provable from two saves.

What would change the next measurement, in order of what the logs point at:

1. Settle pricing in one place: either the model leaves prices to Python,
   or Python's repricing leaves a ware alone for a while after the model
   priced it.
2. Put idle capital in front of the model as a fact with options: money on
   hand against the price of a freighter or a miner at a known shipyard,
   and which station could use one.
3. Then two or three pairs of runs, not one, so a single pirate attack does
   not decide the comparison.

Done on 2026-10-19, before any new run: pricing is Python's alone (a price
the model proposes is refused with the reason, and the prompt, the
guidelines and the report's pricing section say so), and the parser now
reads the numbered actions before call 2 does (`docs/contracts.md`). In one
offline cycle on the same baseline the model proposed no price at all.

### The advise-mode fix

Seen on the in-game panel during the first, dropped advise run: `sent:` for
commands that advise mode never sends, and the next cycle reporting them as
failed ("TJL-171 is on Wait, not Explore"), which told the model something
untrue. The memory treated every cycle as one that sends. Since `4683b6c`
the host passes `sends=False` in advise mode: the cycle plans as before but
keeps nothing of what it would have done, and the panel says `would send`.
The advise run above predates the fix; it changed that run's advice, not
its game.

## 2026-10-19/20: the action catalog, two pairs of runs (5.5)

The same question as 2.4, with the action catalog on (`X4_CATALOG=1`,
`tasks/plan-catalog-2026-10.md`): Python puts situations with ready options
in the report, the model picks one option or none per situation, and only
those choices plus Python's own rules are sent. Same baseline
(`baseline_73h_50m`), same length (120 wall-clock minutes), SETA, the local
model, execute first in each pair. The plan's rule: the catalog is worth
keeping if the execute runs beat their advise runs, and beat 2.4's execute
run.

### Stopped and restarted on the way

The first execute run was stopped five times in its first minutes, each time
for a fault the logs showed within a few cycles, fixed with tests, and
started again from the baseline:

| Seen | Fix |
|---|---|
| a ship bought every cycle (two in six minutes, on course for forty) | at most one purchase per game hour, none while a ship waits for work (`e396702`) |
| an expansion asked for while one was planned, an assignment already held, a budget for a station with no modules: re-sent every cycle, without effect | the executor's "already in effect" gate knows all three (`1159b2c`) |
| four answers to one situation (`S1: 1` to `S1: 4`), all sent: every miner left its station | one answer per situation, a second is reported (`d26b22c`) |
| a scout re-sent every cycle or two: on arrival it sweeps the sector it is in, which looked like covered ground; and `automine` left a miner in its station's mining group | a scout gets a game hour after our explore order; the automine option is gone (`5927fc0`) |

Two more things went wrong around the runs, not in the agent. Stopping a run
from outside left its experiment process alive, and the first of those
finished its own two hours in the middle of the run then going, saved that
game into its own folder and started the next run, which refused because the
game was running; that folder is marked invalid and the stale processes were
stopped by hand. And the game window was minimized for 24 minutes during the
first execute run; X4 stands still then, so that run has fewer game hours,
and runs now restore the window themselves (`e7ad897`).

Between the pairs one more fault: VSR-185 and KGZ-352 came into the baseline
on a MoveWait without a timeout, and every order for them queued behind it,
seven explore orders in a row for VSR-185 among them. A new verb, `clear SHIP`,
cancels a ship's orders, and a catalog choice for a ship held by an order of
its own sends it first (`b5623a2`, proven in the game on the baseline before
the second pair). So the pairs differ in code: the first ran `5927fc0`, the
second `b5623a2`.

### Results

| | Execute 1 | Advise 1 | Execute 2 | Advise 2 | 2.4 execute | 2.4 advise |
|---|---|---|---|---|---|---|
| Game hours | 8.83 | 10.87 | 11.12 | 11.26 | 11.41 | 10.92 |
| Credits gained | 5,078,716 | 19,421,126 | 10,199,125 | 21,223,015 | 19,251,850 | 19,322,351 |
| Paid for ships | 8,412,636 (8) | 0 | 9,058,083 (9) | 0 | 0 | 0 |
| Per game hour, credits | 0.58 M | 1.79 M | 0.92 M | 1.88 M | 1.69 M | 1.77 M |
| Per game hour, ships at cost | 1.53 M | 1.79 M | 1.73 M | 1.88 M | 1.69 M | 1.77 M |
| Ships lost | none | JEP-977 | GWH-145 | KGZ-352 | JUN-174 | none |
| Idle at the end | 2 | 0 | 7 | 0 | | |
| Failed cycles | 0 of 55 | 0 of 64 | 0 of 45 | 0 of 59 | | |

"Ships at cost" counts every bought ship at the price paid, which flatters
the execute runs: seven of execute 2's nine ships ended the run idle.

**The rule is not met.** Both execute runs earned less than their advise
runs, also with the bought ships counted at full price: 15 % less in the
first pair, 8 % less in the second. The second execute run is above 2.4's
execute run only when its ships are counted at cost.

What the logs say:

* **The execution works.** No failed cycle in four runs, every chosen option
  carried out, and the faults that remained were found in minutes and
  fixed. The catalog solved what it was built for: the model's choices
  reach the game.
* **The decisions with weight are purchases, and they do not pay within a
  run.** Eight and nine ships of about a million each. In execute 2 the
  model bought six solid miners while KYV-745's solid store was 99 % full;
  they had nothing to mine and sat idle. That is the catalog's fault as much
  as the model's: "money unused" offers a solid miner whatever the stores
  say, and the purchase brake counts only idle ships the catalog has work
  for, so miners without work did not hold the next purchase.
* **Little else is left to decide.** With the re-sends gone, many cycles show
  no situation at all: the expansion is waiting for a construction vessel,
  storage modules have no verb, and taking miners off a full station needs
  a verb that releases them.
* **One decision saved a ship.** KGZ-352, stuck in Xenon space since the
  baseline, was cleared and brought home in execute 2 and survived; in both
  advise runs the game alone left it there, and in advise 2 it was
  destroyed. The scout GWH-145 was lost in execute 2 on an explore order.

What would change the next measurement:

1. Buy only for a need the save shows: a miner of the kind a station is
   short of, with room to store it; a freighter when products pile up. No
   purchase for "money unused" alone, and every idle ship holds the next
   purchase.
2. The verbs the catalog keeps missing: storage modules, and releasing a
   ship from its station.
3. Longer runs, or a ledger of what each bought ship earns, before ships are
   judged at cost.

### Afterwards: why nothing could grow

In all four runs, and in 2.4's, KYV-745's expansion sat at step 1 of 10,
waiting for a construction vessel, from the first game hour to the last. A
player expansion names its build storage as the build's builder, the parser
read that as a vessel, and the rule that hires one never fired (`0bca33f`).
Proven the next morning on the same baseline, both ways: a hired NPC builder
(50,000 Cr) and a bought one (14.7 to 17.4 M, then `deploy`) each got the
expansion building within half a game hour. So every run so far measured a
station that could not expand, which is the main way an X4 station makes more
money; the comparison above holds for that station, not for the agent's
ceiling.

## 2026-10-21: counted again, with what the stations hold

The scorecard counted player money only. In X4 a station keeps its own
account and its own stock, and when it grows the game draws its budget from
the player: once KYV-745's expansion was built (the builder fix above), its
store grew by about a third and filled, and the money that bought or mined
into it left the player's account. Since `c5e36d2` the scorecard also counts
the stations' and build storages' accounts and their stock at the game's
minimum ware prices (`net_worth`), and shows the stock at average prices
beside it. Every finished run, scored again from its end save:

| Run | Arm | Game hours | Credits per game hour | Net worth per game hour | With bought ships at cost | Stock change (min prices) | Modules | Ships lost |
|---|---|---|---|---|---|---|---|---|
| 2.4 execute | free planner | 11.41 | 1.69 M | 1.79 M | 1.79 M | +0.16 M | +0 | 1 |
| 2.4 advise | game alone | 10.92 | 1.77 M | 1.82 M | 1.82 M | +0.42 M | +0 | 0 |
| e1 | catalog | 8.83 | 0.58 M | 0.67 M | 1.62 M | +0.31 M | +0 | 0 |
| a1 | game alone | 10.87 | 1.79 M | 1.82 M | 1.82 M | +0.41 M | +0 | 1 |
| e2 | catalog | 11.12 | 0.92 M | 1.02 M | 1.83 M | +0.52 M | +0 | 1 |
| a2 | game alone | 11.26 | 1.88 M | 1.81 M | 1.81 M | +0.43 M | +0 | 1 |
| e3 | catalog, builder fixed | 11.50 | 0.65 M | 1.08 M | 1.97 M | +3.25 M | +2 | 2 |
| a3 | game alone | 11.40 | 1.86 M | 1.82 M | 1.82 M | +0.43 M | +0 | 0 |
| r1 | rules only | 11.41 | 1.37 M | 2.07 M | 2.07 M | +8.00 M | +1 | 1 |
| n1 | rules only, no repricing | 11.32 | 1.19 M | 2.01 M | 2.01 M | +8.22 M | +1 | 2 |

**The game alone is very steady**: five runs at 1.81 to 1.82 million per game
hour in net worth. Its credits per hour varied more (1.77 to 1.88) because
money moved between the player and the station.

**Python's rules beat it** once the station can grow: 2.07 and 2.01 million,
11 to 14 % more, in two runs. The difference is stock: the expansion gave the
store room, and the station filled it. Repricing makes little difference
(2.07 with, 2.01 without).

**The catalog runs stay below the rules-only runs**: e3, with the builder
fixed, reaches 1.97 million only with its ten bought ships counted at what
they cost, five of them idle at the end.

What this does not settle:

* Part of the rules-only gain is one-off: new storage fills once. A longer
  run shows how much of it continues.
* Stock is valued at the game's minimum prices; ore and ice have few buyers
  near KYV-745, so even that may be generous for them. New modules and lost
  ships are in no column.
* The purchase rules of 5.6 came after e3; the catalog with them is what the
  next two runs of the series measure.

## 2026-10-21: three arms (5.7)

The same baseline, two hours each at six times speed, scored with the
scorecard of `2d7a911`: player money, the stations' and build storages'
accounts, their stock and their modules, all at the game's minimum prices.
Ships are not in it; bought ships appear in the last column at what they
cost. The advise arm was not run again: advise sends nothing, so code
changes do not change its game, and five runs of it were on hand.

| Run | Arm | Game hours | Net worth per game hour | With bought ships | Modules | Ships lost |
|---|---|---|---|---|---|---|
| 2.4 advise, a1, a2, a3 | the game alone | 10.9 to 11.4 | 1.81 to 1.82 M | | +0 | 0 or 1 |
| r1 | rules only | 11.41 | 2.12 M | 2.12 M | +1 | 1 |
| n1 | rules only, no repricing | 11.32 | 2.07 M | 2.07 M | +1 | 2 |
| r2 | rules only | 11.09 | 1.95 M | 1.95 M | +1 | 1 |
| c1 | rules and catalog, purchases only for a need | 11.32 | 2.11 M | 2.11 M | +2 | 2 |
| c2 | the same, two fixes later | 11.46 | 2.05 M | 2.05 M | +2 | 3 |
| e3 | rules and catalog, before 5.6 | 11.50 | 1.15 M | 2.04 M | +2 | 2 |

The plan's rules:

* **Python's rules are worth their place:** all three rules-only runs beat
  all five runs of the game alone, by 7 to 17 %. Most of it comes from the
  builder fix: the waiting expansion was built, the station had room, and
  its store filled. Repricing makes no measurable difference (2.07 without,
  2.12 and 1.95 with).
* **The model is not yet shown to be worth its place:** rules with the
  catalog average 2.08 against 2.05 for rules only, inside the spread of
  the rules-only runs. With the purchases of 5.6 it no longer loses; what it
  adds is one more expansion per run, and it lost the two ships it sent
  exploring, a scout and a fighter, in both catalog runs.

Changed during the series, each between runs: a purchase is answered only
for a need (5.6, before r1); a ship fighting back or fleeing is not cleared,
and an explore order counts from when it was sent (before c2, after the
catalog cleared a defender in combat six times in c1); after the series,
scouts explore and a lost scout is replaced at once, which is the player's
decision, and a fighter on covered ground is offered home as a defender.

What would tell more:

* Longer runs. Part of the rules-only gain is new storage filling once, and
  an expansion pays off over more than eleven game hours.
* More catalog runs with the code as it now stands, so that two is not the
  whole sample.
