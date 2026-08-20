# Phase 3: an agent that acts

Phase 2 proved one order could reach the game. Phase 3 is the difference between
that and something you can leave running: a vocabulary worth having, gates that
stop bad orders, and enough plumbing that it does not quietly drop half its work.

All of it measured against X4 9.00 on 2026-08-19.

## What the agent can actually do

`executor.describe()` is the single source of truth, and the planner prompt is
built from it, so the model is always told what its body can do.

| Action | In-game effect | Verified primitive |
|--------|----------------|--------------------|
| `assign_ship` | attach a ship to one of our stations as trader or miner | `set_object_commander` with `assignment.trade` / `assignment.mining` |
| `set_behaviour(explore)` | Explore as the ship's default behaviour, aimed at an unknown sector | `create_order id="Explore" default="true"` |
| `set_behaviour(autotrade)` | vanilla AutoTrade | `create_order id="TradeRoutine"` |
| `set_behaviour(automine)` | vanilla mining routine | `create_order id="MiningRoutine"` |
| `set_budget` | operating budget as a level, low/mid/high | `set_object_min_budget`, `set_object_max_budget` |
| `expand_station` | add production for a ware to a station we own | `get_god_production_construction_plan` → `apply_construction_sequence` → `add_build_to_expand_station` |

Everything else the model proposes is recorded as advice and never reaches the
game.

### Expanding a station is easier than building one

No plot to buy, no location to choose, no module list to invent:

```xml
<get_god_production_construction_plan result="$plan" product="$ware" faction="faction.player"/>
<apply_construction_sequence station="$station" sequence="$plan"/>
<add_build_to_expand_station object="$station.buildstorage" buildobject="$station"
                             constructionplan="$station.plannedconstruction.sequence"/>
```

`get_god_production_construction_plan` hands back the prefab plan the game's own
factions use for that product, and `apply_construction_sequence` is documented
as "Appends a construction plan to a station that already exists". The last step
is exactly what `engineer.ai.xml` does for NPC stations.

The player still needs the blueprint and a construction vessel; the agent only
plans the build.

## Four gates before anything reaches the game

Each one exists because something got through the previous ones.

1. **Does it exist?** The model wrote `station_id="market"` and
   `ship_ref="miner"`, which are schema-valid and meaningless.
2. **Is it ours?** It tried to assign our trader to another faction's station.
   Every reference existed; the action was still impossible.
3. **Is it already true?** Without this the agent re-sends the same order every
   cycle, because the plan does not change until the world does. Covers both
   running orders and budgets already set.
4. **Is the ship busy?** A ship carrying a real order is left alone, whoever
   gave it. The game exposes `@object.order.$internalorder` to tell a
   script-issued order from a player-issued one, but only in the running game,
   not in the savegame, so this rule errs on the safe side.

Two more filters sit alongside them: one order per ship per cycle (the model
emitted "put ASO-629 on autotrade" and "assign ASO-629 to KYV-745" in the same
plan, and the second would have silently undone the first), and identical
commands are collapsed (the same action arrives twice with different reasons).

## Things that cost real time

### Commands sent back to back drop the pipe

The log looked healthy:

```
cycle done in 16.9s: 4 valid actions, 3 executable, 0 rejected
sending: assign QNL-869 KYV-745 mine
Pipe client garbage collected, restarting.
```

The host recovered by itself, so nothing looked broken, and only the first
command of every cycle ever arrived. X4 finishes processing a command before
reading the next, and the matching loop on the game side walks every ship and
station, so the pipe is not ready again immediately. Two seconds between writes
fixed it, plus catching a failed write so one loss does not swallow the rest.

This was the third time in one day that a log line said what happened rather
than whether it worked.

### Three different money scales

* Trade prices in the savegame: **hundredths of a credit**.
* `player.money` in the Mission Director: **hundredths of a credit**.
* `info/player money` and station `<account amount=...>` in the savegame:
  **whole credits**.

A budget of "500871850 Cr" in the logbook was really 5,008,718 Cr, printed in
internal units. Use `$value / 1Cr` when formatting money in MD.

### X4 omits attributes that are zero

`<account id="[0x10c]" own="1"/>` does not mean the balance is stored elsewhere.
It means everything is zero. Once a budget was set the same element read
`min="135600" max="203400" amount="135600"`. A missing attribute is a value, not
a missing feature.

### The half-written save

