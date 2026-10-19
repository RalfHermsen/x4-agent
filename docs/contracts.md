# Constrained decoding: what works and what breaks silently

Measured on 2026-08-19 with `gemma4:26b-a4b-it-qat` through Ollama, using the
`PlannerResponse` schema from `schemas.py`. Everything below is observed
behaviour, not theory.

The brief (section 8.1) cites XGrammar and "100% schema compliance". That is
true, and it is precisely the trap: **all three failures below produced
schema-valid JSON.** Compliance says nothing about meaning.

## Failure 1: the union collapses to the cheapest branch

First attempt: one call, schema enforced, actions as a discriminated union of
nine types. Result:

```json
{"priority": "high",
 "rationale": "ASO-629 should replenish the shortages at KYV-745.",
 "type": "hold"}
```

Three actions, all three `hold`, while every rationale described a concrete
thing to do. Valid JSON, wrong meaning, no error anywhere.

**What did not help:** putting the entire action vocabulary in the system prompt
with an explicit instruction never to describe an intended action as `hold`.
Still three `hold`s.

**What also did not help:** the two-call pattern from section 8.1 (call 1 reason
freely, call 2 constrained extraction). The reasoning was fine, the extraction
collapsed anyway. That was the evidence that reasoning room was not the problem.

**The actual cause:** field order. The action classes inherited `priority` and
`rationale` from a base class, and pydantic places inherited fields first. So
`type` ended up last in the JSON schema. Under grammar-constrained decoding the
model writes the rationale first and only then has to pick a branch, at which
point `hold` is the one branch that demands nothing further.

**Fix:** make `type` the first field of every action class. It costs some
repetition of `priority` and `rationale` per class, but the inheritance was the
bug.

## Failure 2: a required field that is not required

With `type` first, real actions appeared, but without `type`:

```json
{"ship_ref": "ASO-629", "station_id": "KYV-745", "role": "trade", ...}
```

Cause: `type: Literal["assign_ship"] = "assign_ship"` has a default, so pydantic
leaves the field out of `required`, so the grammar permits skipping it. Pydantic
then refuses to validate because the discriminator is missing.

**Fix:** no default on `type`. Then it lands in `required` and the grammar
enforces it. Python-side you now have to pass the field explicitly when
constructing an action by hand.

## Failure 3: schema-valid nonsense

After fixes 1 and 2 this came out:

```
assign_ship  ship_ref="ASO-629"  station_id="market"
assign_ship  ship_ref="TJL-171"  station_id="unknown"
```

`market` and `unknown` are not stations. Schema-valid, semantically nonsense.

A subtler variant appeared in the same run: assigning our own trader to a
station belonging to another faction. Every reference existed, the schema was
satisfied, and it still could not be executed.

**Fix:** the semantic validation from section 8.1, implemented in
`planner.check_actions()`, with two sieves rather than one:

1. does the referenced object exist at all?
2. are we allowed to do this to it? Orders only apply to assets we own.

In Phase 1 rejected actions are logged. From Phase 2 this is the last filter
before anything reaches the game.

## Working setup

| Component | Choice |
|-----------|--------|
| Call 1 | reason freely, no `format` |
| Call 2 | `format` = `PlannerResponse.model_json_schema()`, translate only |
| Schema in the prompt | **do not**; Ollama enforces it server side, and the schema is 8.2 kB |
| Field order | `type` first, `priority` and `rationale` last |
| `type` | required, so no default |
| After validation | semantic check on references and ownership |

Cost: 8.3 s reasoning plus 6.9 s structuring on a warm model. The second call is
not free but it is cheap, because it no longer has to think.

## Still open

* `hold` still shows up as filler with a commentary-style rationale. Worth
  considering: take `hold` out of the union and make it a separate field on
  `PlannerResponse`, so it cannot occupy an action slot.

---

## Scale test on a real empire

The reference save is a fresh start. To find out whether the pipeline scales,
the same code was run over all eleven saves in the profile folder: X4 6.20,
7.00, 8.00 and 9.00, from 8,598 to 99,400 seconds of playtime and up to 188
million credits. **The parser ran unmodified on all eleven.**

The sitrep did not.

| Save | Ships | Sitrep before | Sitrep after |
|------|-------|---------------|--------------|
| fresh start | 2 | 922 B | 921 B |
| 188M credit empire | 220 | **40,130 B** | **2,707 B** |

