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
