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

## 2026-10-21/22: three long runs, 33 game hours each (6.1)

The same baseline, six hours of wall time at six times speed, one run per
arm, with a copy of the save every hour so that the rate over the last third
can be read apart from the whole run. Net worth as in 5.7 (player money,
accounts, stock and modules at minimum prices).

| Net worth per game hour | The game alone | Rules only | Rules and catalog |
|---|---|---|---|
| Whole run | 1.83 M | 1.84 M | 1.98 M |
| Last third | 1.82 M | 1.61 M | 2.04 M |
| Credits per game hour, last third | 1.77 M | 1.71 M | 2.03 M |
| Stock change, whole run | +0.4 M | +8.0 M, all in the first five game hours | +6.0 M |
| Modules | +0 | +1 | +2 |
| Ships lost | 4 | 2 | 2 (and three lost scouts replaced) |

* **The game alone is steady:** 1.82 to 1.83 million per game hour throughout.
* **Rules only:** the lead of the two-hour runs was the one-off fill of the
  larger store after the expansion finished; once full, the station earned
  less per hour than the game alone (1.61 against 1.82 over the last third).
  Which rule costs that is item 6.8 of `tasks/plan-growth-2026-10.md`.
* **Rules and catalog:** the only arm with more income per hour at the end,
  12 % over the game alone in the last third, in credits and not in stock.
  The difference from rules only is a second expansion, refined metals,
  which eats the ore that filled the solid store; the rules alone only
  finish the expansion the save already had planned. The model chose it
  from `storage_full`'s options, and the position test (`docs/contracts.md`)
  says its choices follow the order more than the content: what paid is the
  option, an expansion that uses what piles up, more than the choosing.

