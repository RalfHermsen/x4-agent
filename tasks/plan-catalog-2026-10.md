# Plan: an action catalog, so the model decides instead of inventing

Written 2026-10-19, after the first measurement (`docs/experiments.md`) and the
model comparison (`docs/contracts.md`). The finding behind it: whichever model
plans, the agent executes 8 to 10 actions in five saves, because the model
proposes what the bridge cannot do, actions the executor's gates refuse
afterwards, and details (ship macros, prices, which ship) it has to guess.

The idea: Python recognises situations in the save and puts next to each one
only the actions that can be carried out now, with every detail filled in.
The model decides per situation: which option, or none, and why. What it
would like but is not offered goes into a free list as advice, and what keeps
coming back there is the next catalog entry.

House rules that hold for every item:

* Nothing free: an option that gets something pays for it first, at the price
  the game's own menu would ask (L8i).
* Risk stays a decision (L18): an option that sends a ship into unknown or
  hostile space is offered, never executed without the model choosing it.
* Prices stay Python's (After 2.4); no catalog entry offers a price.
* Everything offline is measured on the stored saves before a run uses it.

## 5.1 What the game offers

Inventory of every action a commander can take, from three sources:

* **The game's files**: every order definition in `aiscripts/order.*.xml`
  (id, name, description, category, parameters, whether the player can give
  it), and the station settings the menus write (budget, trade rules, offers,
  limits, storage, workforce, construction).
* **The official manual and three to five strong guides** (Egosoft wiki,
  forum, Steam, Reddit), for what each action is for.
* **The bridge**: every verb in `x4agent.lua` and the MD, with its proof state
  from the plan.

Output: `tasks/research-actions-2026-10.md`, one row per action: what it does,
prerequisites (licence, blueprint, skill, money, ship type), the bridge verb
or "missing", the source.

Done when:

* every order in `aiscripts` with a player-facing name has a row with a status
  (has a verb, missing, or not relevant to a commander, with the reason);
* every bridge verb appears;
* every row cites its source; anything not verified says so.

## 5.2 Situations and strategies

From the guides and from `guidelines.md`: the situations an empire manager
meets, each with the actions recommended there in order of preference and
the reason. Each situation must be detectable from the parsed save.

Output: a "Situations" section in the same research file: situation, the
test on the parsed state that detects it (or "needs the parser to read X"),
candidate actions, reason, source or guideline.

Done when:

* every situation has a detector written against `save_parser` fields, or is
  marked as needing a parser change;
* every situation is backed by a guideline line or a cited source;
* the detectors, run over the 16 stored saves, fire where expected: on the
  73-hour save at least the four problems all three Claude models named
  (solid storage at 99 %, no budget at GKL-870, a fighter under fire in The
  Void, scouts on covered ground).

## 5.3 The catalog in code

