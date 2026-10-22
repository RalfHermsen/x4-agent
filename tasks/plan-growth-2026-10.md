# Plan: growth, after the three-arm measurement

Written 2026-10-21, after 5.7 (`docs/experiments.md`). What the measurements
say: the game alone holds 1.81 to 1.82 million per game hour in net worth;
Python's rules reach 1.95 to 2.12, nearly all of it from one expansion of
KYV-745 that the builder fix let finish; the model with the catalog is not
distinguishable from the rules. So the next gains are in growth: more and
better production, a second station, and selling what is made. And the
model's place is in the choices growth brings, not in every cycle.

House rules as before: nothing free (L8i), risk stays a decision unless the
player has made it (scouts, 2026-10-21), prices are Python's, everything
offline is measured on stored saves before a run uses it. And now also:
while a measurement series runs, code is changed only outside the working
tree the runs read (a separate git worktree), and merged between series.

## 6.1 A score that shows what lasts

Net worth counts stock at minimum prices, which for ore and ice near
KYV-745 is still generous (few buyers), and part of a run's gain is new
storage filling once.

* Income per game hour over the last third of a run: net worth at two thirds
  and at the end, from the cycle saves the agent log names.
* Stock split into wares with a known buyer and wares without one; the
  second shown apart and not in net worth.

Done when: both computed for every finished run and the long runs; written
up beside the full-run figures.

## 6.2 What to build next, by margin

The catalog offers an expansion only when a store is full, and the bridge can
build five wares (energycells, refinedmetals, siliconwafers, water,
habitation) while blueprints for six more are owned (microchips, smartchips,
spices, medicalsupplies, nostropoil, sunriseflowers).

* The bridge's expansion list gets every production ware we hold a
  blueprint for.
* Python ranks expansions by margin per game hour: the recipe's output at
  the best known buy price, minus its inputs at the best known sell price
  (or our own production), per module, from `libraries/wares.xml` recipes;
  wares with no known buyer are left out.
* A catalog entry "a station could grow": the best three expansions, offered
  when no build is running and the station has a builder or one can be hired.

Done when: offline over the 16 saves every offered expansion passes the
gates and the ranking is reproducible by hand for one save; one expansion of
a ware new to the bridge proven in the game.

## 6.3 The second station

GKL-870 (Ianamus Zura IV) has a build storage (CKK-224) and no modules, and
no run has used it.

* Proof in the game: `expand GKL-870 <ware>` on an empty station, or the
  reason it cannot (the construction sequence may need a dock or a base
  first).
* If it works: the catalog offers GKL-870's first modules through 6.2's
  ranking, and its budget once it has modules.

Done when: GKL-870 has a module built in a run, or the reason it cannot is
in `docs/contracts.md` with what would make it possible.

## 6.4 Selling what is made

Rules-only runs ended with about 8 million more stock, 29,000 silicon wafers
among it. Whether traders or buyers are short decides the answer.

* Offline: per product, stock over the run against the trades our ships made
  (the trade logbook in the save, if the parser can read it) and the known
  buy offers for it.
* Then the matching rule: a freighter bought when products pile up and every
  freighter is busy (5.6 offers one only when none is free), or prices and
  sell limits looked at again for that ware.

Done when: the cause is written down per product for two runs, and the rule
it points to is built with tests.

## 6.5 Fewer ships lost

One to three ships lost per run, freighters to pirates and Xenon among them.
The `avoid hostile` verb is built and never proven.

* Proof in the game: `avoid hostile` on the trade fleet's blacklist.
* Python rule: after a ship of ours is destroyed in a sector, that sector
  goes on the traders' blacklist for some game hours.

Done when: proven, and over the next measurement the losses per run are
written up against the runs above.

## 6.6 Cheap levers

* Storage modules as an expansion (container, solid, liquid, by the store
  that is full), offered by `storage_full`: the most requested missing
  option, and the full store was the limit.