X4 writes `temp_save.xml.gz` while saving and renames it afterwards. It is the
newest file in the folder exactly when the agent asks for a fresh save, and a
failed save leaves it behind indefinitely. Reading it gives "Compressed file
ended before the end-of-stream marker was reached".

Asking for an autosave every cycle also turned out to be too much: tens of
megabytes into a synced folder every few minutes, and saves started failing
outright. The agent now only asks when the newest save has actually gone stale.

### Skills run 1 to 15

Displayed as five stars, so three points per star. Measured across 101,543 skill
entries in a late-game save: every value from 1 to 15 occurs and nothing above.

A station manager on 3 points is a one-star manager with about one jump of trade
range, which is why its trader kept reporting "no trades found in allowed
sectors" while suppliers existed two jumps away.

## Prompting findings

**Say what each action type requires.** The extraction step was throwing away
perfectly good actions with reasons it invented: "assigning a miner to 'mine for
station' when it is not specified which ware". `assign_ship` needs a ship, a
station and a role, and nothing else. Listing the required fields per type, and
adding "never drop an action because some detail is missing that its type does
not ask for", fixed it.

**Run both calls at temperature 0.** On an unchanged game state, three runs gave
one command, then none, then two conflicting ones. Reasoning benefits from
sampling in a chat; an agent that touches a live game does not. Determinism made
three consecutive runs identical.

**Tell the model what the executor can do.** Where an intent fits several action
types, naming the executable ones stops the agent from expressing a doable thing
in a type it cannot perform. The analysis is untouched; only the mapping onto a
type is informed.

## Still not possible

* **Setting a station's manual prices.** `minprice` and `price` are properties
  of wares and offers, not setters, and the game's own scripts only ever compute
  prices. It looks like a UI-layer feature. That leaves "auto pricing off for
  end products" as manual work.
* **Passing a ware list through the pipe.** The Mission Director cannot parse
  strings, so a whitelist cannot travel. The executor refuses an autotrade
  action that carries one rather than executing half of it. Each ware the bridge
  understands needs its own comparison in MD; a custom order script with typed
  parameters, as `TDM_SupplyAndTradeRoutes` does, is the way out.

---

## Correction: prices and trade rules are settable, in Lua

Earlier in this document, and for most of a day of building, the conclusion was
that setting a station's prices and trade rules is not possible from a mod. That
was wrong, and wrong in a way worth recording: **the search was in the wrong
language.**

The Mission Director genuinely has no action for it. The UI does the work
through the Lua/C layer, and those functions are as available to a mod as they
are to the game's own menus:

```c
void SetContainerTradeRule(UniverseID containerid, TradeRuleID id,
                           const char* ruletype, const char* wareid, bool value);
void SetContainerWareIsBuyable(UniverseID containerid, const char* wareid, bool allowed);
void SetContainerWareIsSellable(UniverseID containerid, const char* wareid, bool allowed);
void SetContainerGlobalPriceFactor(UniverseID containerid, float value);
void SetContainerBuildPriceFactor(UniverseID containerid, float value);
void AddTradeWare(UniverseID containerid, const char* wareid);
void RemoveTradeWare(UniverseID containerid, const char* wareid);
void UpdateProductionTradeOffers(UniverseID containerid);
void SetPlayerTradeRuleDefault(TradeRuleID id, const char* ruletype, bool value);
void SetPlayerIllegalWare(const char* wareid, bool illegal);
```

Found by searching the game's own UI Lua (`ui/addons/ego_detailmonitor/*.lua`)
for C functions that write rather than read. `menu_map.lua` calls
`C.SetContainerTradeRule(container, tonumber(id), "buy", ware or "", true)`,
which is exactly the "own faction first on buy orders" rule from a strategy
document, expressed in one line.

### Why this changes the design

Look at the parameter type: **`const char* wareid`**. Wares are addressed by
name string, and Lua can take a command apart.

Every workaround in this project for "the Mission Director cannot parse strings"
exists because the command handling lives in MD:

* the inverted string match, building the expected command per ship and
  comparing whole strings;
* the hardcoded list of expandable wares, one comparison per ware;
* refusing an autotrade action that carries a ware whitelist, because the
  whitelist cannot travel.

None of those are limits of X4. They are limits of handling commands in MD. The
Lua side has string handling and takes ware ids as text, so moving command
parsing there dissolves all three at once.

MD remains the right place for what MD is good at: cues, game events, and
creating orders. The split should be by capability, not by whichever layer the
first spike happened to use.