`catalog.py`: each entry has an id, a detector (state to instances), an
options function (instance to executable commands with every parameter
filled, checked against the executor's gates before they are offered), and a
check for the next cycle (what should have changed).

The sitrep gets a SITUATIONS section: numbered situations, each with numbered
options. The answer format is one line per situation, `S2: 1` or `S2: none`,
with a reason; free ideas go under OTHER and are logged as advice. The
parser reads the answer; call 2 is not needed for catalog answers.

Done when:

* each entry has unit tests on crafted states: fires when it should, stays
  quiet when it should not, offers only options that pass;
* over the 16 saves, every offered option passes `check_actions` and
  `executor.to_commands`: no refusal and no skip, by construction;
* the parser reads 100 % of answers in the defined format, and a malformed
  line is reported, never guessed.

## 5.4 Measured offline

`evaluate.py` over the 16 saves with the catalog in the report, against the
current planner (cap 4: 61 lines, 67 valid actions, 39 skipped).

Done when, on the same saves:

* refused plus skipped is under 10 % of the chosen options;
* executable actions are at least the current planner's;
* on the 73-hour save the four named problems are each offered and get an
  answer;
* the same is run with the Claude models as subagents (as on 2026-10-19), so
  the model question is answered on the catalog, not on free text.

## 5.5 Measured in the game

Two pairs of two-hour runs (advise, execute) on the 73-hour baseline with
50 million credits, as in 2.4.

Done when both pairs are written up in `docs/experiments.md` against 2.4's
pair: credits per game hour, ships and modules, losses, options chosen and
their checks. The catalog is worth keeping if the execute runs beat their
advise runs, and if they beat 2.4's execute run.

## Evals

| Item | How | Passes when |
|---|---|---|
| 5.1 | compare the order list from `aiscripts` and the verb list with the rows | every order and verb has a row with a status; every row has a source |
| 5.2 | run each detector over the 16 saves | each fires on the saves it should; the four problems on the 73-hour save are found |
| 5.3 | unit tests; all offered options through `check_actions` and `to_commands` | tests green; zero refused, zero skipped |
| 5.4 | `evaluate.py` with the catalog, gemma4 and the Claude subagents | refused plus skipped under 10 %; executable at least the baseline; the four problems answered |
| 5.5 | two pairs of runs on the 73-hour baseline | written up; execute against advise, and against 2.4 |

## Status, 2026-10-19

| Item | State | Evidence |
|---|---|---|
| 5.1 | done | `tasks/research-actions-2026-10.md`: all 44 player-facing orders and every bridge verb with a status |
| 5.2 | done | detectors over the 16 saves; on the 73-hour save the four problems plus idle capital |
| 5.3 | done | `catalog.py` behind `X4_CATALOG=1`; tests green; options checked when offered |
| 5.4 | done | executable actions 28 to 63 on the 16 saves, nothing refused or skipped; every model's choices carried out (`docs/contracts.md`) |
| 5.5 | done, rule not met | both execute runs below their advise runs (1.53 against 1.79 and 1.73 against 1.88 million per game hour, bought ships at cost); execution clean, purchases do not pay within a run (`docs/experiments.md`). Purchase price proven first: a Mercury at TXT-319 1,104,280 Cr against the menu's 1,075,854, the rest being the menu's software discount |
| 5.6 | done offline | `idle_capital` gone; miners only with room, freighters only for piled-up products with none free; an idle ship holds a purchase of its own kind. Over the 16 saves and the end saves of four execute runs: no solid miner offered, no purchase on the 73-hour saves, the liquid miner for QDA-703 still offered; no violation |
| 5.7 | running | rules only 2.07 M per game hour in net worth, rules only without repricing 2.01, the game alone 1.81 to 1.82 (`docs/experiments.md`, counted again with the stations' accounts and stock); a second rules-only run and two catalog runs with 5.6 to come |

## After 5.5: purchases only for a need, and a rules-only arm

Measured in five execute runs (`docs/experiments.md`): the advise runs earn
1.79 to 1.88 million per game hour, every execute run less, and every time
because of purchases: 8 to 10 ships per run, in two runs six solid miners
bought while the solid store was 99 % full. "Money unused" offered a ship
whatever the station needed, and the brake only counted idle ships the
catalog had work for.

### 5.6 Purchases only for a need the save shows

* No purchase for money alone: `idle_capital` leaves the catalog.
* A miner only for a station short of what that kind mines
  (`mined_shortage`), and only when the station's store for that ware's
  transport type has room (below `executor.FULL`).
* A freighter only when products pile up (`storage_full`, products in a store
  at 90 % or more) and no freighter of ours is free to assign.
* Any ship of ours with no orders and no commander holds every purchase,
  whether or not the catalog has work for it. The game hour between two
  purchases and one purchase per cycle stay.

Done when:

* unit tests for each rule: fires when it should, stays quiet when it
  should not;
* over the 16 saves and the end saves of the five execute runs: no solid
  miner offered while a solid store is at 90 % or more, no purchase offered
  while a ship of ours is idle, and the liquid miner for QDA-703's methane
  still offered (save_003 to save_005);
* every offered option still passes the gates (5.3's eval).

### 5.7 Three arms instead of two

`X4_RULES_ONLY=1`: the cycle runs every Python rule (prices, fleet focus,
funding, hiring builders, repairs, the standing rules) and never the model.
Then one run of each arm on the 73-hour baseline, then a second set:
advise (the game alone), rules only, rules with the catalog.

Done when written up against each other per game hour, with what was bought
and built. The model is worth its place if rules with the catalog beat rules
only; Python's rules are worth theirs if rules only beat advise.

## Order of work, and what needs a person

5.1 and 5.2 need nobody. 5.3 and 5.4 need nobody. 5.5 runs unattended on the
existing baseline; it needs the game, so nobody should be playing during it.