* Seminars for the station manager (4.2: built, only the refusal proven):
  proof in the game with a seminar in the inventory, then a standing rule
  when one is held.

Done when: a storage module built in the game through the bridge, and a
seminar applied, each proven once.

## 6.7 The model where it matters

The model takes option 1 most of the time and adds nothing measurable yet.

* Offline: the stored catalog reports again with the options shuffled;
  count how often the choice follows the option rather than its position.
* The model asked only when a situation with weight is in the report
  (expansions, purchases, risk), not every cycle; the rest is Python's.

Done when: the position test is written up; the second change measured as
GPU time per game hour and, in the next series, as net worth against the
catalog runs above.

## 6.8 Which rule costs income in steady state

Added 2026-10-22 after 6.1's long runs: rules only earned 1.61 million per
game hour in its last third against 1.82 for the game alone.

* A warm baseline: the long rules-only run's end save (107 game hours, the
  expansion built, the store full), frozen next to the 73-hour baseline.
* Two-hour runs from it: the game alone, every rule, and every rule but one
  (`X4_RULES_OFF`: "focus", "sell_limits", "pricing"), so each run measures
  steady state from its first hour.

Done when: each arm written up per game hour in net worth and credits; the
rule that costs income, if one does, switched off or rewritten, with tests.

## Order of work, and what needs the game

| Item | Offline now (worktree) | Needs the game |
|---|---|---|
| 6.1 | all of it | no |
| 6.2 | bridge list, ranking, catalog entry, evals | one expansion proof |
| 6.3 | | the proof first, then a run |
| 6.4 | the analysis | the rule's effect in a run |
| 6.5 | the rule and its tests | the verb proof |
| 6.6 | the storage expansion code | two proofs |
| 6.7 | both | the next series |

Then one measurement series with everything in: rules, rules with the
catalog, and the game alone for comparison, long enough for an expansion to
pay back.

## Status

| Item | State |
|---|---|
| 6.1 | done: over 33 game hours, net worth per game hour (whole run, last third): the game alone 1.83 and 1.82; rules only 1.84 and 1.61 (a one-off stock fill, then less income); rules and catalog 1.98 and 2.04, with a second expansion (refined metals, eating the ore that filled the store) and 2.03 in credits over the last third (`docs/experiments.md`) |
| 6.2 | done: `expand KYV-745 nostropoil` built in the game (a ware new to the bridge); Python's `grow` rule expands with the top of the ranking (margin, demand, and not a ware with ten module-hours in store), in `main` since `311a7d7` |
| 6.3 | done in the game: the MD found no station without modules (`find_object` skips the non-operational); with `checkoperational="false"` GKL-870 took a budget and started a water module, solid storage added to the plan by itself. `grow` now starts an empty station with a ware made from mined inputs or energy cells |
| 6.4 | first finding: the station offers only a sliver of its stock in every arm (energy cells 157,754 held and 328 offered at the baseline, 159,128 and 1,502 in an advise run, 208,846 and 79 after rules only); the game's manager keeps the rest as a buffer for its own production, and Python's sell limits are small (2,000 to 15,000). So the rules-only stock gain is mostly a larger buffer after the expansion, one-off; whether income per hour grows is the long runs' question (6.1) |
| 6.5 | done in the game: `avoid hostile on -> civilian=true`; set once by `standing.once` |
| 6.6 | storage done in the game (`expand KYV-745 storage_solid`, a Teladi L solid store queued); seminars still to do |
| 6.8 | done: from the warm baseline, credits per game hour: the game alone 1.49, every rule 1.76, without fleet focus 1.75, without sell limits 1.98, without repricing 1.98 (`docs/experiments.md`); sell limits and repricing switched off by default, a confirmation run with both off to come |
| 6.7 | position test done: with the options reversed the model took the same option in 1 of 16 choices and the same position in 9 (`docs/contracts.md`); next, Python takes the top-ranked option and the model may only decline it |
