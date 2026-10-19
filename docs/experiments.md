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
  a hull value only for a damaged ship). The payment is not in the logbook,
  and the trade income hides it in the totals.

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

### The advise-mode fix

Seen on the in-game panel during the first, dropped advise run: `sent:` for
commands that advise mode never sends, and the next cycle reporting them as
failed ("TJL-171 is on Wait, not Explore"), which told the model something
untrue. The memory treated every cycle as one that sends. Since `4683b6c`
the host passes `sends=False` in advise mode: the cycle plans as before but
keeps nothing of what it would have done, and the panel says `would send`.
The advise run above predates the fix; it changed that run's advice, not
its game.
