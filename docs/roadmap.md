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
that is destroyed simply stops appearing, and nothing says so.

Caution learned the hard way: a **hired construction vessel comes under player
control and then leaves again** when its contract ends. Comparing fleets
naively would report every finished build as a lost ship. One such vessel was
briefly reported as an idle ship of ours and was gone an hour later, and it took
a while to establish that nothing had been lost at all. Loss detection has to
tell owned ships from rented ones before it is worth having. For unattended
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

## Growth: all three steps exist

Established 2026-08-20 by reading the game's own scripts and UI, not by asking
anyone. Together these close the gap between "plans a build" and "runs an
economy without you".

**Hiring a construction vessel.** The UI does it in two moves, and every call is
one a mod can make:

```lua
local fee = tonumber(C.GetBuilderHiringFee())
if playermoney >= fee then TransferPlayerMoneyTo(fee, ship) else return end
-- then order it to the station
C.RemoveAllOrders(ship)
local idx = C.CreateDeployToStationOrder(ship)
SetOrderParam(shipid, idx, 1, nil, stationid)
C.EnableOrder(ship, idx)
```

So "hiring" is paying a fee to somebody else's construction vessel and then
giving it a DeployToStation order. Still open: how the UI decides which vessels
are on offer.

For a builder we already own the Mission Director is simpler:
`assign_construction_vessel` followed by `deploy_construction_vessel`, which is
exactly what `order.build.deploy.xml` does with `this.ship`.

**Starting the build.** `process_build(object, build)`, as used in
`build.buildstorage.xml`.

**Buying a ship.** Real, and the hardest of the three:

```c
BuildTaskID AddBuildTask6(UniverseID containerid, UniverseID defensibleid,
                          const char* macroname, UILoadout2 uiloadout,
                          int64_t price, CrewTransferInfo2 crewtransfer,
                          bool immediate, const char* customname,
                          AddBuildTask6Container* additionalinfo);
```

Followed by `SetBuildTaskTransferredMoney`. `CanContainerBuildShip` answers
whether a given wharf can build it at all.

**The engine does not take the money.** `AddBuildTask6` has a `price`
parameter, but the payment is a separate call the UI makes itself:

```lua
TransferPlayerMoneyTo(entry.amount * (entry.price + entry.crewprice), menu.container)
...
C.SetBuildTaskTransferredMoney(buildtaskid, objectprice + objectcrewprice)
```

So an agent that calls `AddBuildTask6` and nothing else gets ships for free.
Paying is our obligation, not the game's, and it is the single thing to get
right before any of this is wired up: an agent that can conjure a mining fleet
out of nothing is not playing the same game as the player, and every conclusion
it draws afterwards is worthless.

**The loadout does not have to be assembled by hand**, which was the other
worry. The game generates one, and both helpers are globals in the menu Lua
environment this mod already runs in:

```lua
local loadout = Helper.getLoadoutHelper2(C.GenerateShipLoadout2,
                                         C.GenerateShipLoadoutCounts2,
                                         "UILoadout2", container, 0, macro, preset)
local upgradeplan = Helper.convertLoadout(0, macro, loadout, software, "UILoadout2")
Helper.callLoadoutFunction(upgradeplan, crewplan, function (lo, crew)
    return C.AddBuildTask6(container, 0, macro, lo, price, crew, immediate, name, info)
end, nil, "UILoadout2")
```

The Mission Director also has `add_build_to_construct_ship`, which
`job_helper.xml` uses to build NPC job ships. Whether that route charges the
player has not been established, and it matters: an agent that can conjure
ships for free is not playing the same game.

## Unknown

## Known gap: one full warehouse, no culprit

`focus_fleet` assumes a warehouse fills because one ware is crowding out the
rest, and it aims the fleet at that one. Measured at 49 hours: water 28%,
refined metals 24%, silicon wafers 22%, energy cells 18%. Everything is backing
up equally, no ware is above the threshold, and the fleet is correctly released
to the manager's own judgement.

Which is right, and useless. A station whose storage fills across the board is
short of transport, not short of focus, and nothing in the report says so. The
missing piece is the station's storage capacity: without it the report can say
what the distribution is but not that it is full. It is the same number the game
shows as "16,809 / 16,870", and it is not in the parser yet.

## Known gap: a ship busy doing nothing

Gate 3 refuses an order the ship already carries, which is what stops the agent
re-sending the same command every cycle. It also means a ship stuck in a
useless version of that order is invisible: three scouts sat on Explore orders
that targeted the sector they were already in, and from outside they looked
like three scouts exploring.

The savegame has what is needed to tell the difference. `orders/order/param`
carries `targetspace` as a component id, and comparing it against the ship's
own sector would show the order for what it is. That needs an id-to-sector map
the parser does not build yet.

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
- [ ] Hire a construction vessel from the Lua side, so a planned build starts
      itself. Every call is known; the missing piece is finding the candidates.
- [ ] Buy a ship through `AddBuildTask6`. Reachable, and the loadout can be
      generated rather than assembled. Pay with `TransferPlayerMoneyTo` in the
      same breath: the engine does not charge for it.
- [ ] Event-driven cadence instead of a fixed interval.
- [ ] Use `/refreshmd` and `/reloadui` in the in-game chat window rather than
      restarting the game for every bridge change.
