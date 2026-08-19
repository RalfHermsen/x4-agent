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
