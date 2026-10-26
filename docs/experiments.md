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
