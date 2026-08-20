# Roadmap: what an unattended empire still needs

Written 2026-08-20, after the agent had been running against a live game for a
day. Ordered by what actually limits playing unattended, not by what is
interesting to build.

Each item says how sure the mechanism is. "Verified" means the primitive was
found in the game's own schemas or Lua and its signature read; "plausible" means
the pieces look present but nothing was tested; "unknown" means exactly that.

## The economics behind the ordering

An unattended empire fails in three ways, in this order of likelihood:

1. **It stalls.** An input runs out, nobody nearby sells it, and everything
   downstream stops. This is what happened on day one: a station starved on
   water while its miners sat docked.
2. **It bleeds.** The manager buys from NPCs what your own ships could deliver,
   or sells an end product at the floor price because storage filled up.
3. **It gets shot.** Ships and stations are lost and nothing notices, because
   nothing is watching.

Self-sufficiency beats efficiency, and efficiency beats growth, because a stalled
chain earns nothing however well priced it is.

## Now: close the loop the game already handed us

The reference game's chain is worth spelling out, because it is typical:

```
water          = 60 energycells + 320 ice
sunriseflowers = 30 energycells + 80 water
```

Ice is solid-minable. So a station producing its own energycells and water needs
nothing from outside except mined ice, and the solid miners that were sitting
idle become the thing that keeps it alive. One `expand_station water` turns an
external dependency into an internal one and gives two ships a job.

The general rule the agent should learn from this: **an input with no known
seller is a reason to produce it, not a reason to keep looking**, as long as its
own inputs are mineable or already produced.

## Done since this was written

**Trade rules.** `set_trade_rule` reaches the game through the Lua side: the
agent creates one empire rule, `x4-agent: own faction only`, and points a
station and ware at it. That is "buy this only from our own ships", which stops
a manager paying an NPC for ore our own miners already deliver. See
[phase3-acting.md](phase3-acting.md) for what the arguments actually mean.

**A Lua layer that runs.** Both Lua verbs were dead until 2026-08-20: the
init never executed, so nothing forwarded from MD was ever handled. Fixed, and
confirmed from inside the game. See `tasks/lessons.md` L8.

**Ships say why they are stuck.** X4 records the reason an order failed, with a
timestamp, so the sitrep reports it with how long it has been going on rather
than guessing from the outside.

## Verified mechanisms, not yet wired up

**Turning wares on and off.** `SetContainerWareIsBuyable` and
`SetContainerWareIsSellable`, both taking the ware as a string. Already written
on the Lua side, not yet exposed as an action. The obvious use: stop buying an
input the moment the station starts producing it.

## Plausible, needs building and testing

**Notice losses.** The agent remembers what it did but not what it had. A ship
that is destroyed simply stops appearing, and nothing says so. For unattended
play this may matter more than anything else on this list, and it needs no new
game API: compare the fleet against the previous cycle, which the memory store
already persists.

**Threats in the sitrep.** `Threat` exists in `schemas.py` and is never filled.
Until it is, the model cannot reason about safety at all, and the guidelines'
entire combat chapter is unreachable.

**Repeat orders.** The model asks for them constantly, and they are the one
thing in the strategy document that stays structurally out of reach. X4 builds
them as a looping order queue rather than a single order, so `set_current_loop_order`
is the likely route.

**Habitation and workforce.** More production from the same modules, which is
the cheapest yield increase in the game. Probably another construction plan
source rather than a new mechanism.

## Unknown

**Buying ships.** This is the real ceiling on unattended growth: the agent can
run an empire but cannot enlarge it. Whether a mod can buy a ship at a wharf has
not been established, and no claim is made here either way.

## Structural, no new capability needed

**Event-driven cadence.** The loop runs every few minutes whether or not
anything changed. Running it on meaningful deltas instead would cut most of the
work and react faster to the rest.

**Write the policy down.** Twice now the agent behaved oddly and the cause was a
gap in `guidelines.md`, not in the code. Miners sat idle because the rules say
to prefer station-assigned mining and never say what to do when no station wants
minerals. That kind of fix costs one line and no restart, and it is the cheapest
way to make the agent smarter.


## The list, as items

Roughly in order. Each one is a change to this repo unless it says otherwise.

- [ ] Expose `tradeware` as an action, so the agent can stop a station buying an
      input it now produces itself.
- [ ] Notice losses: compare the fleet against the previous cycle and report
      what is no longer there. Needs no game API.
- [ ] Fill `Threat` in the sitrep, so the guidelines' combat chapter becomes
      reachable at all.
- [ ] Repeat orders, most likely through `set_current_loop_order`.
- [ ] Habitation and workforce expansion, probably another construction plan
      source.
- [ ] An in-game panel: standing goals, recent actions, ships the game reports
      as failing. Simple Menu API, already installed.
- [ ] Interact menu entries: hand a ship to the agent, or take it back. Makes
      "the player outranks the agent" a button rather than a code comment.
- [ ] Establish whether a mod can buy a ship at a wharf. Unknown, and it is the
      ceiling on unattended growth.
- [ ] Event-driven cadence instead of a fixed interval.
- [ ] Use `/refreshmd` and `/reloadui` in the in-game chat window rather than
      restarting the game for every bridge change.