One run per arm; the direction is clear, the size is not yet. The rule
that follows is Python's: expand with what uses the stock that piles up
(the branch's `grow` ranks by margin and demand), and measure it against
these three.

## 2026-10-22: which rule costs income, from a grown station (6.8)

The long rules-only run earned less per hour than the game alone once its
store was full. To find out why without waiting 33 game hours each time, its
end save (107 game hours, the first expansion built, the store full) was
frozen as a warm baseline, and two-hour runs started from it: the game
alone, every rule, and every rule but one. The code was `main` after the
growth merge (`311a7d7`): the rules now grow stations by themselves
(`grow`), GKL-870 included, and keep traders out of enemy sectors.

| Per game hour | Credits | Net worth (minimum prices) | Net worth (stock up to known demand) | Modules | Ships lost |
|---|---|---|---|---|---|
| The game alone | 1.49 M | 1.76 M | 1.94 M | +0 | 1 |
| Every rule | 1.76 M | 1.69 M | 2.07 M | +3 | 0 |
| Every rule but the fleet focus | 1.75 M | 1.58 M | 2.08 M | +3 | 0 |
| Every rule but the sell limits | 1.98 M | 1.87 M | 1.98 M | +3 | 1 |
| Every rule but repricing | 1.98 M | 1.70 M | 1.99 M | +3 | 1 |

* **Every rules arm earns more credits than the game alone**, 17 to 33 %,
  through growth: KYV-745 and the empty GKL-870 each expanded with refined
  metals, builders hired by Python.
* **Two rules cost income:** the sell limits (4.3) hold stock back that
  would have been sold, and Python's repricing sells under the price the
  game's own managers set; each costs about 0.22 million credits per game
  hour, more than four times the spread between the advise runs.
* **The fleet focus makes no difference.**
* The net worth at minimum prices falls where stock is used up: the rules
  turned 37,000 silicon into wafers and sold them, and silicon counts at 111
  Cr a unit while only 11,600 are asked for. Counting stock only up to known
  demand (`net_sellable`, `3e5d2b2`) removes that bias; credits remain the
  hardest measure.

One run per arm. Both rules are switched off by default after this and kept
behind a switch; a run with both off confirms it.

**Afterwards, the confirmation did not confirm.** With both rules off from
the same warm baseline: 1.83 million credits per game hour, 1.91 in net
worth with stock up to known demand. Had each rule cost 0.22 million, both
off should have been the best arm; it is in the middle. The spread between
runs that grow is evidently larger than the 0.05 between advise runs (an
expansion finishing earlier or later, a ship lost or not), so the single
runs above do not single out a rule that costs income. What does hold: every
arm that grows earns more credits per hour than the game alone, 12 to 33 %.
Both rules stay off by default, because off is simpler (some 200 price
commands fewer per run) and was not worse; that is a choice, not a finding.

## 2026-10-23: the new rules over 33 game hours

The rules as they stood after 6.8 (growth on, sell limits and repricing
off), from the 73-hour baseline, six hours at six times speed:

| Last third, per game hour | Credits | Net worth (minimum prices) | Modules over the run |
|---|---|---|---|
| The game alone | 1.77 M | 1.82 M | +0 |
| Old rules | 1.71 M | 1.61 M | +1 |
| Old rules and catalog | 2.03 M | 2.04 M | +2 |
| New rules | 1.78 M | 1.87 M | +4 |

The new rules built most, four modules on two stations, and at the end
earned no more per hour than the game alone. What they built differs: the
catalog's winning run added refined metals, which eats the ore that fills
the store; `grow` added water at GKL-870 and nostropoil and water at KYV-745,
because its margin counted every input at the price it would sell for, and
ore, of which we hold ten times what anyone asks, still cost its minimum
price. Since `catalog._input_cost` an input held beyond every known buyer's
demand costs nothing in the margin; on the 73-hour baseline water (eating
the ice) and refined metals (eating the ore) now head the ranking, well
above nostropoil. Whether that is enough is open: water stays just ahead of
refined metals, and this run built water twice without earning more. The
next run with growth shows whether refined metals is what paid.

**Correction, after the parser fix below.** Counted again with modules under
construction left out, the new rules built three modules over the run, not
four, all at KYV-745 (25 to 28); the rates in the table stand, since the
miscounted modules appeared before the last third. The water at GKL-870 was
never built.

## 2026-10-23: GKL-870 was never built

The run with the catalog and the new rules was stopped after twenty minutes:
a budget for GKL-870 and a defender assigned to it were each sent three
cycles running, and `expand GKL-870 water` six times. Each refusal looked
like it had its own cause (no manager, then no dock), and the manager verb
built for it was refused by the game for every one of 54 crew members
("This transfer is currently not possible"). The station had never been
built. In the save the station and both its modules carry
state="construction"; the parser counted every module component as built.
Its build had waited at step 1 of 9 since before the 73-hour baseline, in
every run: a build storage with no money offers to buy 0 of everything while
it still wants the lot, and the funding rule counted the offers, saw nothing
missing, and never sent a credit. No `fund` had ever been sent in any run.

Fixed and proven in the game, one step at a time, from the 75-hour save:

| Step | What happened |
|---|---|
| Funding counts what the build wants | `fund GKL-870 low` (5.2 M); the build finished within about two game hours and used some 0.4 M |
| `manager GKL-870`, crew from our own ships, no fee | refused on the construction site; on the built station a 4-star manager (12/15) arrived within minutes |
| `expand GKL-870 dock` | refused: no construction sequence could attach an M dock, the venturer dock or even a second water module to the 2 km plot. It is full |
| `budget GKL-870 low` | sets min and max (4.9 M and 7.3 M) and moves nothing: two game hours later the account was empty and the ice offer still at 0 |
| `account GKL-870`, the game's "Accept Estimate" | 0.62 M moved, min and max set, the ice offer up from 0 to 17,828 |
| Trade without a dock | in 2.4 game hours not one trader reserved a trade at GKL-870; KYV-745 beside it had eleven. A station without a dock is out of every trader's reach |

Most of this the manual says in a sentence (the Station Building page of the
Egosoft wiki): an unfunded build storage pays nobody, a hired builder that
waits too long for resources may leave, the station account is filled with
the slider or "Accept Estimate", and the dock goes first. Looking there
first would have saved four probes. What it leaves open, trade without a
dock, the last probe answered. GKL-870 stays as it is: a full plot with
nowhere to dock, its 5.4 million in two accounts still ours.

What changed in the rules: a module being built is not counted; a build
storage is funded from what the build wants; a built station without a
manager gets one from our crews (6.9); an empty plot gets a dock before
anything else, and a station without one is not grown (6.10); a station with
a manager and an empty account gets the game's own estimate moved into it,
as its "Accept Estimate" button does (6.11); a manager and money go only to
a station with a dock; a build still waiting for a vessel four game hours
after a hire hires again; an expansion the bridge could not fit is not asked
for again; and a run deploys the bridge it measures (L25: the first proof
run spent half an hour against the previous bridge).

## 2026-10-23: expansions of a working station were free

Why KYV-745 stopped growing at 28 modules, and what that showed about every
growth result before it.

**The stall.** KYV-745's refined metals expansion left a queued build whose
sequence was the station's 28 standing modules and nothing new. Hired
builders came, found nothing to build and went back to their own work;
the build sat queued for every remaining game hour, and Python, seeing a
build planned, asked for no other expansion. The generator, asked again,
returned nothing for any production module on either station: water,
refined metals, nostropoil and a habitat all came back null with the
connectors the player holds blueprints for, while storage, docks and
connectors fitted. With every connector the game has it worked, and adding
one was enough: `struct_arg_cross_01` (88,348 Cr). Python now buys that
blueprint (a ship of ours docks at an Antigone station; a ship still on a
stale MoveWait of its own has its orders cleared first) and requires it for
any production or habitat module.

**The free modules.** With the connector in place, a proof run from the
86-hour save added 12 modules to KYV-745 and 16 to GKL-870 in five game
hours while neither build storage spent a credit. A probe showed why:
`apply_construction_sequence`, which the bridge used to append the plan to
the station before handing it to the build storage, puts the modules on a
station that stands at once, finished and working, and leaves behind a
build of modules that already exist. Only a station still being built (an
empty plot's first modules) got them as construction sites. The faction
logic does not apply the plan; it hands it to the build storage
(`add_build_to_expand_station` with the generated sequence). Done that way,
from the same save, the new module appears as a construction site, the
build runs and the build storage pays (4.83 M down to 4.53 M within the
first game hour).

**What this does to earlier results.** Every expansion of a working station
since the bridge was written was free: in the expansion proofs (6.2's
nostropoil included) and in every run whose arm grew. Those arms gained
modules, and their production, without paying for them. So the finding
that every growing arm earned more than the game alone, 12 to 33 % in
credits (6.8 and the long runs), does not stand as a comparison of play:
part of it, perhaps all, is the free modules. What stands are the arms
that did not grow (the game alone, advise runs) and every finding that
does not rest on what an expansion cost. The series after this fix is the
first in which growth is paid for.

## 2026-10-23/24: growth paid for, rules and catalog over 33 game hours

The first series with expansions built and paid for (`54c707c`), from the
73-hour baseline, six hours at six times speed each. The game alone is the
run of 2026-10-21/22 (nothing grew there, so the free modules never touched
it).

| Last third, per game hour | Net worth | Credits | Modules | Ships |
|---|---|---|---|---|
| The game alone | 1.82 M | 1.77 M | 25 | 23 |
| Rules (lean2-long, 33.8 game h) | 3.41 M | 1.55 M | 25 to 104 | 23 to 20 |
| Rules and catalog (leancat2-long, 30.3 game h) | 2.17 M | 0.22 M | 25 to 108 | 23 to 30 |

**The rules almost double the game alone in net worth**, and it is paid
for: 25.8 million moved into build storages in the hourly saves, 39
builders hired, 34 expansions planned, the connector blueprint bought at an
Antigone station. Most of the growth is in modules (counted at their
minimum price) and in the build storages' accounts; credits per hour stay a
little under the game alone because the money keeps going into the next
build. Whether a module pays back its cost in income is the next question;
over this run credits still rose by 28 million.

**The catalog arm bought 21 ships** (11 scouts, 10 solid miners, about 1
million each) and sent scouts exploring 65 times; the rules arm bought none
and sent none. The scouts died in hostile space and each loss was replaced
at once (the player's policy); the miners were the catalog's "buy one"
option for a station short of a mined ware. Ships are not in net worth, but
counted at cost the catalog arm would still trail. It got fewer game hours
too (the model's calls take time), and its final save never came: the last
save is from 25 minutes before the end, used as its end point. A fault seen
during it, the same assignment sent three cycles running because a group
number means mining at both stations, is fixed in `main` (a sent assignment
counts as done for half a game hour).

One run per arm, and growth runs spread widely (L23). The rules' lead is
large enough to stand without a second run before the next change; the
catalog's deficit has the same cause it had before, purchases.

## 2026-10-24/25: Claude Sonnet 5.5 as the planner, against the rules on the same code

Before this pair, a day of faults found by the Claude runs themselves, all
fixed: group numbers read on each subordinate's own commander (the fleet
focus had turned four miners and a fighter of GKL-870 into wafer traders,
and the catalog handed miners between the stations every cycle), station
roles assigned through `AssignCommander` as the game does it, a drained
station account topped up again, no cycle planning on a save older than its
own last commands, and a purchase counted as soon as it is sent. Three Claude
runs were stopped on the way. The npm Claude CLI turned out to map "sonnet"
to Sonnet 4.6, 93 seconds a call; this pair used Sonnet 5.5 through the newer
CLI, about 12 seconds a call, on the subscription.

| Net worth per game hour | Whole run | 85 to 96 h | Last 11 h | Ships bought | Modules | Credits at the end |
|---|---|---|---|---|---|---|
| Sonnet 5.5 and rules (leansonnet55-long, 33.5 game h) | 1.62 M | 0.78 M | 2.38 M | 25 (6 scouts) | 25 to 104 | 29.4 M |
| Rules only (lean3-long, 33.3 game h) | 2.72 M | 3.08 M | 3.04 M | 0 | 25 to 136 | 75.9 M |
| Rules only, before the fixes (lean2-long) | 3.38 M | 4.43 M | 3.41 M | 0 | 25 to 104 | 78.2 M |

Rates are interpolated between the hourly snapshots over the same game-time
windows; `timeline.py` sorts snapshots by file name, which puts a run across
midnight out of order, and the Sonnet run missed the snapshot at 96 hours.

**A strong model in the catalog still loses to the rules.** Its one lever
that the rules do not pull is buying ships: nineteen miners and freighters
at about a million each plus six scouts, not in net worth and not earning it
back within the run, and the money went out of credits rather than into
modules (104 against 136). Counted at cost the ships would not close the
gap. Its notes were the best fault-finding of the project, but in catalog
mode it chooses from about one situation a cycle. A buy option for a station
short of silicon is the wrong answer since 9.00 anyway: a silicon miner's
efficiency goes with its pilot's skill to the fourth power and doubles with
a probe of ours within 40 km (`docs/forum-findings.md`), so more miners with
one-star pilots add little.

**The rules arm ran lower after the fixes** than before them, 2.72 against
3.38 over the whole run, while building more modules. One run each and
growth runs spread widely (L23): this may be noise, or a fix (defenders that
now really protect, accounts topped up) may cost something. A second rules
run on this code decides before anything is built on either number.

The model's value so far is as a reviewer, not a player. The strategist
(tasks/plan-strategy-2026-10.md, branch `strategy`) is the attempt to give a
model a lever the rules then carry out.

## 2026-10-25: net worth overcounted modules, and the rules run repeated

A second rules run on the same code (lean4-long) came out where the first
did: 2.67 M per game hour over the whole run against 2.72, 3.02 in the last
11 hours against 3.04. So the drop from lean2-long (3.38) was not noise. It
was the measure.

Net worth counted every module at the minimum price of its module ware, and
that price runs two to three times above what the module takes to build. A
microchip module counts 4.12 million; its construction resources cost about
two. lean2-long had built fifteen of them (61.8 of its 71.6 million in module
value), lean3 and lean4 none: they built silicon wafer modules instead, at
0.40 million each. Which ware the margin ranking picks depends on how the
market went: in lean2 wafers piled up, an input held in excess counts as
free, and microchips came out on top, although at the prices the 88-hour
save knew they lose money (`economics.py`). In money the newer runs ended
richer: credits and station accounts 136 million against 107.

`score.py` now also counts modules at their construction resources' minimum
price (`modules_cost`, `net_worth_cost`), the way stock is counted. Every run
again, from its final save, per game hour over the whole run:

| Run | Net worth, modules at ware price | Net worth, modules at build cost |
|---|---|---|
| The game alone (builds nothing) | 1.82 M | 1.82 M |
| Rules, before the fixes (lean2-long) | 3.38 M | 2.16 M |
| Rules (lean3-long) | 2.72 M | 2.38 M |
| Rules, repeated (lean4-long) | 2.67 M | 2.32 M |
| Rules and gemma4, before the fixes (leancat2-long) | 1.93 M | 1.38 M |
| Rules and Sonnet 5.5 (leansonnet55-long) | 1.62 M | 1.32 M |

The order holds: the rules beat the game alone and beat every arm with a
model in it, and the fixes made the rules a little better, not worse. But the
rules do not nearly double the game alone: at build cost they add about 28 %
(2.35 against 1.82). Earlier cards that compared growth by net worth carry the
same inflation, in proportion to how much each arm built.

## 2026-10-26: the strategist (Opus 5.5) and the rules, against the rules alone

leanstrat-long: rules only, with `strategist.py` asking Opus 5.5 through the
API for a plan whenever the last one's horizon had passed, 33.2 game hours
from the 73-hour baseline. Nine plans, 11 to 17 seconds and about $0.07 each.
Compared with the two rules runs on the same baseline and code:

| Per game hour, whole run, modules at build cost | Net worth | Credits at the end | Modules added | Ships bought |
|---|---|---|---|---|
| Rules (lean3-long) | 2.38 M | 75.9 M | 111 | 0 |
| Rules (lean4-long) | 2.32 M | 84.2 M | 120 | 0 |
| Rules and the strategist (leanstrat-long) | 1.21 M | 36.2 M | 100 | 9 |

**The strategist halved the rules' result.** Two rules runs differ by 2 %;
this one is half of either. Its plans grew each time a horizon passed
(refined metals and water from 2 to 7 modules at KYV-745, medical supplies
from 2 to 7, energy cells to 4, teladianium to 5 at GKL-870) and gave both
stations fleet targets, so the fleet rule bought six miners and three
freighters. It chose energy cells and medical supplies for their "demand
hours", which add up what other stations' buy offers ask for: that is the
room in their stores, not what they take, and these are the wares the NPC
economy fills itself (the Economy Primer says as much). Money left credits
for modules dearer than the rules' wafers and refineries, for ships, and for
stock that did not sell (24 million at the end against 15).

Its reasoning read well every time; the numbers it reasoned on were the
weak part. What it would need before another run: realised sales per ware
(the save keeps a trade log), the outcome of its previous plan beside the new
report, plans that add to what stands rather than restate a growing total,
and no fleet targets unless a station visibly lacks ships.

Nineteen of the 28 purchase commands bought nothing and wrote no refusal;
to be looked into.

## 2026-10-26: the stations sold below cost

The save's trade log (now in `save_parser`, `trades`) shows what changed
hands. Over the last 24 game hours of lean4-long, KYV-745 sold silicon wafers
at 176 Cr and bought the silicon for them at 149 of a 150 maximum; with 240
silicon in 107 wafers that is 347 Cr of silicon in each. Refined metals went
at 87 for 174 Cr of ore apiece, microchips at 788, below the game's own
minimum of 805. The repricing rule undercut the cheapest rival on everything,
on the reasoning that "the station's marginal cost is near zero anyway: mined
inputs and its own energy". That held while miners fed the station; once
expansions outgrew them, the game raised the buy prices toward their maximum
and the station bought most of its ore, silicon and ice.

Two rules now (`executor.sell_floor`, `executor.input_caps`): a ware is never
priced below the game's minimum or what its inputs cost at the prices the
station pays for them, and a mined input is bought for no more than 90 % of
what the best product made from it earns, the ware's minimum at the least.
On lean4's final save that raises wafers from 176 to 345 and refined metals
from 87 to 169, and lowers ore from 58 to 43 and silicon from 150 to 111.
Measured next (leanfloor-long).

The trade log does not hold all of our income: over the same window credits
and accounts grew by 2.67 million an hour, the logged trades by about 0.2. So
it is read for what is bought and sold, not as a profit.

Correction, the same day: the floor and caps never ran in the rules runs,
because our pricing has been off by default since 6.8. The prices the trade
log shows are not the rule's either. They are price overrides frozen into the
73-hour baseline by the pricing of that time (`<prices><override>` in the
station: water 51, refined metals 87, wafers 176, microchips 788 and six
more), which the managers never move, so every run since sold at them. The
bridge now hands a price back to the manager (`price <station> <ware>
<buy|sell> auto`, the menu's automatic price checkbox), and while our pricing
is off the rules do that for every fixed price (`executor.automatic_prices`).

## 2026-10-26/27: the player's own ship, and ships paid for that never came

Three runs ended early with the game itself: leanplan-test, leanauto-long and
leanauto2-long (leancat2-long had the same event). In each the player's ship,
the Falcon NBO-436, was shot down. The player then floats in a spacesuit,
where SETA does not work, and about half an hour of game time later the game
was over: the pipe client was garbage collected and never came back, and the
stall reload only replayed the death. `experiment.py` now reads from the
baseline which ship the player last controlled and stops the run, while the
game can still save, when the host log reports that ship destroyed.

The baselines were saved again by hand with the player seated and stopped near
KYV-745 and only a Wait order in the queue (the 73-hour one had carried a
stale DockAndWait). The ship still left. In leanauto2-long the hourly saves
put it near KYV-745, then 3 km from the gate to the next cluster 340 km away,
then back, then at the gate again, standing still for hours in between, under
Wait with the player in the pilot seat; lean4-long had ended at that gate as
well. At 104.5 h it was shot down by a Xenon raiding party in Hewa's Twin II.
What flies it is not known. Not the lockbox and abandoned ship responses (each
find writes a logbook line, and none names it), not the Wait order (its idle
flying is patched off), and none of our commands names it. The state line the
bridge sends every 30 seconds now carries the player's ship, its sector, zone,
position, speed and order, so the next run shows when it moves and under what.

The nineteen purchases of leanstrat-long that seemed to do nothing were paid
for. `buy_ship` pays up front and the ship then waits in the wharf's build
queue until the wharf has the wares for it: at SCY-867 24 of our ships, 22.7
million Cr, waited for advanced electronics. The parser reads these
(`ships_on_order`), the catalog buys no ship of a kind while one is coming and
none at a wharf whose order has waited more than two game hours, and the card
shows them as `on_order`. They are not in net worth, as ships are not.

## 2026-10-27: prices handed back to the managers

leanauto2-long: rules only, with the ten fixed prices of the baseline handed
back to the station managers (`executor.automatic_prices`), 30.2 game hours
until the player's ship was lost. It started from the parked baseline, the
same game 45 game minutes after lean3's and lean4's, so the runs are compared
over the same hours counted from each start, interpolated between the
baseline, the hourly snapshots and the result save:

| Per game hour, first 30 hours | Net worth | Credits | Station accounts | Stock | Modules |
|---|---|---|---|---|---|
| Fixed prices (lean3-long) | 2.34 M | 0.90 M | 1.57 M | -0.38 M | 0.25 M |
| Fixed prices (lean4-long) | 2.27 M | 0.93 M | 1.41 M | -0.33 M | 0.25 M |
| Managers' prices (leanauto2-long) | 2.74 M | 0.30 M | 2.46 M | -0.22 M | 0.20 M |

**The managers' prices earned 18 to 21 % more.** The money stayed on the
stations' accounts rather than coming to the player, which is why credits
grew less. The trade log of the last 24 game hours shows where it came from:

| Last 24 game hours | Sold | Bought | Net |
|---|---|---|---|
| lean3-long | 4.10 M/h | 4.93 M/h | -0.82 M/h |
| lean4-long | 4.28 M/h | 5.00 M/h | -0.72 M/h |
| leanauto2-long | 4.97 M/h | 3.81 M/h | +1.15 M/h |

KYV-745 sold wafers at 305 instead of 176 (half as many), refined metals at 142
instead of 87 (more of them), microchips at 1,028 instead of 788, and bought
half the silicon. The first run of this arm, leanauto-long, lost the player's
ship at 79.9 h; over its first six hours it was behind both rules runs (1.56
against 1.76 and 1.95), so early hours say little.

The strategist changed before its next run: a plan says what to add to what
stands, at most two modules of a ware and four at a station, one miner of each
kind and one trader; the report shows what changed hands per game hour at the
average price and the ships on order; and each plan that ends is shown in the
next report with how far it got and what net worth, credits, accounts, stock
and modules did while it held.

## 2026-10-27: a station that could hold nothing, and the ceremony series

The rules arm on the ceremony baseline (leancer2-long) was stopped by hand at
22.6 game hours. GKL-870, an empty plot at the start, had grown to a dock, a
solid store and eleven production modules (five water, two refined metals,
two wafers, two microchips) and made nothing: its solid store was full with
45,000 ice, 12,000 ore and 1,000 silicon, and it had no container store.
Every ware the bridge builds is a container ware, and so are the energy cells
each module eats, so it could not buy a cell or keep a product. The expand
cue added a solid store with the first module that eats a mined solid; it now
adds an M container store with the first production module of a station that
has none (`$agent_module.isclass.production`, as the game's own
`finalisestations` uses it). In the rerun GKL-870 got both stores with its
first water module, sold 1,544 water within the hour and ended both arms with
13 and 14 production lines selling water, metals, wafers and chips.

The expansion tracker also called a dock or a store done only once it showed
in production, which it never does: GKL-870's dock stood for 20 game hours
while the report said it was queued.

Then both arms ran on that code from the same baseline, 33.8 and 33.6 game
hours, compared over the same hours from each start:

| Per game hour | 0-12 h | 0-20 h | 0-30 h |
|---|---|---|---|
| leancer2-long (rules, GKL-870 dead, stopped at 22.6 h) | 2.08 M | 2.24 M | |
| leancer3-long (rules) | 1.74 M | 1.84 M | 1.94 M |
| leancstrat3-long (rules and strategist) | 1.60 M | 1.78 M | 1.79 M |

**The station that made nothing scored best, because 30 game hours is too
short a window.** The trade log of the last 25 game hours of each run:

| | Sold | Bought | Net |
|---|---|---|---|
| leancer2-long | 3.23 M/h | 3.14 M/h | +0.10 M/h |
| leancer3-long | 5.20 M/h | 4.24 M/h | +0.96 M/h |
| leancstrat3-long | 4.28 M/h | 3.44 M/h | +0.84 M/h |

Fixed, the rules sold 60 % more. But `net_worth_cost` counts a module at its
construction resources at their minimum price, while building one costs
those resources at market price and the builder's fee: over the first 20
hours leancer3 put 0.29 M/h more into modules than leancer2 and had 0.57 M/h
less in credits. A module that has not yet earned back that difference
shows as a loss at this horizon, and a run that builds more trails for a
while. Building is an investment: production modules pay more the longer
they run, and from the middle of the game on a fleet has to be built from
our own production, from the raw materials up, because buying it cannot be
paid for. Self-built fleets are a goal on a horizon of weeks of game time,
and runs and plans are weighed against that, not against 30 hours.

Ships are not counted at all. The strategist arm bought twelve M container
freighters at SCY-867, about 1.07 M each (the player's money fell by that much
within three minutes of each `buyship`), 12.8 M in all, against none in the
rules arm. Counted at what they cost it would lead (about 2.1 M/h against
1.9); counted as the score counts them it trails. Its traders did not sell
more: 4.28 M/h against the rules' 5.20. It built 112 modules to the rules' 95,
cheaper ones (9.8 M against 14.8 M at cost).

The strategist read its own history as intended: after plans returning 1.3
to 1.7 M/h it cut each plan to one cheap module, and the next four returned
1.29, 2.21, 2.42 and 3.02 M/h, which it took as proof that small plans pay.
But a run earns more per hour later on whatever the plan, because more
stands; the history shows each plan's outcome without what the rules alone
did over the same hours, and so credits the plan with the growth.

The scorecard's role counts are what each ship was doing in the last save:
the strategist arm's four miners were docked at that moment and counted as
"other". The rules arm lost freighter IJK-742 to Xenon raiders at KYV-745 and
fighter KGZ-352 in The Void; the strategist arm lost KGZ-352.

The player's ship stayed put in leancer2 and leancstrat3. In leancer3 it
flew twice: at 77.46 h, from its parking place in zone001 through a temporary
zone at 2,870 m/s into zone003, and at 78.43 h on into zone002, where it
stayed to the end. The state line showed `order=Wait` at every 30-second
sample, before, during and after. Xenon were attacking our ships at KYV-745
then (MCX-254 at 77.25 h, EMJ-300 at 77.50 h). The game's own flight
responses, to an attack (`interrupt.attacked`) and to a tide
(`interrupt.tide`), both create a `Flee` order, which the samples would have
shown over a three-minute flight, so neither is confirmed; what flies it is
still open.

## 2026-10-28: shipbuilding stage B, the first two campaign runs

From here a run continues from the last run's result save, so the empire
keeps what it built (`--baseline-file`, `tasks/plan-shipbuilding-2026-10.md`).
Both runs were rules only, with a plan from a file. ship2-long started from
the ceremony baseline with graphene 1, hull parts 1, two liquid miners and no
traders for KYV-745 (ba6e6d1); ship3-camp continued from its result save
with a Teladi defence disc added, traders back to four and six solid miners
(db2d94d).

| | ship2-long | ship3-camp |
|---|---|---|
| Game hours | 74.3 to 107.8 (33.6) | 107.8 to 142.4 (34.5) |
| Net worth | +99.1 M (2.95 M/h) | +210.2 M (6.09 M/h) |
| Net worth at cost | +69.4 M (2.07 M/h) | +172.2 M (4.99 M/h) |
| Player's money | -2.1 M | +122.5 M |
| Station accounts | +45.4 M | +8.1 M |
| Modules | 25 to 107 | 107 to 204 |
| Ships | 23 to 19 | 19 to 26 |

The second run had four times as many modules standing from its first hour,
so its rate is not a verdict on the plan; it is what a campaign is for.

**Losses.** ship2-long lost six ships, four of them (EMJ-300, NDX-233,
GRW-124, IJK-742) to one Scale Plate Pact ship, NRF-961, around KYV-745,
FWR-392 to Duke's Buccaneers and KGZ-352 to the Antigone Republic. With
traders at 0 in the plan, the lost freighters were not replaced. ship3-camp
lost KTK-861 to NRF-961 in its first game hour and nothing after; it bought
six container freighters and two solid miners at SCY-867 and ended at
traders 4/4 and solid miners 6/6.

**The defence disc stood empty.** It was built, and the save showed no
turret or shield on it. A module from `create_construction_sequence` comes
without equipment; the game's own `Apply_Loadout_To_Stations`
(`md/finalisestations.xml`) arms a standing station with
`generate_loadout` and `apply_loadout` on every entry of the plan before
`add_build_to_expand_station`. The bridge now does the same for a defence
module, from the turret and shield blueprints the player holds
(`requireblueprints`), so an empty disc is armed with the next expansion
(28d8989). We hold Teladi M gatlings and M shields, none for L mounts.

**Graphene was overbuilt.** The plan asked for one graphene module; the
margin ranking added four more, and KYV-745 ended ship3-camp with 30,000
graphene in store. Selling, not making, limits it now.

**The money came from the game.** In ship3-camp the player's money rose in
steps of about 22.4 M every four game hours, seven times, while the account
rule sent three commands. The game moves a station's surplus to the player
itself (`md/notifications.xml`, PlayerOwnedMoneyUpdated): above the larger
of its maximum budget and one and a half times its production money, the
account goes back down to the production money. In ship2-long KYV-745's
account filled to 38.8 M without crossing that line, as the amount the game
keeps grows with what the station produces; in ship3-camp it crossed it.
Stage C is reached: 172 M against the 122.5 M the wharf's blueprint needs.

The player's ship showed `order=Wait/0/null/order.wait` at every sample of
ship3-camp and was not destroyed in either run.

Next, ship4-camp from ship3-camp's result save: a second hull parts module,
a second defence disc (which arms the first), the S/M Ship Fabrication Bay,
and eight solid miners, since the refineries stood with 7 ore in store.

## 2026-10-28: ship4-camp and ship5-camp, the wharf and 636 turrets

Two more campaign runs, rules only, each from the last one's result save.
ship4-camp asked for a second hull parts module, a second defence disc, the
S/M Ship Fabrication Bay and eight solid miners; ship5-camp for a third
disc, with the bridge arming plans from our turret blueprints only (4464df2).

| | ship4-camp | ship5-camp |
|---|---|---|
| Game hours | 142.4 to 176.2 (33.8) | 176.2 to 210.2 (34.0) |
| Net worth | +136.4 M (4.03 M/h) | +175.3 M (5.15 M/h) |
| Net worth at cost | +42.8 M | +167.9 M (4.93 M/h) |
| Player's money | 171.8 M to 165.5 M | 165.5 M to 318.1 M |
| Modules | 204 to 265 | 265 to 287 |
| Ships | 26 to 35 | 35 to 36 |
| Lost | IZD-990 (Godrealm of the Paranid), UIE-514 (Xenon) | none |

**The wharf.** ship4-camp bought the blueprint for the S/M Ship Fabrication
Bay from the Teladi at YMH-359, which took the player's money from 170.7 M
to 54.4 M, and built it. The blueprint counts in neither net worth figure;
the game's surplus transfers had the money back within the run.

**636 turrets, and the discs still empty.** With `requireblueprints`, the
disc expansion of game hour 143.8 planned all 129 entries: every group of
every production and storage module got a Teladi M shield and two M
gatlings, and the two discs got nothing, though four of a disc's five
groups take M equipment and only the fifth wants L. Why the generator
passed over the discs is not known yet. KYV-745 went from no turret and no
shield at all (ship4-camp's start) to 636 gatlings and 48 shields.
Every one of those turrets still carries the time it was built as its last
shot, so none has fired yet; ship5-camp's lack of losses cannot be put
down to them.

**270 shields stopped KYV-745.** The refined metals expansion of game hour
156 started from the station's own sequence, which now carried the planned
equipment, and 270 shields stayed in construction: they are made of field
coils and shield components, which no station we know sells, and a build
waits for every ware it lacks. Every module of that build stood; the
executor refuses an expansion while a build runs, so KYV-745 was not
expanded again in ship4-camp or at all in ship5-camp, while GKL-870 took
all 22 of ship5-camp's new modules. The bridge comment of 4464df2, that
`requireblueprints` had planned nothing, was wrong.

The fix (e4c0ea6): a running build whose modules all stand is cancelled
after six game hours, through the interact menu's own CanCancelConstruction
and CancelConstruction, and a plan carries turrets and no shields; a disc
expansion arms every entry, any other expansion re-arms only the entries
that already carry equipment. Whether the game lets go of a running build
is what ship6-camp tests first.

Shields come back with a supply. Field coils and shield components are both
made from energy cells, plasma conductors and quantum tubes, and those two
from graphene and superfluid coolant, which is made from helium. A ship
built at our own wharf needs the same shields, so that chain comes before
self-built ships carry any.

Next, ship6-camp from ship5-camp's result save, with the same plan.

## 2026-10-29: ship6-camp, field coils and shield components

One campaign run, rules only, from ship5-camp's result save. The plan of
ship5-camp, plus a field coils module and a shield components module, and
two traders for GKL-870. The shield components module moved to KYV-745
during the run, when GKL-870's plot had no room for it.

| | ship6-camp |
|---|---|
| Game hours | 210.2 to 244.5 (34.3) |
| Net worth | +176.4 M (5.14 M/h) |
| Net worth at cost | +132.3 M (3.85 M/h) |
| Player's money | 318.1 M to 398.1 M |
| Modules | 287 to 351 (KYV-745 142 to 185, GKL-870 145 to 166) |
| Ships | 36 to 50 |
| Lost | MCX-254 (fighter) and MXB-144, to the Xenon at game hour 232.5 |

**The game does not cancel a running build.** The abort of e4c0ea6 was
refused twice: the interact menu's CanCancelConstruction is false for a
station's running expansion. The game's own scripts cancel queued builds
only. 3765486 takes the command out and reports such a build in the
situation instead.

**The build ended anyway, and how is not known.** XQL-000's deliveries
rose from 6 to 1,326 field coils and from 197 to 725 shield components by
game hour 211.85, and at 211.35 it still wanted 2,808 and 2,773. At 211.65
it had no running build. No command of ours went to KYV-745 in between; a
builder had been hired at 210.42.

**Turrets, and no shields at all.** The third disc's expansion (211.65)
applied a turret-only loadout to every entry, which took off the 48 shields
that stood: KYV-745 ends with 692 turrets and no shield. The discs stayed
empty again, though the bridge passed the generator an explicit list of
turret wares: 0 of 3 defence modules armed. All 692 turrets give game hour
211.7, when the loadout was applied, as their last shot: none fired after,
also not when the Xenon came at 232.5.

**The supply.** The blueprints for field coils (12.77 M) and shield
components (3.18 M) came from the Paranid at SCY-867 at game hours 211.3
and 211.8. KYV-745 ends with four field coils modules, all by margin, and
two shield components modules; GKL-870 with one of each. In
the last 24 game hours KYV-745 sold 42,723 field coils for 12.5 M and
11,577 shield components for 2.9 M, and held 28,235 and 2,730 at the end.
The inputs are the narrow part: plasma conductors had one known seller and
quantum tubes three. a31e89b now refuses an expansion whose bought input
the known sellers cannot feed for four hours.

**GKL-870's plot is full.** From game hour 221 the bridge could not build a
construction sequence at GKL-870 for shield components, then medical
supplies, sunrise flowers, refined metals and spices. The refusals came
back every 2.1 game hours, because the parser kept only two hours of the
logbook; 8a140b5 keeps them over the whole logbook. Its build waited for 12
claytronics until game hour 218, which is before its own two traders came
(219.2 and 220.4): they were not what ended the wait.

**Four miners bought for four that were there.** KYV-745's group 2 held
four miners assigned before the bridge logged its assignments. While
GKL-870 had no groups, group 2 could only be KYV-745's; once GKL-870 had a
group 2 for trade, which a miner can also hold, nobody could say, KYV-745
read as four solid miners short, and four were bought at SCY-867 between
game hours 221 and 225. The four went on mining for KYV-745. The fix:
the bridge names every ship's commander when a save loads.

**Losses.** A Xenon force with an XL came into Hewa's Twin I; MCX-254, a
fighter of ours, and MXB-144, which appears in no save of the
run, were destroyed at game hour 232.5. KYV-745 is in that sector.

Next, ship7-camp from this result save: stage E, the first ship from our
own wharf.

## 2026-10-29: ship7-camp, the first own ship that did not start

One campaign run, rules only, from ship6-camp's result save. The plan of
ship6-camp, plus the blueprints of the Teladi M solid miner and the Teladi
M all-round engine, and a ninth solid miner for KYV-745 built at our own
wharf. Stopped by hand after 14.5 game hours, when it was clear the ship
would not be built.

| | ship7-camp |
|---|---|
| Game hours | 244.5 to 259.1 (14.5), stopped by hand |
| Net worth | +58.6 M (4.02 M/h) |
| Net worth at cost | +52.6 M (3.62 M/h) |
| Player's money | 398.1 M to 455.2 M |
| Modules | 351 to 383 |
| Ships | 50 to 53 (one solid miner and three freighters bought, one lost) |
| Lost | XPR-722 (container freighter), to the Xenon in Bright Promise at game hour 257.85 |

**The blueprints.** The miner's came from Teladi at WLI-542 at game hour
244.89 for 1,188,650 Cr. The engine's purchase was given up after 1.1
hours: the errand ship lay at WLI-542 already, its `dockat` there ended at
once and it went back to trading. A second errand bought it at ZIR-755 at
246.47 for 130,640 Cr. 2642e19 buys at once where the errand ship lies.

**The order went in, and nothing worked it.** The fleet rule sent
`buildship` at 247.51, and the bridge's line said the wharf had taken it,
with 1 engine, no thruster, 2 turrets and the 2 shields left out. Ten game
hours later it was still in KYV-745's queue, without even a list of
missing wares, which each queued build at SCY-867 has. A wharf's
queue is worked by its ship trader (`aiscripts/build.shiptrader.xml`).
The game gives every NPC wharf one when the universe is made
(`md/inituniverse.xml`); KYV-745 had a manager, a defence officer and an
engineer, and no ship trader. d18b540 sends one from our crews, the way
the map menu's crew transfer does.

**And it had no thruster.** The ship menu takes no order with the engine
or the thruster slot empty (`helper.lua`, `allowempty`); for shields it
does. No thruster blueprint was ours, and nothing bought one, because no
thruster has an owner in `wares.xml`. The `offers` lines of game hour
244.65 show that the representatives of Teladi and the Ministry list 18
thrusters each, the generic M all-round mk1 at 130,190 Cr. 5b9a817 takes a
blueprint's sellers from those lines when `wares.xml` names none, holds
the own build until a thruster blueprint of the size is ours, and has the
bridge refuse a loadout without an engine or a thruster.

**A ninth miner bought instead.** At 249.83 the order had waited longer
than two game hours, after which a wharf counts as one that does not
deliver. A Paranid solid miner was bought at SCY-867 (249.89, 1.04 M) and
put to mining for KYV-745: the plan's ninth.

**Traders lent and never given back.** GKL-870's build storage borrowed
one of its two traders at 250.47 and another at 252.65. Each time the
fleet rule saw one trader of two and bought a freighter. The order to
trade again was skipped by the bridge, because the ship had GKL-870 as
its commander already; it did not look at the assignment. The run ended
with six of GKL-870's freighters at its build storage and two trading
(ship6-camp ended with four there). ea564ab checks the assignment, takes
up a ship found at a build storage as its feeder while a build runs and
sends it back when none does, and counts it as a trader meanwhile.

**The loss.** XPR-722, one of those freighters, was bought at 253.03, put
to trade for GKL-870 at 253.27 and shot down in Bright Promise at 257.85.
The sector read as a major threat from 248.6 (two Xenon XL, 35 S). A
third freighter was bought at 257.91, in its place.

Next, ship7b-camp, again from ship6-camp's result save rather than from
this one, whose queue holds the order without a thruster. A restart from
this save was stopped before its first cycle, to take ea564ab along, and
a second one after its first, when the missing thruster came to light.

## 2026-10-29: ship7b-camp, the first ship from our own wharf

One campaign run, rules only, again from ship6-camp's result save. The plan
of ship7-camp, plus the blueprint of the generic M all-round thruster, and
two solid miners for GKL-870, which the game had asked for since game hour
77 (an upkeep mission). It ran four of its six hours: at game hour 266.77
the game hung.

| | ship7b-camp |
|---|---|
| Game hours | 244.5 to 266.8 (22.3), ended by a hang of the game |
| Net worth | +148.8 M (6.69 M/h) |
| Net worth at cost | +141.7 M (6.37 M/h) |
| Player's money | 398.1 M to 534.8 M |
| Modules | 351 to 393 (KYV-745 185 to 217, GKL-870 166 to 176) |
| Ships | 50 to 52 (one built at our own wharf, two solid miners bought, one lost) |
| Lost | JFZ-239 (fighter), and CTT-204, which is in no save of the run, to the Xenon PNJ-650 at game hour 248.9 |

**Five starts before this one**, each stopped within minutes: to take along
ea564ab (lent traders), the thruster blueprint, 77ab597 (a purchase only
with a ship held at the seller), 41185e2 (upkeep missions in the report)
with GKL-870's miners in the plan, 197802d (cargo drones), and 503c1db.
That last one: the bridge writes one `offers` line per faction and tag, all
at the same moment, and the memory read one line per moment, so it knew the
sellers of three wares, and not the thruster's.

**The blueprints.** All three from Teladi at WLI-542, without a refusal:
the miner at 244.84 (1,188,650 Cr), the engine at 245.01 (130,640 Cr) and
the thruster at 245.12 (130,190 Cr), its seller taken from the `offers`
lines of 244.74.

**The first own ship.** A ship trader went to KYV-745 at 244.72, from the
crew of GWH-145, with a skill of 0 of 100. The order went in at 246.45,
with the engine and the generic thruster and the shields left out, and the
queue then named what the wharf lacked: engine parts. KYV-745 put out a buy
offer for them itself. ENF-175, a Teladi solid miner, came out at 255.07,
8.6 game hours after the order, with a pilot, a defence officer and an
engineer aboard, standing at Wait.

**And nothing for it to do.** At 248.5 the order had waited longer than two
game hours, after which a wharf counts as one that does not deliver. Two
Paranid solid miners were bought at SCY-867 for GKL-870, OBC-723 at 248.58
(996,968 Cr) and ESP-000 at 249.86 (991,480 Cr). GKL-870 had its two and
KYV-745 its nine (twelve, with the four of ship6-camp), so ENF-175 stood
idle to the end. An idle miner holds the purchase of the next, so it is the
first one put to work when a miner is lost. 62cf7b6 gives an order at a
wharf of ours twelve hours: it buys the parts only once the order is in.

**Upkeep missions.** The report names them per station. At the start
GKL-870 had three: Restock Cargo Drones (since game hour 76.9) and Assign
subordinate twice (77.2 and 105.1). At the end the first of the two Assign
subordinate missions was gone; the other two stood.

**Cargo drones.** At 244.72 GKL-870 was set to keep 10 cargo drones in
stock (197802d). At the end it had a buy offer for 10 drone components,
as supplies, and the game's mission to restock cargo drones was still open:
in 22 game hours the parts did not come.

**Traders.** No freighter was bought (ship7-camp bought three). Ships lent
to a build storage went back to trading when the build was done: KYV-745
ends with 24 traders for a plan of four, GKL-870 with six for two.

**Building.** KYV-745 grew by 32 modules (refined metals, silicon wafers,
spices, shield components, graphene, smart chips) and GKL-870 by 10 (smart
chips). GKL-870's plot is full: refined metals, silicon wafers, spices,
shield components, smart chips and graphene got "could not build a
construction sequence". A builder was hired 15 times, 12 for KYV-745, at
50,000 Cr each.

**Losses.** The report rated Hewa's Twin I, KYV-745's sector, a major
threat with a Xenon XL through the run. PNJ-650 destroyed JFZ-239, a
fighter, at 248.90 and CTT-204 at 248.92, and attacked CVT-715 and RBV-357.
There is no rule for a major threat yet.

**The hang.** At 12:27 real time, game hour 266.77, the game stopped. The
bridge's state messages stopped, every call to X4Mcp timed out ("timeout
waiting for game thread"), the window drew no new frame, and one core was
busy. The last cycle before it ended normally, with a save and nothing to
send; the one before that sent a builder hire, which the game refused
("AOR-401 is busy or hostile"). The run script tried three reloads, which
timed out the same way, and then waited out the 110 minutes left; the final
save did not come and the shutdown timed out too. X4 was ended by hand and
the player saves restored. The result is the last save the game wrote,
at 12:26.

## 2026-10-29: ship7c-camp, engine parts of our own

One campaign run, rules only, from ship7b-camp's end save, six hours. The
plan adds stage F's first link at KYV-745: an antimatter cells module
(hydrogen and energy cells) and an engine parts module (antimatter cells,
energy cells, refined metals), their blueprints bought first. ENF-175 took
8.6 game hours in ship7b-camp, nearly all of it waiting for engine parts,
and no station we knew sold antimatter cells. GKL-870 gets a third solid
miner. Along: 62cf7b6 (twelve hours for an order at our own wharf) and
f9f028d (a hung game ends the run). The game did not hang.

| | ship7c-camp |
|---|---|
| Game hours | 266.8 to 300.6 (33.8) |
| Net worth | +207.2 M (6.12 M/h) |
| Net worth at cost | +193.3 M (5.71 M/h) |
| Player's money | 534.8 M to 714.9 M |
| Modules | 393 to 440 (KYV-745 217 to 260, GKL-870 176 to 180) |
| Ships | 52 to 49, none bought or built |
| Lost | JCR-188 (container freighter, 277.2, "by null (Teladi Company)"), DKA-072 (281.8, by the Xenon RNG-210), CVT-715 and RBV-357 (fighters, 288.6, by the Xenon IDB-199) |

**The blueprints.** The antimatter cells blueprint took two errands. KUZ-687
was sent to RUZ-037 (Teladi), waited a game hour to dock and was released at
267.9; ZVZ-581, already in TEN-917's sector, bought it there at 268.1. The
engine parts blueprint came from YMH-359 (Teladi) at 268.7, by FEW-731.

**The modules.** The first antimatter cells module stood at 269.2, the first
engine parts module at 270.8. Then the margin ranking took over, as the plan
says for everything past its targets: KYV-745 ended with six engine parts
modules and five antimatter cells modules for a plan of one each. Over the
trade log's last 24.8 game hours KYV-745 sold 2,496 engine parts an hour at
144 Cr on average, about half of what six modules make at full run, and held
9,155 at the end. Of antimatter cells it sold 916 an hour; the engine parts
modules take up to 1,920; it held 13,145, and 38,017 hydrogen, so the
modules were not short of gas. The ranking prices a ware at the best bid it
knows (181 to 237 Cr for engine parts), not at what the station gets. The
cost is small: an engine parts module is about 2.5 M, an antimatter cells
module 0.44 M. No ship was ordered at our wharf, since the fleet plan stood
(KYV-745 had 12 solid miners for 9, 23 traders for 4), so whether a ship
now comes sooner is not measured.

**GKL-870.** Eight expansions were sent; two were built (antimatter cells,
hull parts) and six got "could not build a construction sequence"
(graphene, engine parts, smart chips, antimatter cells, silicon wafers,
refined metals): its plot is full. Its stores were too: solid 99 %,
container 94 %. ENF-175, assigned to it at the start, ended holding silicon
with "No buyers found in allowed sectors", like two methane miners at
KYV-745, whose liquid and solid stores stood at 93 and 94 %. Both stations
mine more than they process.

**The threat that was two wrecks.** The report rated Hewa's Twin I, KYV-745's
sector, a major threat with two Xenon XL through the whole run. Both were
wrecks: BZE-134 since 236.8, and PNJ-650 since 272.5, rammed by our L
freighter JEP-977. A wreck keeps its class, owner and code in the save, and
the parser counted it (0d5e457 skips it). In the 105-hour reference save
all four threats in our sectors were wrecks. Live Xenon did pass through:
the report counted four XL at one point, and IDB-199, gone from the end
save, destroyed both fighters.

**Station turrets.** KYV-745 carries 690 M gatlings, all built, all set to
attack enemies, none fired since 211.7. No hostile came within their reach;
the Xenon K wrecks lie about 155 and 165 km from the station. In the same save NPC
stations destroyed Xenon K destroyers out of the player's sight
("lowattentionattack"), so station turrets do fight there.

**Upkeep.** KYV-745 asked for a builder from 297.0 on.

## 2026-10-30: ship7d-camp, frigates from our own wharf

One campaign run, rules only, from ship7c-camp's end save, six hours. The
plan gets a third kind of ship besides miners and traders: defenders, two at
KYV-745 and one at GKL-870 (188b169). Any combat ship of ours counts; a new
one is a Teladi M frigate from our own wharf, with the M pulse laser as main
gun, whose blueprint the plan names before the frigate's so the first one
does not leave without guns. Ships we build get shields again: KYV-745 makes
field coils and shield components since ship6-camp. The rest of the plan is
ship7c-camp's.

The first try was stopped after half an hour. A ship in a wharf's bay is in
the save from the start of its build, with its code, owner and equipment,
and state "construction". QWL-354, the first frigate, was read as a
delivered idle ship of ours minutes after the order and sent to defend
KYV-745, then GKL-870; both assignments failed. Since af3344e such a ship is
on order, not ours. The run below is the restart from the same save.

| | ship7d-camp |
|---|---|
| Game hours | 300.6 to 334.6 (34.0) |
| Net worth | +191.7 M (5.64 M/h) |
| Net worth at cost | +187.3 M (5.51 M/h) |
| Player's money | 714.9 M to 905.5 M |
| Modules | 440 to 449 (KYV-745 260 to 266, GKL-870 180 to 183) |
| Ships | 49 to 45; five frigates built, none bought |
| Lost | frigates YSX-645 and DNV-141 (318.9, by the Xenon IDQ-917); container freighters ZVZ-581, WEA-247, XZQ-233 (302.1), JZI-135 (303.8), KYG-099 (305.7), WOL-202 (319.3, by the Xenon K CZJ-432), JUN-174 (323.0, by LXH-323, Scale Plate Pact), the first five by other Xenon; two craft the report types only as "ship", STQ-827 (319.3, CZJ-432) and SFE-049 (332.6) |

**The frigates.** JEP-977 bought both blueprints in one stop at WLI-542
(Teladi). The orders went in at 302.5, 303.5 and 304.5, one a game hour as
the brake allows, and each frigate left the bay about half a game hour after
its order: YSX-645 and DNV-141 to KYV-745, SFC-428 to GKL-870. Each carries
two M pulse lasers, four Teladi M gatling turrets, three Teladi M shields
(mk2) and two Teladi M engines. No frigate was bought.

**Combat.** SFC-428 at GKL-870 was attacked by Xenon S fighters from 305.1 on
and was alive at the end; the end save holds three Xenon S fighters it hit
as wrecks (GGI-765, OQG-516, UOC-086, 334.4 to 334.5, out of the player's
sight). At 318.9 IDQ-917 destroyed YSX-645 and DNV-141 in Hewa's Twin I,
where the report counted Xenon 1 M, 1 S and 2 XL; IDQ-917 is not in the end
save, so its class is not known. In the same minutes the Xenon K destroyer
CZJ-432 attacked KYV-745 and destroyed WOL-202, STQ-827 and one of the
station's three defence discs (defence 2/3 from 320.2). CZJ-432 is a wreck in
the end save. The fleet rule replaced the two frigates: orders at 318.9 and
319.9, XHY-024 at KYV-745 from 319.3 and YMW-171 from 320.5. Both were
attacked by LXH-323 (Scale Plate Pact) at about 323 and survived. The run
ended with defenders 2/2 and 1/1. An M frigate holds against Xenon fighters;
against an XL it is lost.

**What a frigate is made of.** By recipe, at average prices, the inputs of a
frigate with this loadout are worth 336 k Cr. The wares KYV-745 makes (hull
parts, energy cells, field coils, shield components, engine parts) are 83 %
of that. It buys the rest: advanced electronics, turret components, weapon
components and antimatter converters; it held 1,626, 4,087 and 875 of the
first three at the end, and wanted 5,758, 12,101 and 1,397 more (its buy
offers; an earlier version of this entry gave those as the stock). Its hull
parts stock was 0 at the end: over the trade log's last 25.0 game hours it
sold 77,918 and bought 1,727. A frigate needs 985. So by recipe the hull and the shields are ours, the engines nearly
(antimatter converters are bought) and the guns not; what left the store for
each ship is still not traced.

**No builder, as reported.** KYV-745's lost defence disc was not rebuilt. Its
medical supplies expansion waited 16.6 game hours at the end with "build
queued but no construction vessel assigned", GKL-870's two for 29.4; the
station has asked for a builder since 297.0. Every module waits on that, the
plan's too. For KYV-745 that report was wrong: a construction vessel lay at
the build from 318.3, waiting for claytronics and turret components, and the
game sent away each one hired after it (fixed in fcb69d6; see the next entry
for what the build waited on).

## 2026-10-30: proof-feed, what KYV-745's build waited on

From the ship7d-camp end save (334.6 h), 4.5 game hours under SETA, no
planner: only the commands below. Question: why did the build storage XQL-000
get nothing for 16.6 game hours, with 4.72 M on its account and SBA-383 lent
to it?

**Why the routine found nothing.** SBA-383's TradeRoutine for the build
storage had failed with "No trades found in allowed sectors". The game's
trade.find.commander.xml buys for a build storage only from a seller that
holds at least the whole demand or half the ship's free hold, whichever is
less (`totalvolume`). SBA-383 is an L freighter of 62,000 m3: 1,291
claytronics in one place. The one claytronics seller within reach, TEN-917 in
Bright Promise, two jumps from KYV-745, had 843. The two with more, ZCD-993 in
Argon Prime and XKZ-211 in Second Contact VII, are reached only through
Profit Center Alpha, Silent Witness I and Hatikvah's Choice I, all Xenon
now, and the avoid-hostile blacklist keeps the routine out of those
(lib.find.sectors.inrange.xml). The price was not it: XQL-000 bid 2,346 Cr,
the top of the range.

**The fix.** `feed_build_storages` lends the smallest freighter, and swaps a
lent one for a smaller trader of the station. On the end save it sent SBA-383
back to trading and lent CQN-712, a Paranid M freighter.

| Game hour | Claytronics still wanted | Turret components still wanted | Build |
|---|---|---|---|
| 334.6 | 1,864 | 836 | step 4 of 15, waiting for resources |
| 335.5 | 877 | 753 | |
| 336.5 | 606 | 836 | step 12 of 12, building |
| 337.6 | 222 | 836 | step 5 of 11, building |
| 338.6 | 0 | 836 | no step, no vessel |
| 339.2 | 0 | 836 | no step, no vessel |

KYV-745 went from 266 modules to 289: nine connectors, four graphene, two
silicon wafers, one each of refined metals, water, microchips, smartchips,
medical supplies and engine parts, a base structure, and the defence disc
lost at 320.2. XQL-000's account went from 4.72 M to 0.65 M. CQN-712 had 210
claytronics aboard at 335.5; NPC traders may have brought some too, and the
saves do not say which ship brought what.

**Turret components did not come.** They are for the M gatlings the bridge
puts on every module, and all 690 of KYV-745's turrets fired during
ship7d-camp (last shot 326.4 h), so they stay. The market we know sells 62.
KYV-745 holds 4,087 and wants 12,101 more for its wharf. Making that ware
sellable for our own faction only (`tradeware` and `traderule`, both
confirmed in the logbook) produced no sell offer: a station does not offer a
resource it is short of. It was switched off again before the end. At the
end one build was still listed as in progress, with no step and no vessel,
and 836 turret components wanted.

**The sector graph.** The agent's own table had gates only, so the two
sectors of one cluster were 99 jumps apart and KYV-745 reached 5 of 125
sectors; purchases, hires and repairs chose "nearest" from it. It is now
built from the game files (`gamedata.build_sector_graph`): gates and Terran
accelerators from galaxy.xml and its DLC patches, superhighways from the
cluster files. 140 sectors, every one reachable from KYV-745.

## 2026-10-30: ship7e-camp, claytronics of our own, and the loss of GKL-870

Three runs, rules only, each from the end save of the one before, from the
proof-feed end save (339.15 h) to 382.18 h. The goal was a chain of our own
for claytronics: every expansion of KYV-745 waited on them, and the sellers
holding enough sat behind Xenon sectors. All of it stands now. GKL-870, our
second station, was destroyed on the way.

| | ship7e3-camp start | ship7e3-camp end |
|---|---|---|
| Game hour | 349.19 | 382.18 |
| Credits | 907.7 M | 1,088.2 M |
| Net worth | 1,514.2 M | 1,616.2 M |
| Stations | 2 | 1 |
| Modules | 481 | 317 |
| Ships | 46 | 44 |

**The chain.** Superfluid coolant, quantum tubes and four liquid miners came
in ship7e and ship7e2. The claytronics module's save stamp says operational
at 362.2 h, advanced composites at 364.6 h, plasma conductors at 365.6 h,
advanced electronics after that. Its production line stood at "producing" in
both saves read, 108 claytronics per 900 s. The later modules took about 25
and 11 real minutes where the claytronics module took hours. Up to the end
the builds asked for at most 4,779 claytronics, against 8,631 if the line
never stopped; the rest is not traced. Stock moved between 0 and 216 and
ended at 0.

**The plan was wrong first.** The first plan had the claytronics module
before advanced composites and plasma conductors, because the plan looked at
what the factory consumes. The module's own build recipe asks 5,630 advanced
composites and 4,737 plasma conductors. Corrected at 349 h: both modules were
added. The agent's report filter (`known_stations`) hid sellers two jumps away, in Trinity Sanctum VII, and
that looked like a dead end for a while.

**Waiting on a ware the station holds.** A build storage does not buy from its
own station unless that station sells, and a station does not offer a resource
it is short of. In ship7e manual `limit` commands proved a sell limit opens an
offer for the stock above it; they were undone three minutes later and made a
rule, `own_stock` (eedfdb4). Its whole cycle ran in the game for plasma
conductors: opened, limit lowered from 529 to 143, cleared. A ware held short
alone stays short (837 plasma conductors against 2,405 wanted).

**One freighter was too slow.** 233,000 m3 was open with one M freighter and
19 traders for a plan of 4. Feeders now go by open volume (a762459), at most
four, keeping four traders trading: PAR-984, CKG-869, CQN-712 and VKB-235 ran
together, and the 4,892 advanced composites wanted were bought down to zero
in one run.

**GKL-870.** 187 modules, 8 turrets, no defence disc; KYV-745 has 696 turrets
in the same save. Its plan said field coils and then let margins decide, so
`grow` kept adding modules. Attacks were reported from 352.2 h. Its defender,
the frigate ZYO-082, was lost at 355.6 h, the station by 360.9 h, with Xenon
in Ianamus Zura IV at 6 M, 17 S and 7 XL in the last report before. The loss was
in the report as "GKL-870: not one of our stations" and was noticed only on the
scorecard at the end. Modules value fell by 68 M net.
Why it had 8 turrets where the bridge fits M gatlings on every module is not
known. Since e303f38 a station gets one defence disc per 60 modules before any
other module.

**Other losses.** 11 ships in ship7e3: 6 solid miners, 3 container freighters,
a frigate and one other. At the end Trinity Sanctum III, one jump from
KYV-745, had 12 M, 30 S and 3 XL Xenon and a Xenon station.

**Saves.** The first 22 real minutes gave a save per real minute and 4.4 times
speed. Over the whole run it was 262 cycles in 360 minutes and
5.5 times speed (ship7d-camp 5.7). The change that lets attacks wait for the
regular cycle (355ff0b) came after this run started.

**A wrong number.** The report said "short 1242448 helium", which reads as a
large shortage. `shortage/ware/@amount` is a game time: of 1,095 in the end
save none lay past the clock and the median was near it. Fixed in 6caf029.

**Next.** Stage I (ship7f-camp): discs to 5 at KYV-745, the L Ship Fabrication
Bay (`wharf_l`, licence `station_equip_lxl`, held), Teladi destroyers of our
own. `capitalship` is held from Teladi only and we know no Teladi L wharf, so a
destroyer is never bought in this plan.

## 2026-10-31: ship7f, ship7g and ship8, the first destroyers

Three runs in a row, ending with six destroyers of our own and a turret
component line. Saves: ship7f and ship7g continue each other; ship8 starts from
a save at 402.35 h in which the player went through the Paranid ally ceremony by
hand, which opened the turret components blueprint.

| Run | Commit | Game hours | Net worth | Result |
|---|---|---|---|---|
| ship7f-camp | e303f38 | 382.2 to 402.1 | no score, stopped by hand | discs to 5, L bay built |
| ship7g-camp | 3a4bd6c | 402.2 to 410.2 | +32 M | 5 destroyers in 8 game hours, ended when the player's ship died |
| ship8-camp | 0f16b55 | 402.4 to 437.1 | +162 M | 6 of 6 destroyers, turret lines 2 of 4, no station or destroyer lost |

ship8-camp in numbers: credits 888 M to 980 M, accounts +56 M, stock at market
average +12 M, modules 324 to 329, ships 35 to 40. One ship was shot down, a
solid miner, by a criminal. Two more left the fleet with no cause in the report.
That is 4.7 M of net worth per game hour.

**A run ends with the player's ship.** The harness closes the game when the
player's ship dies, and a player in a spacesuit makes the save unusable as a
start. A player can also sit in the game during a run: a ship the report showed
flying on its own turned out to be flown by hand.

**The plan's destroyers dropped by the schema.** A plan had `destroyers` before
the schema did, pydantic ignored the unknown field, and the test built its plan
by hand. `StationGoal` now forbids unknown fields, and a test goes through
`strategy.load`.

**Turret components: stock that does not reach the build.** The new line's stock
stood frozen at 1,660 to 1,708 with 12,669 wanted, because the game moves stock
to a station's build storage only above the sell limit. One hand-set `limit KYV-745
turretcomponents sell 300` moved all of it within a cycle. The rule does this now
(`own_stock`, 4957f96), but ship8 ran on the older code.

**Then the same again with hull parts.** The third turret line waited 21 game
hours on 1,785 hull parts with 51,163 in store. In the end save the station's sell
offer for them has amount 0, and the rule in ship8 took any offer as "it sells
already". Since 4957f96 it sums the amounts on offer. ship9 should show this
working. The turret line stayed at 2 of 4, so scanning arrays and the second
advanced electronics module never started. By then the turret stock had grown to
5,664 and the discs' demand was met, so its surplus went unused while TXT-319
paid 421 Cr against our 166 Cr.

**A wrong statement of ours.** The report said no expansion starts behind a build
waiting for equipment. Two did, after 7.7 and about 9 game hours, in ship7f and
ship7g, reason unknown. The report now says so.

**Crew.** Everything we built flew with three officers and nobody else; the
bridge passed an empty crew list. Fixed for new builds in 72e0e4a. The six
destroyers of ship8 stay without crew until there is a refit verb.

**Saves and speed (355ff0b).** Attacks no longer ask for a save of their own:
ship8 ran 117 cycles in 360 minutes at 5.8 times speed, against 262 cycles and
5.5 times in ship7e3, with Xenon around in both. So the change did what it was for.

**Next.** ship9-camp: `tasks/plan-shipbuilding-2026-10.md`, Raids.

## 2026-11-01: ship9 to ship9d, the first raids

Four runs on one plan: six destroyers, 24 fighters from our own wharf, raids on
the Xenon ships in Trinity Sanctum III, one jump from the station. ship9 and
ship9c were stopped by hand for a fix, ship9b died with the session. Only ship9d
ran to its end and has a score: +174 M credits, net worth +255 M to 2.18 G,
20 modules, 34.9 game hours in 360 minutes.

**What did not work first, each found by reading orders and places in the save.**
The first fighter flew unarmed: the wharf fits only blueprints we hold, so a
fighter now waits for a weapon and a shield blueprint (7cc51b1). The first raid
turned back after one cycle: "no Xenon left" was judged on the way, when we
simply did not see them yet (f3debef). The leader flew alone: five destroyers and
24 fighters were under it on paper with their old orders, because
`set_object_commander` changes no orders. `AssignCommander` created from MD does
(a34b513). A run ending mid-raid left five destroyers under the leader, and the
next read 1 of 6 (0ed95e7). At a raid's return the five read as gone for one
cycle, and a seventh destroyer went on order (2f7a279, not yet in ship9d).

**What ship9d shows.** The fleet goes together: one cycle after leaving, all six
destroyers and all 24 fighters were in the sector. Ten raids, in 28 of the
run's 114 cycles. In five of them a Xenon XL or M was seen in the sector with the fleet
there, up to 2 XL at once, and our fighters were attacked there. No destroyer and no
fighter was lost, and all seven destroyers end undamaged. Eight of our
freighters were attacked by Xenon, none lost. Trinity Sanctum III held 3 M and
6 S at the start and 1 M at the end.

**What it does not show: that we killed anything.** Paranid fight in that sector
too. The save's stats, `xenon_ships_destroyed` among them, are 0 at the start and
at the end, also with defenders and turrets at work for 490 game hours, so they
say nothing about our ships. The bridge now reports `KILLED:` lines from
`event_player_owned_killed_object`.

**Open.** The report showed "xenon 1 STATION" in the sector in five raids, up
to six cycles long, and neither the start nor the end save holds one, so it came
and went. Who removed it is unknown. UQL-278 appeared for one cycle with no orders
and was gone, not bought, built or hired by us and in neither save; cause
unknown. Six destroyers still have no crew. The XL bay needs a module entry and
a `wharf_xl` rule, not yet there.

**Next.** ship10-camp: destroyers to ten with `raid_from` 6, so raids go on
while the fleet grows, and kills in the report.

## 2026-11-01: ship10 to ship10d, what held the destroyers

Destroyers went from 7 towards 10 with `raid_from` 6, so raids went on. The first
order with crew had waited 6 hours in the queue and the second never began: every
ware in store, the game saying nothing was missing. I read the crew as the cause,
limited it to what the workforce had spare (0), cancelled the order and placed one
without crew. ship10b then ran 29 game hours with that order in the queue too, so
the crew was not it. VFM-670, the first ordered with crew, has its 24 people. The
limit went out again.

**The cause.** A destroyer of ours lay in the wharf's L bay. `buildmodule_gen_ships_l`
has a dock (`dockingbay_gen_l_inv`), and the save nests a docked ship in it: TUR-084
was there at the end of ship9d and of ship10 and through all of ship10b, on a
temporary `DockAndWait` without a timeout. VOK-360 lay the same way at the pier.
My guess at the source is `sellware` on destroyers (the regex fix in be02cda), not
proven. `release` does not take
it (`RemoveAllOrders2` with `onlypriority`) and a new default order waits behind it.
Removing the queue as the map menu does (`RemoveOrder`, new verb `undock`) does:
TUR-084 got it at playtime 1941242 and JOD-285 was started by 1941290, 48 seconds
later, after 36 hours of waiting. A rule now sends `undock` to any destroyer docked
with only a DockAndWait in its queue. It fires now and then, on other destroyers too.

**Not explained.** The 6 hours of the first crewed order: at the three saves in that
time the bay was empty. It may have held a ship between saves, or a crewed order may
wait for its crew. The next crewed orders measure that.

**Also found.** The verb first sat in the station table of the bridge, answered "no
station of ours" for two hours of game time, and no report showed it: that line and
a failed `pcall` in the dispatcher went to the logbook without REFUSED. Both are
refusals now.

**ship10b, the run that has a score** (360 minutes, 34.5 game hours): +180 M credits
to 1.64 G, net worth +220 M to 2.47 G, 39 modules, fighters to 40. Ten raids. The
first Xenon kill: MJC-551, a miner, by a fighter. One ship lost, TKN-091. No destroyer
or station lost.

**The workforce.** KYV-745 houses 500 against the 38,720 its modules can use, 1.3%,
and wares.xml gives a bonus of 0.34 to 0.53 per ware for full staffing. How output
scales with staffing is not measured yet. `habitation_tel_l` (1,000 people) is in.

## 2026-11-01: ship10e to ship12g, raids that lost and raids that killed

The raids of ship9 and ship10 flew out and back without a fight worth the name. These runs had
the fights, and most of what I had built for a fight turned out wrong in the fight.

**What you see from home is not what stands there.** ship11 left for Scale Plate Green I on the
sight of 1 station, found 4 XL and 90 S, stayed over four game hours and lost all 10 destroyers.
The rule counted XL only before launch. It now counts them on station as well and turns back at
one XL per 6 ships, and a dead ship counts as a hull of nothing. ship11c then had no destroyers
left when 8 XL came to the station, so the plan got `raid_home`: destroyers that stay, with a
purchase below that number.

**The first station.** ship12: 22 destroyers, 10 sent, 24 fighters, arrival at playtime 2012700.
I first reported no damage, from the turret count and the station's top-level `attacktime`. Both
lag. Per module there was a fight: `<hull>` on each damaged part, `state="wreck"`, an `attacktime`
per module. The rule recalled the fleet at 75% and I sent 5 back by hand. JCQ-635 (120 turrets)
fell at 2028606. 5 of 10 destroyers lost, and the Xenon were rebuilding in that sector within hours.

**`release` is not a retreat.** It removes queued orders; a ship under fire then gets a response
Attack and stays. ship12c sent 4 Paranid destroyers to patrol Trinity Sanctum III when the wharf
there was under attack. BRN-748 fell, WKU-369 fell after its release, FKS-219 and NOV-273 came out
on a dock order. NOV-273 was then released at home and fell in Trinity Sanctum III 1,100 game
seconds later: the save has it on an Attack against a Xenon solid miner, with `pursuedistance`
40000, through the gate. Its fighter flew with it, so it was not drawn back by a wing left behind,
as I first said. A defender chases past the gate, and nothing stops that yet.

**A dock order is not a retreat either.** ship12f retreated on `dockat` for all 15 (2ab467c). They
reached home at 2102863, were back in the fight by 2103603 and stayed 2,300 game seconds, until
the rule's wait ran out; VOK-360 fell there. Why they went back is unknown. `release` with `assign
defend` then brought 14 home within 600 game seconds, and did so again for the 14 of ship12g, from
2111067, with 3 XL in the sector. That is the retreat now (bf350d8). Two samples.

**The reserve rule bought what it did not need.** 14 destroyers firing back at one Xenon M at home
read as gone, because a non-default Attack counted as away, and a Paranid destroyer was bought
for 25.7 M. Ships in the home sector count now, whatever they are doing (40a045c).

**A brake on the wrong number.** The launch gate counted XL against the whole fleet, and the fleet
turns back on arrival by the ships that went: with 15 going it would leave at 5 XL and turn round
at once. It counts the ships that go now (bf350d8).

**Drone components.** KYV-745's stock went 258, 183, 117, 0 and the 29th destroyer stopped, with
`dronecomponents` missing. No known station has any for sale: the two that list a sell offer stand
at 0, both starving at their buy price. The module's blueprint was bought from Argon for about 9 M
at reputation 0.02, and its licence is the intermediate one; the module is in the plan. The
weaponcomponents blueprint needs 0.1 with Argon, so that module stays 0/1.

**The factory.** ship12e: 16 destroyers with `raid_home` 12 left at 2090000. LYB-042, the factory
that had been killing our fighters, fell at 2094070, about 3,100 game seconds after they arrived.
One destroyer lost, the other 15 at 94% hull. Then the fleet went home by itself: a killed station
stays on the faction's list as a wreck and a factory goes first, so `raid` sent it to the wreck and
the order ended at once. `raid` skips wrecks now (01b93b8, `IsComponentWrecked` from menu_map).

**The defence bases.** ship12f and ship12g sent 15 each against SDN-839 (69 turrets) and GUV-415
(76). Neither shows one damaged part at the end. ship12f stood in the sector from 2098294 to the
retreat at 2102077 and killed 36 Xenon fighters and a corvette for 8 fighters; with the time spent
after the failed retreat it lost VOK-360. ship12g lost KMN-517 to GUV-415 and turned back after
under 2,000 game seconds at 3 XL. That the swarm of S ships takes all the fire is my guess, not
measured. Against these bases, 15 destroyers killed ships and had not touched the station
when these two runs ended. That did not hold: see the next section.

**Score.** Not a scored run: restarts for fixes, and the game hours went to fleet building. At
2112729: 28 destroyers, 84 fighters, 2 Xenon stations killed, 12 of 12 defence discs, home not
attacked by a fleet. Whether home holds against one is still not measured.

## 2026-11-02: ship12h to ship12j, the bases fell and the allied sector went with them

**A correction.** The last section says 15 destroyers do not touch the defence bases. They do, given
time. The ship12h save had 15 destroyers on GUV-415 when the run ended, and ship12j reports it killed
at about 2232800, in the cycle before its own raid went out. Two runs of under 4,000 game seconds on
the station showed no damaged part, and I read that as no effect.

**The raid.** ship12j sent 25 of 40 destroyers with 15 at home. Factory YOF-841 fell at about 2238800
and defence base SDN-839 at about 2241600. All 10 destroyers lost in the run went between 2237741 and
2241295, so three Xenon stations cost 10 of 25. The retreat took 1,700 game seconds, against 600 twice
before. Why it took that long is not measured.

**What the raid did not do.** It did not protect the sector it was meant to help. With the fleet home
the Xenon overran Trinity Sanctum III: wharf SCY-867 fell at about 2271935, RYV-966 at about 2272841
and wharf HOW-875 at about 2274800. The sector went from 5 M, 6 S and 2 Xenon stations at the end of
ship12h to 20 M, 82 S, 12 XL and 3 stations at the end of ship12j. Those wharves were the nearest
source of L and XL ships for us. Whether a guard of 25 would have saved them is not measured, and it
is what ship13 tests.

**Home held.** A Xenon fleet came at about 2285000 and grew to 7 M, 12 S and 2 XL. By 2287660 one S
was left. Between saves at 2274970 and 2287849 the home sector has 34 new Xenon wrecks: 2 XL, 9 M and
23 S. Not one destroyer was lost, 33 stood at home, fighters went from 119 to 110, the station was
last hit at 2286832. The question the last section left open has one answer now: 33 destroyers with
12 defence discs hold against that fleet. It says nothing about 15.

**Stock that looked like no stock.** KYV-745's `weaponcomponents` went to 0 and the report said no
known station sold any. TS III sold them; we had no eye there, and the parser keeps stations only
for sectors with an asset or an eye. The report now says how many known stations are out of sight.
The stock of 257 at RYV-966 sat unbought from at least 2236127 and that cause is still not measured.

**The player's ship.** ship12i is useless as a start: the Falcon died, and the player sits in it
because SETA needs the controls. AI orders do not move a ship with the player at its controls, the
game's autopilot does (`autopilot STATION faction`, c342442). It held through all of ship12j,
including the fleet attack at home.

**Score.** Not scored; the game hours went to the fleet. ship12j over 22.45 game hours: credits
1,856 M to 1,914 M, net worth 2,746 M to 2,805 M, ships 210 to 163, destroyers 40 to 33, fighters 148
to 109. Three Xenon stations killed, three allied stations lost, 2 XL killed at home.

**What goes into ship13.** From the end of ship12h, before the wharves fell: two satellites per
allied sector that matters (`watch_sectors`), and `raid_guard`, so a raid stays on patrol in the
sector after its kill and comes home on strength or on an XL at home (f772f58).

## 2026-11-02: ship13 and ship13b, satellites over the allies and a guard that held

**Satellites.** ship13 stopped within minutes: the game refused both scouts with "no satellite
aboard". My count of 26 and 11 aboard came from a regex over a nested save, and it read the next
ships' blocks. A ship's deployables sit in `ammunition/available`, the parser reads them now, and a
scout bought with the default loadout has none. A player's ship does not resupply at another
faction's wharf (`interrupt.restock.xml`), so they go in the build loadout: `buyship` takes a sixth
argument, and `watch` buys one stocked scout when a sector is short (d56541f). By the end of ship13b
all 8 watched sectors have 2. Satellites are what made the guard's reports readable from home.

**The first guard.** 25 went to Trinity Sanctum III at 2232220 and stood until 2240878, about 7,600
game seconds, with no destroyer lost. New Xenon wrecks in the sector by 2241704: 1 XL, 4 M, 7 S.
Recalled at 5 XL, and KRB-182 died leaving. The leader stayed behind alone: `release` does not remove
a guard's Patrol, `undock` does (3bd5005). I sent that by hand, then bought 5 Paranid destroyers at
HOW-875, which took until about 2276622 to reach 45.

**The second guard.** 30 under DOB-223 left at 2276621 and took no loss for about 15,000 game
seconds, while the sector's Xenon ran up to 4 XL, 34 M and 79 S. Then one XL, FQG-788, killed five:
two by the save at 2292375, three more by 2293540. The recall went out at 2292613, when the count read
too many XL for 30, so at least two of the five fell after it. Against ship12j the wharves lasted
longer: SCY-867 about 25,800 game seconds, and HOW-875 is 29,000 past its old date and still there.
Whether that is the guard or the different course of this run, one run does not separate.

**After it left.** SCY-867 fell by 2297728, about 5,100 game seconds later. At the run's end
HOW-875 stands and is on the attacked list, with 2 XL, 30 M and 77 S in the sector. Paranid stations
there went from 27 to 18 over the run. The guard could not go back: the launch needs `raid_from` +
`raid_home`, 45, and 41 were home. 4 more are on order at HOW-875 and none had arrived in about
5,700 game seconds.

**Home.** 15 destroyers stayed. The home line showed at most 1 M with 10 S, and the raid's losses were
all in Trinity Sanctum III's fights. Home was not tested by a fleet in this run.

**Weapon components.** KYV-745 stands at 0 with room for 11,870. XKZ-211 sells them at 285 Cr with
492 in stock, so the eye in TS III did not bring them back. Traders trade on their own and leave no
command in the log; why they leave this ware is not measured. The ware's module stays blocked at 0.02
with Argon against 0.1, and fighters stood at 138 of 180 from at least 2288545; that the two are
connected is likely and not measured.

**Score.** Not scored; the hours went to the fleet. ship13b over 20.59 game hours: credits 1,856 M to
1,682 M, of which 9 destroyers about 231 M, so about 57 M came in. Net worth 2,746 M to 2,577 M: it
does not count those purchases back. Destroyers 40 to 41 with 4 on order, fighters 148 to 139, 2 Xenon
stations killed (YKC-022, GUV-415).

**What goes into ship14.** From the end of ship13b, with HOW-875 still standing. Two changes, one
question each. `RAID_HOLD_PER_XL` 4 against the launch's 6: a guard on its post stays until XL * 4
exceeds its number or its hull falls below 75%. What does staying cost against an XL? And
`raid_from` 25 with `raid_home` 15, so 40 can go: does an early return save HOW-875? Home keeps 15
either way.

## 2026-11-02: ship14, the guard held longer and the wharf fell anyway

**The guard.** 25 under INT-177 left at the start, at 2303900, against 2 XL, 30 M and 78 S. The first
destroyer fell at about 2352700, so about 48,800 game seconds without a loss, under mostly 1 or 2 XL.
Under the guard the sector's Xenon went as low as 3 M and 17 S. Xenon stations went from 3 to 2. It did not keep
the Paranid standing: their stations went from 18 to 12 under the guard, so a guard on Patrol does
not stop every attack on an allied station.

**What ended it.** A wave reached 4 XL at about 2353000. One XL, AEG-473, killed 6 of the 7 destroyers
lost, about one per 300 game seconds. The rule held the guard at 4 XL, as `RAID_HOLD_PER_XL` meant
it to, and the hull rule brought it home at 18 left. The guard went home with its leader, so 3bd5005
works unattended. Staying cost 7 against 5 in ship13b, for a guard three times as long; whether the
longer stay came from the rule is not separate from the smaller waves before it.

**After it left.** HOW-875 was last listed at 2366532, about 12,000 game seconds later. The 4 destroyers
ordered there in ship13b were never delivered. The order sat for 68,000 game seconds. Money rose 61 M
around that time and I have not established why, so what the undelivered orders cost is not known. At
the end Trinity Sanctum III has 10 XL, 2 L, 39 M, 118 S and 6 Paranid stations, and home is quiet.

**The brake.** This is the finding that matters most for growth. The fleet is 34 destroyers and 125
fighters with no way to add to them. Our own destroyer and fighter wait on `weaponcomponents` (0 in
store, the build's `missing` says so), and no known station has real stock: of the 5 that list them
four stand at 0 and TNM-909 has 313. The module's blueprint needs 0.1 with Argon, we have 0.02. The
only L wharf known now is Argon's CXY-258, and we hold no Argon capital ship licence. Fighters can still
be bought at the M wharves.

**Two hand steers that did nothing.** Opening 29,809 `hullparts` for sale: a price rule set my 220
back to auto within a cycle, and at 151 nobody took them for 29,000 game seconds while WAC-778 pays 299.
Traders do not move this by themselves. And `haul` on JZQ-086: the ship was a trader, the buy order sat
behind its trade queue and was never reached in 24,000 game seconds. Hauling needs a ship with no
other job.

**A market next door.** XPP-596, in our own sector, buys what we hold in stock: `advancedelectronics`
at 1,013 Cr, `antimatterconverters` at 353, `fieldcoils` at 411, `engineparts` at 181, `hullparts` at
208. It wants about 10 M Cr of it, and it is not being delivered. Not tried yet.

**Score.** Not scored. Over 22.1 game hours: net worth 2,577 M to 2,609 M, credits 1,682 M to 1,728 M,
ships 202 to 180, destroyers 41 to 34, fighters 139 to 125, failing 2 to 6.

## 2026-11-02: a new game, from a custom start

**Why.** The old game's fleet could no longer grow, its allies were falling and part of its station
came from the free modules of October. So a new universe, set up by hand, and no longer comparable with
the 1.82 M per game hour of the old one.

**The start.** The creative custom start, saved at 13 game seconds, then edited: 1,000 M Cr, 86
blueprints including the weapon components module, the SETA item, 0.1 with Argon, Terran, Paranid and
Teladi with their licences, and Argon Prime's 8 stations known so that a wharf could be found. The game
kept all of it through a load and a save. `edit_save.py` gained reputation, licences and known sectors.

**The map.** Scouts come first. A plan's `scouts` buys them at once, and each goes to its own unknown
sector, because the game's explore sent four into one sector side by side. `watch_known` gives every
sector with a known station two satellites. After 13.4 game hours: 361 stations known in 51 sectors, 81
satellites in 45 sectors, 3 scouts lost and replaced. Xenon so far: 8 XL in three sectors and 3 stations.

**The first station, from nothing.** The old game always started from a plot, so `newplot` is new:
ReserveBuildPlot and payment at the map menu's price. An 8 km plot in Argon Prime cost about 0.93 M, and
growing it to 20 km about 13.6 M. The rules then did the rest with no help: a dock, a manager, freighters
and a budget. After 10.5 game hours: dock, 2 energy cells, refined metals, graphene and hull parts.

**What held it up.** Hired vessels: each build step waited for one, and four came and went. An own
XL builder from Argon's wharf removed that wait, and a step went from about 6,000 to 4,300 game seconds.
Bought miners stood idle until a module wanted what they mine, since the plan bought them first; the
rule was right to leave them. And the user put the player's ship on Explore during a run, which took the
player out of the seat and SETA with it, so a slow run has that as its first suspect.

**Score.** Over 13.4 game hours: net worth 1,000 M to 952 M, credits to 940 M. Not yet earning.

## 2026-11-03: start4 to start8c, the chain to advanced electronics and destroyers of our own

Seven runs in a row from the new start. start5, start8 and start8b were stopped by hand to restart
with fixes.

| Run | Game hours | Result |
|---|---|---|
| start4 | 13.4 to 17.2 | plasma conductors, the reputation 0.1 with all four factions held |
| start5 | 17.2 to 28.6 | 7 destroyers and 4 frigates at home, bought at Argon's wharfs; first disc |
| start6 | 28.6 to 50.2 | discs 4 of 4, weapon components, the chain to advanced electronics, L bay |
| start7 | 50.2 to 69.8 | default build method; production stood still on a full store; large stores |
| start8 | 69.8 to 71.1 | the first destroyer from our own bay, once the bay had a ship trader |
| start8b | 71.1 to 78.6 | traders kept home while the stores have room; destroyers 15 of 16 |
| start8c | from 78.6 | six destroyers guard Hatikvah's Choice I, ten stay home |

**Ships from a faction.** A capital ship needs the faction's licence, not only an ally's standing:
`reserve_purchase` now takes either. Ten destroyers were ordered at EBF-432 for about 21 M each, and
the frigate's cap went to the reserve's 40 M, as one costs 4.5 M at XFW-633. Three destroyers waited
there on advanced electronics, for about ten game hours.

**Our own vessel was called once.** `find_builds` marked the XL builder when it sent it and never
cleared the mark, so the first disc waited 8.9 game hours beside an idle vessel. The mark now clears once
no build waits; from then on every disc and module got the vessel without help. A frigate paid for sat
at the wharf because destroyers had already filled `defenders`; an idle warship now guards home past the
plan's number.

**Advanced electronics.** In the known stations the galaxy asked about 339,000 and offered 235, at
1,450 Cr; turret and weapon components were short too. The plan went on past weapon components to
silicon wafers, microchips, quantum tubes and advanced electronics, which our graphene and coolant
already feed. The whole chain stood at 38.3 game hours, with all twelve production lines running. The
build storage had bid 853 Cr for it against a market at 1,310, yet it was delivered; the bid was not
what held the discs up.

**An L bay of our own, and the Terran method.** The L Ship Fabrication Bay was built at 40.8 game hours,
and the first Teladi destroyer ordered from it. It waited 9.3 game hours on metallic microlattice: a
Terran character makes Terran the global build method, and no module of ours makes that ware. New verb
`buildmethod` sets a station and its build storage as the map menu's build rule does, and a rule sends
it once per station. The queued build changed with it, without being cancelled: it now waits on hull
parts, field coils, shield components, drone components and smart chips.

**Score (start6).** Net worth 719 M to 902 M over 21.5 game hours, but most of that is the modules
valued at market: at cost it went 711.8 M to 707.6 M, and credits fell 25 M. The station holds 9.4 M in
its own account, above the 6.4 M the rule set as its top. Ships lost: two scouts, one to a Xenon
ship and one to the Scale Plate Pact. No station or warship was lost.

**Everything stood still on a full store (start7).** At 59.6 game hours every production module of
ZLR-942 was idle: the container store at 96%, the solid at 100%, the liquid at 94%, and one trader
hauling. The player saw it first, in the station's logical overview. With the plan's targets standing,
the margin ranking had added nine antimatter cell modules in four game hours: it prices the output at
the best bid we know, 310 Cr, and never saw that nothing took the cells. A margin-driven expansion now
skips a ware whose store is full. The plan put a large container and a large solid store first and four
traders; production ran again within one check. A full check of production per module, stores, offers,
miners and traders now runs every 15 cycles, read from `<production state=...>` in the save.

**Our destroyer waited for a ship trader.** The queued Teladi destroyer sat 27 game hours with every
ware in store. A wharf's queue is worked by its ship trader, and the rule sent one only to a station
with the M wharf; ZLR-942 has only the L bay. Sent by hand at 69 game hours, and the rule now counts the
L bay. NSL-517 left the bay at 70.9 game hours, the next at 71.7, and the bay built on by itself.

**Freighters lost on the way to a buyer.** Eight freighters and four miners were lost in start7 to
start8b, to Xenon, Kha'ak and the Scale Plate Pact. `focus_fleet` aimed every trader at the biggest
pile whether or not the store was full, and a focused trader goes wherever pays most: energy cells for
24 Cr in Silent Witness XI, through Hatikvah's Choice I next door, where a Xenon XL destroyer and
fighters sat. With room in every store a trader now stays on the station's routine. OQO-648 was lost
there even so, so the plan went to 16 destroyers, and six guard Hatikvah's Choice I with `raid_guard`
while ten always stay home. The guard left at 80.1 game hours.

**Scouts held the traders back.** Lost scouts are replaced about once a game hour, and every scout
purchase set the one-purchase-an-hour gap, so the traders stood at 1 of 4. Scouts now hold no other
purchase, as fighters and destroyers did not already.

**Antimatter cells.** Nineteen antimatter cell modules stand idle: the station offers 25,000 cells at
121 Cr, the game's floor, with 310 the best bid we know. A ware we offer at the floor price is no longer
expanded. The modules are paid for; what sells their output is open.

**Score (start7).** Net worth at cost 707.6 M to 681.0 M over 19.7 game hours, credits down 47.8 M.

## 2026-11-03/04: start8c to start8k, the guard, the Pact and growth that stopped

Nine runs in a row from the end of start8b. start8c to start8j were stopped by hand to restart with
fixes; start8d ran one cycle.

| Run | Game hours | Result |
|---|---|---|
| start8c | 78.7 to 89.1 | six destroyers guard Hatikvah's Choice I; two lost there |
| start8d | 89.2 | named sectors avoided; a guard leader left on its post called off |
| start8e | 89.3 to 90.2 | two destroyers lost to the Xenon defence platform MDR-660; the guard stays home |
| start8f | 90.3 to 93.6 | a focused trader carries only the wares of a full store |
| start8g | 93.8 to 110.5 | MDR-660 fell beside a Terran fleet; a second raid lost seven; four docks |
| start8h | 111.1 to 113.7 | from a save with the Terran relation set on both sides |
| start8i | 113.9 to 120.9 | scouts, freighters and miners flee when attacked |
| start8j | 121.0 to 124.9 | the floor price as a band; a module waiting for inputs holds the next |
| start8k | 125.0 to 147.6 | nothing built beyond the plan; the guard went out at 20 and came home whole |

**The guard and the defence platform.** Six destroyers went to Hatikvah's Choice I with `raid_guard`
at 80.1 game hours and lost two there in start8c. A guard holds against a Xenon XL at four destroyers
each, but MDR-660, a Xenon defence platform, is a station and not an XL, and two more fell to it in
start8e. The plan kept the guard home after that. A guard leader from the earlier run was still alone
on its Patrol order: `release` leaves a Patrol in place, so a destroyer posted with no raid in memory
is now undocked and comes home.

**MDR-660 fell beside the Terrans.** At 97 game hours a Terran carrier fleet, Tokyo WMP-072 with about
79 S, 12 M and 2 L, was clearing Hatikvah's Choice I. Seven of our destroyers joined that fight and the
platform fell at about 101 game hours without a loss.

**A raid that chased its target lost seven.** The next raid followed the Xenon out of Hatikvah's
Choice I into Tharka's Cascade XV, where 5 to 7 Xenon stations and up to 6 XL stood, and lost all
seven destroyers there. Its state still read "settling", which is not home. A raid that has arrived
now comes home as soon as one of its ships is in a sector off the shortest way between home and the
target.

**The guard came home from three XL.** With twenty destroyers in start8k six went back to Hatikvah's
Choice I at 138.6 game hours and held it for about eight game hours without a loss. When a Xenon
station and three XL stood there, at 12 destroyers needed against six, the guard was called home
whole. A sector too strong stays off the list for 20 game hours only where we have no eyes; our
satellites watch Hatikvah's Choice I, so what they see counts, and start8l sent the guard again at
149.2 game hours with one XL in sight.

**Freighters and the Scale Plate Pact.** The Pact, neutral to us at -0.003, killed six freighters from
start8f to start8k, one in start8k's 22.6 game hours. The game's attack and kill events name no sector,
so where they were caught is not known. The station's traders and miners keep out of Hatikvah's
Choice I since start8d, and since start8g out of five more: Silent Witness XI and XII, Heretic's End,
Sacred Relic and Void of Opportunity. Five of the six were lost after that. New verb `avoid sector`
adds a sector to the game's own blacklist for hostile sectors. Since
start8i scouts, freighters and miners answer an attack by fleeing (`shiprespond`, 21 ships); warships
keep their own answer. The freighters carry two shotgun turrets and an M shield.

**The Terran relation.** The faction list showed Terran at -15 while our side stood at 0.1. A relation
has two sides, and the faction's own entry toward the player was -0.032. `edit_save` now sets both;
start8h ran from a save edited so, with the player's consent, and the player saw it right in the game.

**Docks.** At 106 game hours 14 of the 16 freighters and miners waited in Argon Prime to dock: the
station's one dock has a single M bay. Three more docks stood at 110.2 game hours.

**Growth that did not sell.** The margin ranking kept adding modules past what the plan names: 20
antimatter cell, 13 energy cell, 11 water and 8 silicon wafer modules stand. It skips a ware whose store
is full or offered at the floor, and the floor never matched: the station asked 121.6 against a floor
of 121, so the floor is now a band of 5% of the price range. A ware whose lines all wait for storage,
or any line for inputs, gets no new line. Even so the plan now says `free_growth: false`, and a station
builds only what the plan names. At 147.6 game hours 20 antimatter cell and 11 water modules stood
idle with 15,400 cells offered at 121 Cr against a best bid of 310 and 16,100 water at 32 against 81.
The traders report "No trades found in allowed sectors" at times. What moves the output to the buyers
we see is still open.

**Score.** 78.7 to 125.0 game hours: modules 75 to 142, their cost up 44.5 M, credits down 88.0 M, net
worth at cost 654.4 M to 626.8 M. start8k, with nothing added: credits up 24.7 M, the station's account
up 13.2 M, net worth at cost 626.8 M to 663.7 M over 22.6 game hours. Lost from start8c to start8k:
eleven destroyers to Xenon, seven freighters (one to Xenon, six to the Pact) and fourteen scouts.

## 2026-11-04/05: start8l to start9c, Silent Witness XI and XII claimed

Eighteen runs in a row from the end of start8k, most stopped by hand to load a fix or a request of the
player's.

| Run | Game hours | Result |
|---|---|---|
| start8l, 8m | 147.6 to 176.0 | the guard back in Hatikvah's Choice I with one XL in sight |
| start8n | 176.2 to 182.4 | a guard on its post is topped up from home to the plan's number |
| start8o | 182.5 to 193.2 | a carrier with 40 fighters and an auxiliary go with the guard |
| start8p | 193.3 to 196.7 | the Pact made an enemy in the save; six frigates patrol the trade route |
| start8q, 8r | 196.8 to 219.9 | the guard clears the Pact's stations and build storages in Silent Witness XI |
| start8s to 8v | 219.9 to 293.4 | XI claimed at 223.4 by ZXX-974's L bay; its plan built by 292.6 |
| start8w | 293.5 to 299.5 | the carrier guards ZXX-974 after three freighters were lost near it |
| start8x, 8y | 300.1 to 305.8 | the guard in Silent Witness XII; both L bays build destroyers; the Pact's base destroyed |
| start8z | 305.8 to 324.9 | the Kha'ak hive and four of its five weapon platforms destroyed |
| start9a to 9c | 324.9 to 337.7 | third station GZI-064; Silent Witness XII claimed; the guard hunts |

**Claiming a sector.** A sector goes to the faction with a claiming module there: the game's own
ship-building modules for S, M, L and XL, equipment docks, claim defence modules and trade stations
carry `<ownership claim="1"/>`. Our S/M dock area does not. ZXX-974's L bay made Silent Witness XI ours
at 223.4 game hours, GZI-064's made Silent Witness XII ours at about 337.7. The plot in XII cost
nothing: the sector had no owner and so no control station to pay.

**What the save holds is not what the player knows.** The raid on Silent Witness XII was planned from
the whole save, and nothing there was known to the player (no `knownto="player"`): `raid` attacks only
known stations, so the guard of 20 patrolled beside the Kha'ak nest for half a game hour. Explore
searches only a sector's core (`order.move.recon`, the blind tourist), and the Pact's base lay outside
it. New verb `moveto` flies a ship to 25 km of another faction's station, inside a ship's 40 km radar
(`libraries/defaults.xml`); at 10 km the base shot the scout down, after it was on the map. A scout
that flees when attacked lost its order on the way to the hive; the guard itself went and put the
hive and a platform on the map.

**An attack takes the guard's Patrol with it.** After the Pact's base fell the guard of 20 flew home
on its default order: the Attack put in front of its running Patrol had removed it. A guard now always
asks with its Patrol behind the attack, and one without a Patrol is told again at once. A priority
order goes behind another priority order, not in front of it: `moveto` waited behind an Attack that
had not hit platform XYU-174 since 302.8 game hours, why is not known. The raid went back to the Pact,
so the guard no longer asks for that attack and only patrols.

**Hunting.** Patrolling did not stop the ships that shot our freighters: the Pact's armed scout
QRJ-271 killed five in Silent Witness XI beyond the carrier's radius, and bombers kept coming into XII.
New verb `hunt` gives one of ours an Attack on a ship of another faction; QRJ-271, two Pact destroyers
and bombers and two Fallen Families destroyers fell to it, each in a cycle or two, with no loss. Rule
`hunts` now sends up to six of the guard after a ship that attacked a freighter, miner or scout of ours
in the guard's sector or on its way there, once per attacker, Xenon excepted. MD writes the attacker's
faction id behind its name for it. An Attack reaches a ship assigned to a station; a Patrol given to
the carrier, assigned to ZXX-974, did not stay.

**Field coils.** The nine field coil lines at ZLR-942 waited for plasma conductors most of the time:
nine need 2,160 an hour and 2,322 quantum tubes, one plasma conductor line makes 176. The lines ran on
what the traders bought. The station's container storage held some wares at their share while 49 to
61 of its 75 lines waited for room; a stock limit per ware (`SetContainerStockLimitOverride`) is not
in the bridge yet.

**Score.** 147.6 to 337.7 game hours: credits 527.7 M to 659.6 M, net worth at cost 663.7 M to
877.4 M, two stations added and two sectors claimed. Lost, by the fleet's count of ships gone: 38
freighters (most to the Pact, some to the Fallen Families), two miners, two frigates, four scouts and
one destroyer.

## 2026-11-05/06: start9d to start9n, the Kha'ak cleared from XII, a review, and a yardstick

**What happened.** The guard of 30 took Silent Witness XII from the Kha'ak a second time (a hive,
six weapon platforms and a nest rebuilt there after the claim, put on the map with `moveto`), and the
reserve took the nest in Silent Witness XI. The fleet's home moved to ZXX-974; ZLR-942 in Argon
Prime, which the Argon now defend, keeps a reserve and the route patrol of its own. Fighter patrols
in Second Contact II and Silent Witness XI were tried as single fighters (slaughtered), as groups,
and as groups led by frigates (four frigates lost); light ships were all the losses there.

**Bugs found by running.** A guard leader without its Patrol was not recognised at a restart, and
its 30 were assigned home (start9k); a second station with destroyers called the guard to itself;
`fleet` counted raid ships at every station; four piers were ordered for one station across two
runs, which looked like a build that took no vessel; Attack orders of ships under a leader dropped
when the target was in another sector. Each fixed with a test.

**The review.** Four reviewers read the repository and the run data (tasks/plan-2026-11.md has the
findings). Since start8p Pact kills of our freighters and miners rose from about 0.08 to 0.23 a game
hour; no destroyer was lost since start8m; miners filled full stores while our mining raises the
Kha'ak's activity; a run started with empty memory and rules met on the same ships. The plan that
followed: a foundation (dry run with checks before every run, memory carried across runs, one owner
per ship per cycle, rules reloaded between cycles), the losses stopped (miners parked, hunts from
the reserve, destroyers leading patrols), a yardstick, then campaigns against one faction at a time.

**The yardstick, start9n.** 426.9 to 448.4 game hours with the plan frozen and no hand command: net
worth at cost +5.36 M a game hour, credits +3.87 M; 6 fighters and 2 frigates lost to the Kha'ak,
no freighter or miner lost; 30 Kha'ak, 2 Fallen Families and 1 Pact ship killed; 46 of 94
production lines running at the end.

## 2026-11-06/07: start9o to start9w, saves that stopped, sell runs, Hatikvah's Choice I opened

**What happened.** The first campaign began: the Pact, Heretic's End first, in its scout phase. Plan
1.5 was measured (tasks/plan-2026-11.md): station managers priced refined metals at 92 to 98 Cr while
buyers paid 200 and more, and Silent Witness and Argon Prime were not connected at all outside the
avoided sectors. Both remedies were built: sell runs, freighters of our own that take a ware from a
station to a buyer, and Hatikvah's Choice I taken off the avoided list with four of ZLR-942's
destroyers patrolling it.

**Saves that stopped.** start9o wrote its last save twelve minutes in and ran four hours without one;
start9p did the same. The bridge now sends `save=` in its state line and, when the game refuses a
save, the reason (`lua unsaved cutscene`). The reason was ours: a MoveWait that arrives with no next
order has the pilot say "Awaiting orders", played as a cutscene on the monitor, and five sweeping
scouts on legs of a few seconds kept one playing without a break. A Wait now stands behind each leg;
start9q then had no refused sample in its first 135. The run reloads its newest save after fifteen
minutes without one.

**Sell runs.** Five restarts to learn what the game takes (tasks/lessons.md L8k): no Single trade
order above the hold, none at a station of our own, and no SingleSell to a foreign buyer at all. A
trade goes as the map menu's does, the station's offer queued (`GetTradeList`,
`AddTradeToShipQueue`), one leg at a time by what is aboard. Of nine buyers tried, eight had their
offer for refined metals closed to our ships, which the save does not show; the one open bought
2,586 in the first hour. The rule now keeps, across runs, which buyers took a sale and which were
closed.

**Other fixes.** Each destroyer ZXX-974's bay built for its own number went to ZLR-942, first in the
plan, because an idle warship past a station's number stayed at the first station that looked. The
hunts rule now also hunts an attacker of ours one jump from home. Sweeps of our five sectors ran 43
game hours and none was ever done, so no scout came free for Heretic's End; a sector now counts as
swept after six game hours.

**Losses, start9q to start9v.** Freighters: JUJ-718, VVH-982, DZK-868 and UNH-883 to the Pact in
start9r, ICK-764 to the Pact in start9s, JQZ-336 to Duke's Buccaneers in start9v. The frigate PAX-426
and the fighter COQ-984 to the Kha'ak. Four ships of no known type left the fleet without a
destruction report. The Pact's SHH-527, which shot two of them, was hunted by hand from the home
reserve.

**Score, start9v.** 469.7 to 491.4 game hours: credits +3.86 M a game hour, against +3.87 M in the
yardstick; net worth at cost +3.95 M, against +5.36 M, with stock down 2.3 M and four ships added.

## 2026-11-07/08: start9w and start9x, Heretic's End taken

**start9w (491.4 to 512.8 game hours).** With the sweeps capped, the campaign went from scout to
siege, claim and base in one run: both Pact stations in Heretic's End (KRU-287 and GVZ-136) fell,
a plot was bought and VJA-376 began. The price was eight destroyers, all to KRU-287. With no raid in
memory, `raids` takes over a guard left on its post on the way, and it took MLX-818, leading the
patrol of Hatikvah's Choice I on the way to Heretic's End, for the guard's leader; the 30 were put
under it, and later EZE-828's route patrol was taken the same way. A sector patrol or the route is
no longer a candidate (d9a8579). Five freighters were lost as well, to the Pact, the Free Families,
the Vigor Syndicate and Duke's Buccaneers. The run was not watched for three hours while a question
to the player waited for its answer. Credits +2.76 M a game hour, net worth at cost +2.74 M.

**Where the freighters die.** The game's own logbook says it (category upkeep, "was destroyed.",
with the sector): 118 freighters and miners lost in the game, 52 since 361 game hours. The sectors
with a loss since 456 game hours or two since 361 that are not ours or patrolled joined the avoided
list: Profit Center Alpha, Black Hole Sun IV and V, Eighteen Billion, Scale Plate Green I, Trinity
Sanctum III and VII, Heart of Acrimony II and Morning Star IV. Heretic's End came off it, for the
base's traders and miners.

**start9x (512.8 to 535.1 game hours).** No ship lost. The base stood, its garrison held Heretic's
End for ten game hours, and the campaign counts it taken and is scouting Nopileos' Fortune VI. Net
worth at cost +3.19 M a game hour and credits +1.35 M, with fifteen modules and eight ships bought.

## 2026-11-08/09: start9y to start10a, Nopileos' Fortune VI taken

**start9y (535.1 to 557.3 game hours).** The guard went to Nopileos' Fortune VI under IVB-214, a
destroyer of the home reserve, so the leader fix held; it destroyed the Pact's OTX-938, a plot was
bought and DBA-060 began. One freighter lost, to a Pact bomber that the hunts rule's ships then
killed. Net worth at cost +3.92 M a game hour, credits +3.74 M.

**start9z (557.3 to 578.6).** No module was built in the whole run: DBA-060's running build had
all its modules standing and waited from game hour 549 for 76 turret components that no seller
brought, and the game does not cancel such a build. The campaign waited in its base phase for the
template's four defence discs; it now goes on with the claim and one disc (4568d58). Silent Witness
XII, left to a patrol of three while the guard is out on the campaign, had Kha'ak back; the patrol
became five. One freighter lost, in Second Contact VII, which joined the avoided list. Net worth at
cost +3.90 M a game hour, credits +4.24 M.

**start10a (578.6 to 596.4).** The base went on, its garrison held Nopileos' Fortune VI for ten
game hours, and the campaign counts it taken and is scouting Loomanckstrat's Legacy. Two fighters
lost to the Kha'ak. Net worth at cost +4.51 M a game hour, credits +2.87 M, station accounts +27.9 M.

**Ships that are not ships.** Most runs list ships of no known type leaving the fleet without a
destruction report, up to 28 in start10a. The ones still in a save are a generic M corvette and XS
distress beacons: objects that come and go, not losses.

## 2026-11-09: start10b and start10c, the guard lost at Loomanckstrat's Legacy

**start10b (596.4 to 616.1 game hours).** The siege of Loomanckstrat's Legacy began at 599.2 game
hours. One freighter and two fighters lost. Net worth at cost +4.20 M a game hour, credits +5.37 M.

**start10c (616.1 to 635.7).** The guard of 31 destroyed five of the Pact's stations in
Loomanckstrat's Legacy without a loss (WWF-212, WPZ-699, OIB-795, WKZ-872 and JQS-891) and then
turned on the sixth, the Anarchy Port ZTU-930: 30 defence modules, 467 turrets, 204 shield
generators. JQS-891 had 5 defence modules and 21 turrets. ZTU-930 killed all 31 within 450 game
seconds, at 629 game hours, faster than any rule could act on a loss. The sector came out of the
plan, which reset the campaign to its first sector; a sector the plan drops is now skipped with what
was taken kept (65cf7fa). And the campaign passes by a sector where one of the target's stations has
more than 10 defence modules, calling a guard under way home (0eefea6): the save lists the modules
of every station we know, also out of sight. The campaign scouts Moo-Kye's Revenge, two Pact
stations with 5 defence modules each. Lost besides: two freighters to the Pact's EYB-436, one of
them on a sell run sent before Pious Mists IV joined the avoided list, a miner and five fighters to
the Kha'ak. Net worth at cost +3.14 M a game hour, credits +2.86 M.

**start10d (635.7 to 657.5).** The campaign scouted Moo-Kye's Revenge and stands in its siege,
waiting for 30 whole destroyers at home: ZXX-974 had 18. Seven freighters, two miners and three
fighters lost, all in our own sectors and all to the Kha'ak but three freighters: Silent Witness XI
and XII, and the two miners in Second Contact II Flashpoint. Silent Witness XI's patrol stood in its sector, three
destroyers, four frigates and twelve fighters, and went to five destroyers. The Pact's LCV-670
shot three freighters in Silent Witness XII and no hunt went: `hunts` ran only while a guard was
out. With none, it now hunts round the guard's home, and a sector patrol's destroyers hunt in
their own sector, its leader kept on its Patrol (cddab74). Net worth at cost +1.79 M a game hour,
credits +1.72 M, the weakest run since start9w.

**start10e (657.5 to 679.5).** No freighter lost. Two miners lost to the Kha'ak in Second Contact
II Flashpoint, four there in two runs, so its patrol went to five destroyers; a fighter and a
frigate of Silent Witness XI's patrol lost to the Kha'ak as well. The run ended with the route
patrol on Patrol at its first stop, Second Contact II Flashpoint, and the dry run before start10f
put all twelve under that sector's patrol, an invariant the dry run flags: `fighter_posts` ran
before `route_patrol` could take the route back. It runs first now, and takes over no sector
patrol's ship (8e894e9). Net worth at cost +3.71 M a game hour, credits +3.46 M.

**start10f (679.5 to 701.5).** The route was taken back at the start and went on, and the first
hunt with no guard out went (two of a patrol after the Pact's FEH-009). No freighter lost; a
miner in Second Contact II Flashpoint, the fifth there in three runs, and three fighters, all to
the Kha'ak, while PTJ-289 of that sector's patrol destroyed a Kha'ak nest. The run ended well and
then failed: the scorecard parsed both saves beside a running X4, the machine was out of memory
(WinError 1455, a Windows service holding 10 GB), and the check whether X4 still ran failed, so no
player save was put back. The game was closed and autosave_01 restored by hand; the scorecard now
comes after the game is closed (951e80c). Net worth at cost +3.49 M a game hour, credits +3.75 M.

**start10g (701.5 to 721.3).** No ship lost, the first run without a loss since start9x. A hunt
went after the Pact's bomber DJT-660 and the patrol of Silent Witness XI killed it, and a Pact
scout fell as well. GZI-064's hull parts waited on graphene now and then, 46 in store with room
for 992, while ZLR-942 offered 1,174: a matter of hauling, not of a stand-still. The scorecard came
after the game had closed, and no player save had changed. Net worth at cost +3.46 M a game hour,
credits +3.24 M.

**start10h (721.3 to 743.7).** One miner lost to the Kha'ak in Second Contact II Flashpoint, the
sixth there in four runs; the sector stays open, since keeping traders out of it as well would cost
the trade more. Net worth at cost +3.23 M a game hour, credits +3.46 M.

**start10i (743.7 to 765.4).** The Kha'ak had a hive (QVH-727) and a weapon platform back in
Silent Witness XII, and three freighters and two fighters were lost there, one freighter to the
hive itself. Silent Witness XII's patrol of five destroyers then destroyed both, so a patrol does
take on Kha'ak stations in its sector. Found on the way: from start9x to start10c two new
destroyers a run, built in Heretic's End and idle, went to VJA-376, whose plan names none: past its
number a station still takes an idle warship in its own sector. Thirteen stand there; none went
since start10d. Net worth at cost +3.52 M a game hour, credits +3.86 M.

**start10j (765.4 to 787.2).** The Pact's bomber AYN-925 shot two freighters in Hatikvah's Choice I
past two hunts, so its patrol went from four destroyers to six; another freighter, a sell runner,
fell to the Pact in Silent Witness XII. The Kha'ak built a new nest, SUJ-611, in Second Contact II
Flashpoint and took a miner and two fighters there, the seventh miner in that sector in five runs.
Two player autosaves had changed and were put back. Net worth at cost +3.53 M a game hour, credits
+2.98 M.

**start10k (787.2 to 809.6).** The Pact killed two freighters, one in Silent Witness XI and one in
Morning Star III, the one way into Heretic's End; VJA-376 now has a plan of its own, the base's
template with three of its thirteen idle destroyers patrolling Morning Star III, and they went.
Two more miners fell to the nest SUJ-611 in Second Contact II Flashpoint, nine there in six runs.
A sector patrol's leader is told `raid ... stay`, which goes for Xenon stations; it now names the
Kha'ak when a Kha'ak station there is known (dd88bba). SUJ-611 is not: the save gives it no
`knownto`, and the bridge's raid targets known stations only. Net worth at cost +3.12 M a game
hour, credits +2.92 M.

**start10l (809.6 to 831.4).** One freighter lost, to the Pact in Atiya's Misfortune I, a sector
with no loss before. Morning Star III's new patrol held, and no miner fell in Second Contact II
Flashpoint. The red hammer with a count beside a station in the game's property list is its
fleet units, the ships the game rebuilds when lost; it is red when one of them has a build issue
(no wharf, ship or equipment unavailable, or paused), by the map menu's own code. Net worth at
cost +2.84 M a game hour, credits +3.40 M.

**start10m (831.4 to 853.5).** No ship lost, the second such run since start10g. A hunt went after
the Pact's TRH-298, and MTQ-773 shot down the Pact bomber YCQ-924. Net worth at cost +3.21 M a game hour, credits +3.52 M.

**start10n (853.5 to 875.2).** No ship lost. The red fleet units in the player's property list led
to it: the game rebuilds lost ships for their fleet units at our own wharfs, and three Phoenixes
had waited at ZXX-974's L bay since 629 game hours, 240 game hours, on hull parts and shield
components. ZXX-974 made hull parts and sold them down to the 2,000 `wharf_sales` keeps, and
offered 263 for shield components while the sellers asked 113 to 209 in sectors our traders
avoid. The agent counted those three as on order. `wharf_supplies` now feeds a ship stuck at our
own wharf past an hour: the station keeps back 15,000 of what it makes and outbids the dearest known
seller for what it buys (13bd1b1), the price set every cycle, since `executor.automatic_prices`
hands back each price not set in the same cycle (6ca7eaa). By the end of the run two of the three
were built and the third lacked nothing; hull parts at ZXX-974 went from 2,342 to 10,214. A
destroyer at DBA-060's wharf, whose station makes nothing, still lacks eleven wares. Net worth at
cost +3.07 M a game hour, credits +2.99 M.

**start10o to start10s (875.2, again).** start10o lost the player's own ship, RTV-678, to the
Kha'ak ARJ-114 in Silent Witness XII after 1.5 game hours, and with the player in a spacesuit the
run ended. RTV-678 had sat in the open by GZI-064 since start10n. The rule that shelters the
player's ship had sent nothing since start10a: it took the plan's first entry for the station, and
that is START, a placeholder. Its autopilot to a station stops short besides: in start10p RTV-678
flew 4 km toward GZI-064 and stood still 5 km out. Each next try began again from start10n's end.
A docking request as Shift+D makes was granted from 9 km and moved nothing, and the autopilot
toggled after it flew the ship out of the sector to some other guidance (start10q, which lost the
container freighter RGD-867 to the Kha'ak SRV-300 before it was stopped). MD's
`dock_player_ship_at`, the action the Split story docks the player with, behind our own check of
5 km to the station's centre, never fired with the ship 5.1 km out where the autopilot stops
(start10r). In start10s the bridge asks the game whether it would grant the request
(`RequestDockAtReason`), and `dock_player_ship_at` then docked RTV-678 from 9 km in about 100 game
seconds. `shelter` now picks our station in the ship's own sector, and in its zone sends `dock`
until the ship is docked (tasks/lessons.md L8m).

**start10s (875.2 to 897.6).** Four ships lost, all to the Kha'ak in Second Contact II Flashpoint:
the fighter LAX-900, the frigate WKD-878 and the solid miners UCE-906 and GRB-220. The nest there is
DVA-963 in this save, spawned at 3,133,400 s and unknown to us, so the raid rule cannot pick it. The
check every 15 cycles found ZLR-942's 20 antimatter cell modules idle on 27,546 cells offered at 121
with a bid of 267 known, and VJA-376's refineries idle on 11,256 refined metals; neither station had
`sell_runs` in the plan, now two runs each. The purchase of their runners was held by the brake: a
runner idle between its runs counts as an idle freighter of the kind, so no other was bought; the
sell-run purchase now goes without it (553ea72), and five freighters came. Many sell runs were
refused at a buy offer "closed to us", and that is the map's stale offer, one we have no live view
of: IJH-368 docked at IMD-107 by hand and sold there, and a loaded runner so refused now docks at
the buyer first (4fd4379). FME-114 and IJH-368 sold 320 and 448 antimatter cells at CGO-701 that
way. The buyers want 200 to 2,000 cells each, so the stock of 27,600 goes down slowly. Net worth at
cost +4.05 M a game hour, credits +3.38 M.

**start10t (897.6 to 917.7).** Five ships lost: four container freighters to the Pact (KOF-224 and
OHA-176 on visits to stale buyers 7 and 9 jumps out, the station trader HJK-621, and QVR-116 in
Silent Witness XI) and the fighter BBY-426 to the Kha'ak in Silent Witness XI. A visit now goes no
further than six jumps from home (c3cd76c), and not to an offer that wanted none (93c11e0). The
Kha'ak nests were unknown to us, so the raid rule could not name them. The scout CLP-378, sent with
`moveto` to 25 km of a nest, inside the 40 km of its radar, put each on the map, and the sector's
patrol, which turns on a known Kha'ak station, took both: DVA-963 in Second Contact II Flashpoint
(by WGW-932) and GFM-954 in Silent Witness XI (by MVX-881), 30 turrets each. Two hives in our
sectors hold 147 turrets each, AHJ-007 in Silent Witness XII and DYQ-953 in cluster_31 beside the
nest QQZ-842; a patrol no longer goes for the Kha'ak where a hive is known (991456c). Net worth at
cost +3.19 M a game hour, credits +3.66 M.

**start10u and start10v (917.7 to 945.8).** start10u stopped after 70 minutes when the PC restarted;
the game had written save_008 three minutes before, intact and one cycle after the memory, and
start10v went on from it. No ship lost in start10u. start10v lost four container freighters to the
Pact: HDI-762 and BDY-694 in Atiya's Misfortune I, IJH-368 in Atiya's Misfortune III and FME-114 in
Faulty Logic VII, the last two on sell runs. The game's own logbook names the sector of each loss
(category upkeep, "Location: ..."), which our lines do not: since start10s six of the eight ships the
Pact took fell in those three sectors, where four of its six killers still stood, the destroyers
DAT-973 and PTD-664 among them. Antimatter sold at IMD-107 freed room, and ZLR-942's idle modules
ran again. DBA-060 now makes energy cells and refined metals. Net worth at cost +3.47 M a game
hour, credits +2.19 M.

**start10w (945.8 to 966.6).** Five container freighters lost: JMZ-762 and XXP-787 to the Pact in
Hatikvah's Choice I, OAW-538 to the Pact in Morning Star III, LXG-414 to the Fallen Families in
Nopileos' Fortune VI and KFO-429 to Duke's Buccaneers in Pious Mists XI. Atiya's Misfortune I and
III and Faulty Logic VII went on the plan's avoided list early in the run, after six of eight Pact
kills since start10s had fallen there; none fell there after. Four of the last six freighters lost
were DBA-060's, a base among the Pact, the Fallen Families and the Buccaneers; the plan now names
DBA-060 with the base template and no traders. Since the nest DVA-963 fell, nothing more was lost
to the Kha'ak in Second Contact II Flashpoint. Hatikvah's Choice I, with a patrol of six destroyers,
lost three freighters to Pact Minotaur raiders since start10t. Net worth at cost +4.16 M a game
hour, credits +4.87 M, the best of this series.