40 kB is over 10,000 tokens for a mid-sized empire, and that fleet is not even
large. The aggregation principle in `schemas.py` ("fleets aggregated per role,
not per ship") is therefore a necessity, not a style preference.

**Derive roles from the order, not the macro.** Measured on that save: Escort
115, Assist 92, MiningRoutine (three variants) 6, TradeRoutine/Middleman 2,
SectorExplorer 1, Wait 3. Macro names say what a ship *is*, the order says what
it *does*, and the latter is what the planner needs.

Also measured:

* Parsing a 42 MB save takes 18.8 s with flat memory.
* Known stations scale with exploration: 4 in the fresh start, **792** in the
  late-game empire. Playing fair therefore constrains you less the more you
  explore.
* Margins only get interesting at scale: 782 Cr per unit on the best ware in the
  late-game save, versus 21 Cr in the fresh start.

## The executable action surface exists

An open risk was whether the action vocabulary in `schemas.py` is executable at
all, or whether parts of it are UI-only. The answer is in the game itself:
`libraries/common.xsd` (1.7 MB, 1,339 defined elements).

| Action type | Script primitives that exist |
|-------------|------------------------------|
| assign_ship / set_behaviour | `create_order`, `edit_order_param`, `cancel_order`, `set_current_loop_order` |
| set_trade_rule | `set_trade_restrictions`, `add_tradeware`, `set_tradeoffers_enabled`, `add_supply_order` |
| set_price | `minprice`, `price`, `relativeprice` |
| fleet_order | `set_subordinate_group_assignment`, `set_subordinate_group_protected_sector` |
| build_station | `set_build_plot`, `reserve_build_plot`, `apply_construction_sequence`, `add_build_to_expand_station`, `process_build` |
| purchase / budget | `set_object_min_budget`, `set_object_max_budget`, `add_blueprints` |
| boarding | `create_boarding_operation`, `start_boarding_operation` |

So building a station is scriptable and not UI-only.

**What this does not prove:** that a Mission Director cue of ours may call these
primitives in player context, or that they do what their names suggest. The risk
moves from "we are building on capabilities that may not exist" to "they exist,
and we must show we can invoke them".

---

## Phase 1 definition of done: measured

`evaluate.py` runs the whole loop over every save in the profile folder. Eleven
saves, four game versions (6.20, 7.00, 8.00, 9.00), from a 20-second fresh start
to a 220-ship empire with 220 million credits.

| Metric | Result |
|--------|--------|
| Saves processed | 11/11, no failures |
| Largest sitrep | 2,640 bytes (at 221 ships) |
| Time per save | roughly 40 s, about half of it parsing |
| Actions produced | 46 |
| Rejected by the semantic check | 6 |

### What the rejections taught us

The first run rejected 10 of 58 actions (15%), and the reasons were not random:

```
4  ship_ref=miner does not exist
3  ship_ref=trader does not exist
1  ship_ref=combat does not exist
1  fleet_id=scouts does not exist
1  station_id=MJI-379 is not ours
```

Nine of ten were **role words instead of ID codes**. That is the cost of
aggregating the fleet by role: it cut the sitrep by 15x, but summarising ships
as "miner 6, trader 2" makes the model reach for the role word rather than for
`NCD-755`.

Adding one constraint to the extraction prompt ("every reference must be an ID
code of the form AAA-123, copied literally from the report; never a role word")
removed that entire class:

```
3  station_id=MJI-379 is not ours
1  station_id=BSL-396 is not ours
```

The headline number moved from 15% to 12%, which on 58 versus 46 actions across
eleven saves is too small a sample to lean on. The *composition* is the evidence:
the invented-identifier class disappeared, and what remains is a different kind
of error entirely.

### The error that is left

The model wants to assign our ships to stations belonging to other factions,
repeatedly and to the same station. That is not a formatting slip but a genuine
strategic misunderstanding: `assign_ship` only works on stations we own, and the
sitrep already separates "# OWN STATIONS" from "# KNOWN MARKET".

This is exactly why the second sieve exists. Without the ownership check those
actions would have passed as schema-valid and gone to the game.

---

## The same trap, twice

Two months of care about the discriminator field and it still caught us again.

`PlannerResponse.updated_goals` carried `default_factory=list`. Pydantic
therefore left it out of `required`, the grammar allowed the model to omit it,
and it did: the free-reasoning call ended on

```
**Standing Goals:**
* Stabilize KYV-745 production by ensuring sufficient budget and internal logistics.
* Accumulate capital toward the 2M Cr threshold.
```

and the structured answer came back with an empty list. The agent's entire
memory between cycles was being thrown away at the last step, silently, while
every visible part of the pipeline looked healthy.

**The rule, restated:** in a grammar-constrained schema, a default is not a
convenience, it is permission to skip. Any field you actually need must be
required, even when an empty value is legal. `updated_goals` is now required and
documented as "may be empty, but the field itself must be present".

---

## Local against hosted: one run each, 2026-10-18

The same reasoning prompt over the same 15 saves (one more failed on the
hosted side with HTTP 429, a rate limit). Run A: `gemma4:26b-a4b-it-qat` for
both calls. Run B: GPT-OSS 120B on a hosted endpoint for the reasoning call,
the same local gemma4 translating (`X4_EXTRACT_MODEL`). One run each, so
these are indications, not measurements of variance.

| | A: local | B: hosted reasoning |
|---|---|---|
| Valid actions | 74 | 118 |
| Action types used | 4 | 8 (adds trade rules, purchase, build_station, hold) |
| Refused by the executor gates | 27 | 46 |
| Of which "ship already busy" | 3 | 16 |
| Prices outside the sane band | 2 | 6, four of them 0 Cr |
| Invented references (rejected) | 3 | 2 |
| Model time per save | 100 to 316 s | 64 to 173 s, mostly the local translation |
| `expand_station` proposed | 0 | 0 |

The model times are almost certainly CPU times. The model server had fallen
back to running the local model on its CPU after a restart on 2026-10-15
(found and fixed on the evening of 2026-10-18, `docs/experiments.md`); on
its GPU a whole cycle, both calls, takes about 16 s. The counts are not
affected; the times say nothing about the GPU setup.

What it says:

* **The hosted model reads more of the report and does more.** It assigns
  ships and sets trade rules where the local one mostly proposes prices. It is
  also the one that keeps assigning ships that are already working: 16 of its
  refusals are "already busy", the exact failure that 1.2 (refusals back in
  the report) was built against. Neither run had that feedback.
* **Both spend most of their actions on prices** (44 and 50), which the
  guidelines say not to do because Python reprices every cycle. That is a
  prompt and guideline problem, not a model one.
* **The 0 Cr prices are probably the translation step**, which was gemma4 in
  both runs: the reasoning names a price, the structured action carries none.
  Worth checking before blaming either model.
* **Neither is good enough to pick on this evidence.** The deciding test is
  the scorecard over game hours from one baseline, with the refusal feedback
  in place, which this comparison predates.

## The translation step, replayed: 2026-10-19

`backtest_extract.py` ran every stored pair of report and reasoning (175:
the comparison files and every model cycle of the 2.4 runs) through call 2
on the local model, twice, and through a parser that fills the simple types
from the words of a line and only with codes from that cycle's report.

| | call 2, `gemma4:26b-a4b-it-qat` | parser |
|---|---|---|
| Numbered lines in | 681 | 681 |
| Actions out | 765 | 546 |
| Answers with lines but no action | 5 | 11 |
| Invented references | 22 | 0 |
| Identical on a second run | 151 of 175 | always |
| Median time per call | 5.7 s (GPU) | none |

* **The parser alone reads 75 of the 173 inputs that have actions
  completely**; for those no model call is needed at all.
* **The 5 answers where call 2 dropped every action** all had lines the
  parser could read: 1 to 4 actions each.
* **All 22 invented references are in inputs the parser did not read
  completely**: sector names, `UNKNOWN`, a ware or an order name where a
  station code belongs.
* **Call 2 flips the side of prices.** Of the 441 prices the parser read off
  a line, call 2 gave 347 back unchanged; 87 of the other 94 had become buy
  prices, mostly from lines that name no side, such as "set_price for
  KYV-745: microchips to 1198, ..." at the station that makes microchips. 7
  were dropped. No buy-side price reached the game in the 2.4 runs, but the
  73-hour save carries two buy-side overrides from an earlier session at
  KYV-745 (medical supplies at 88, nostropoil at 46, game hour 64.9) that
  look like the same error.
* **Call 2 is not repeatable at temperature 0**: 24 of 175 inputs came back
  different the second time.
* **The hosted route could not be measured.** On the free tier its daily
  budget is 200,000 tokens, about 45 translation calls, and it was spent
  (L20).

What this suggests: the parser first, for every line it reads with
certainty, and call 2 only for the rest, told to read a price without a side
as a sell price when the station makes the ware. That removes the empty
answers and the flipped sides on the lines the parser takes, and leaves
call 2 a quarter of the lines (169 of 681).

### Parser first, built and replayed the same day

`planner.translate` now puts the parser in front of call 2: every line it
reads with certainty becomes its action, only the other lines go to call 2,
and when there are none call 2 does not run. Replayed over the same 175
cycles, twice:

| | call 2 alone | parser first, then call 2 |
|---|---|---|
| Answers with lines but no action | 5 | 1 |
| Invented references | 22 | 14 |
| Prices given back as read | 347 of 441 | 441 of 441 |
| Identical on a second run | 151 of 175 | 159 of 175 |
| Cycles with no model call | 0 | 75 |
| Model time over all cycles | 1,059 s | 483 s |

The one empty answer left is an old hosted reasoning in a shape the parser
does not read (a bold code and a dash, with sub-bullets). The 14 invented
references are all call 2's, on lines the parser left: `UNKNOWN`, sector
names, order names where a station belongs. `check_actions` refuses them.

## More actions per cycle, and other models: 2026-10-19

**The cap.** Call 1 has ended in at most four actions since the first day,
with no reason written down. `X4_MAX_ACTIONS` makes it a setting (default
4), and `evaluate.py` ran all 16 saves through the agent's own path
(reasoning, parser, call 2, `check_actions`, executor gates) at 4 and at 8,
on the local model:

| | cap 4 | cap 8 |
|---|---|---|
| Lines proposed | 61 | 118 |
| Valid actions | 67 | 67 |
| Refused | 7 (9 %) | 46 (41 %) |
| Skipped by the executor gates | 39 | 39 |

Twice the lines, the same valid actions, five times the refusals. The cap
stays at 4.

**Other models, without an API key.** The same call-1 prompt for five saves
(0.7 to 81 million credits, 6 to 29 ships) was answered by Claude Haiku,
Sonnet and Opus running as subagents of a coding session, so with that
session's own instructions around the prompt: an approximation of API use,
not a measurement of it. Each answer then went through the same pipeline as
the local model's:

| | gemma4 | Haiku | Sonnet | Opus |
|---|---|---|---|---|
| Lines | 19 | 19 | 20 | 20 |
| Valid actions | 31 | 26 | 28 | 20 |
| Skipped by the executor gates | 21 | 18 | 20 | 10 |
| Executable | 10 | 8 | 8 | 10 |
| Expansions and purchases proposed | 0 | 4 | 7 | 4 |

The executable count hardly moves, and the reasons are the executor, not
the model: assignments to ships busy with a dock or a move ("already busy,
not overriding", the most common skip for every model), storage modules the
bridge cannot build (the Claude models' first action on the 73-hour save,
which is 99 % full of solids), and purchases that need an exact ship macro
the model has to guess. The reading differs: on the 73-hour save all three
Claude models named the same four problems (solid storage, no budget at
GKL-870, a fighter under fire in The Void, scouts on covered ground), where
the local model reassigned eight freighters that were traders already and
took the full store for container storage.

## The action catalog, measured offline: 2026-10-19

`catalog.py` (5.3) puts situations with prepared options in the report, and
call 1 answers per situation. `evaluate.py` with `X4_CATALOG=1` over the same
16 saves, on the local model:

| | free actions (cap 4) | catalog |
|---|---|---|
| Lines or situations | 61 lines | 77 situations, 130 options |
| Executable actions | 28 (67 valid, 39 skipped by the gates) | 63 |
| Refused or skipped | 46 | 0 |
| Answers that could not be read | n/a | 0 |

The first catalog run read nothing: the local model wrote its `S1: 2` lines
without the DECISIONS heading, in every save. The parser now takes decision
lines without the heading too (`abecd96`).

The same five saves as the model comparison, with the Claude models again as
subagents of a coding session:

| | gemma4 | Haiku | Sonnet | Opus |
|---|---|---|---|---|
| Situations answered | 23 of 23 | 22 of 22 | 22 of 22 | 22 of 22 |
| Options chosen | 17 | 19 | 19 | 16 |
| None, on purpose | 6 | 3 | 3 | 6 |

On the 73-hour save all four models now bring the fighter home from Xenon
space, and three of four expand KYV-745 with refined metals to use the ore
that fills its solid store; Opus declined a budget for GKL-870, which has no
modules, and no Claude model bought a ship while the store is full. The
local model still read "exploring the sector it is already in" as a reason
to leave the scout alone.

With the catalog the model question mostly goes away for execution: every
model's choices are carried out. What remains is the quality of the choice,
which only runs in the game can measure (5.5). Opus's free ideas are the next
catalog entries: keep traders out of a sector with Xenon in it, escort
traders that were attacked, satellites where stations are known but unseen.

A side finding: Sonnet 5.5 stopped once on its safety classifier
(`reasoning_extraction`), apparently on "think out loud" in the planner's
prompt. Asked for a short assessment instead, it answered normally. A hosted
Claude planner should be prompted that way.
