# Plan: our own fleets, from the raw materials up (2026-10-27)

From the middle of the game on, a fleet has to come from our own production:
buying it cannot be paid for. So building ships ourselves is a goal on a
horizon of weeks of game time, and the rest of the empire is weighed against
it. Building is an investment, not a cost: a production module that has not
paid for itself after 30 game hours is early, not wrong. This plan is what
it takes, what we hold already, and the steps, each to be agreed before it is
built.

## What it takes (game data, 9.00)

**The modules.** A wharf for S and M ships is an S/M Ship Fabrication Bay
(`buildmodule_gen_ships_m_dockarea_01_macro`, ware
`module_gen_build_dockarea_m_01`, priced 86 to 116 M); fitting and repair is
an S/M Ship Maintenance Bay (`buildmodule_gen_equip_m_dockarea_01_macro`, 26
to 35 M). L and XL need the L and XL bays (up to about 245 M each) and their
maintenance bays (about 65 M). All of them are built from hull parts,
claytronics and energy cells: the S/M fabrication bay from 12,112 hull parts,
3,312 claytronics and 6,620 energy cells. The prices are the module wares'
own; what the blueprint costs at the representative is to be read in the game.

**The licence.** Building them needs `station_equip_sm` (S/M) or
`station_equip_lxl` (L/XL), which the game grants on the ally ceremony
(`md/tutorial_global.xml`: "auto-gained on 'ally'"). The baselines hold both,
from Teladi, and Teladi sell all four bays. Paranid stand at 0.125, which is
past the ally threshold of 0.1 but without the ceremony.

**A ship.** A hull is hull parts and energy cells (an M container freighter
162 hull parts, an S fighter 122). Its equipment is separate wares, each with
its own blueprint: an M engine is engine parts and antimatter converters, an
M shield shield components and field coils, a weapon weapon components and
advanced electronics, a turret turret components and advanced electronics.
The research found a 9.00 note that S/M engines and shields are now built
into the model; the game data still lists them as wares with recipes, so
that is to be checked in the game before it is relied on.

**The chain** below those, per game hour of one module:

| Ware | Made from | One module per hour |
|---|---|---|
| hull parts | refined metals 280, graphene 40, energy cells 80 | 1,176 |
| graphene | methane 320, energy cells 80 | 1,440 |
| claytronics | antimatter cells, microchips, quantum tubes, energy cells | 432 |
| antimatter cells | hydrogen 320, energy cells 100 | 2,970 |
| quantum tubes | graphene, superfluid coolant, energy cells | 470 |
| superfluid coolant | helium 320, energy cells 60 | 1,425 |
| engine parts | antimatter cells, refined metals, energy cells | 832 |
| plasma conductors | graphene, superfluid coolant, energy cells | 176 |
| shield components | plasma conductors, quantum tubes, energy cells | 579 |
| field coils | plasma conductors, quantum tubes, energy cells | 1,050 |
| antimatter converters | advanced composites, microchips, energy cells | 1,596 |
| advanced electronics | microchips, quantum tubes, energy cells | 270 |
| weapon / turret components | hull parts or microchips, plasma conductors or quantum tubes, scanning arrays | 340 |

One hull parts module makes the hulls of about seven M freighters an hour.
Everything past refined metals and microchips needs the three gases:
methane, hydrogen and helium.

## What we hold, and what is missing

* **Held:** the licences above; blueprints for energy cells, water, refined
  metals, silicon wafers, microchips, smart chips and a few food wares; S, M
  and L container and solid stores, S and M habitats; an M dock
  and an L pier; two Teladi M shields and two Teladi M turrets.
* **Missing blueprints** (module prices): every bay; hull parts (3.9 M), graphene (0.18 M),
  antimatter cells (0.44 M), superfluid coolant (0.16 M), quantum tubes
  (2.4 M), engine parts (2.5 M), claytronics (18 M), liquid storage (0.5 M),
  and the rest of the table; every ship blueprint; engines.
* **Missing in the bridge:** graphene, antimatter cells, superfluid coolant,
  plasma conductors and liquid storage are not among the expansions it can
  build (no gas inputs were added in strategy step 3).
* **Missing in the fleet:** gas miners. The four miners are solid.
* **Money:** at the end of the ceremony series the empire held 38 to 40 M
  in credits and 70 to 78 M on station accounts. An S/M fabrication bay,
  blueprint and resources, is of that order.

## Steps

| # | Step | Status |
|---|------|--------|
| 1 | Read in the game what the bays' blueprints cost at the Teladi representative, what a ship blueprint costs, whether S/M engines and shields are still fitted as wares in 9.00, and how a ship is ordered at our own wharf (who pays, what it draws from the station's store). Manual and the game's scripts first, a probe for what they leave open | scripts read (below); two points left for a probe once a wharf stands |
| 2 | The gas chain in the bridge and the rules: graphene, antimatter cells, superfluid coolant, plasma conductors and liquid storage as expansions; gas miners bought and assigned like solid ones; the first module that eats a gas adds a liquid store, as solid and container do | open |
| 3 | Hull parts first: the one end product the wharf, the bays and every hull need, and the usual shortage. A station that makes hull parts from our own refined metals and graphene | open |
| 4 | The wharf: an S/M Ship Fabrication Bay and Maintenance Bay at a station of ours, supplied with hull parts; the first ship built there, a freighter or a miner, from a blueprint we hold | open |
| 5 | The equipment chain, in the order the first ships need it: engine parts, then shields, then weapons | open |
| 6 | The strategist plans toward this, on a horizon of game weeks: the milestones above as its goal, its history judged against what the rules alone did over the same hours (the ceremony series showed it credits plans with the growth time brings) | open |
| 7 | Measure on that horizon: runs of a game week (about 30 hours of wall time under SETA), scored by the milestones reached and by sales, with net worth beside them rather than above them | open |

## Step 1: what the game's scripts say

* **Blueprint prices.** The representative's menu
  (`menu_trader_blueprintsorlicences.lua`) asks a module's maximum price and
  ten times the average price for a ship or a piece of equipment, with no
  discount; the connector blueprint was bought for exactly its maximum,
  88,348 Cr. So: S/M Ship Fabrication Bay 116.4 M, S/M Maintenance Bay
  35.2 M, hull parts 4.52 M, graphene 0.21 M, antimatter cells 0.51 M,
  superfluid coolant 0.19 M, quantum tubes 2.80 M, engine parts 2.86 M,
  claytronics 20.8 M, Teladi M liquid store 0.57 M. Teladi ships: M solid or
  liquid miner 1.19 M each, M container freighter 2.66 M, S fighter 1.64 M;
  Teladi M all-round engine 0.13 M. We hold two Teladi M shields and two M
  turrets already.
* **Our own wharf charges nothing.** The ship menu places the build with a
  price of 0 when the wharf is ours (`menu_ship_configuration.lua`:
  `menu.isplayerowned and 0`), so no money moves and the station builds from
  its own store. The bridge's `buyship` pays a faction's wharf; building at
  our own needs a variant without the transfer. Which ships a wharf offers
  comes from the engine (`GetContainerBuilderMacros`); the manual says ship
  and equipment blueprints are needed.
* **Equipment is still fitted in 9.00.** The Teladi and Paranid M container
  freighters keep their engine, shield and turret connections, and engines
  and shields are wares with recipes (an M engine is engine parts and
  antimatter converters, an M shield shield components and field coils).
* **The bill for the first ship we build.** Blueprints: the fabrication bay
  116.4 M, a Teladi M miner 1.19 M, an engine 0.13 M, and for hull parts the
  module, graphene and a liquid store, 5.3 M: about 123 M, before the bay's
  construction (12,112 hull parts, 3,312 claytronics, 6,620 energy cells;
  the claytronics bought). The empire held 38 to 40 M in credits and 70 to 78
  M on station accounts at the end of the ceremony series, so most of it
  sits on accounts, and the bridge has no verb to move money back to the
  player.
* **Left for a probe:** whether the fabrication bay fits equipment itself or
  needs the maintenance bay beside it, and how the station comes by the
  wares a build takes (buy offers, as at a faction's wharf, or only what is
  in store).

## The stages after hull parts

Each stage names what it builds, what it costs, what has to be written, and
what proves it in the game. Runs from here on continue from the last result
save (a campaign, game weeks long), so the empire keeps what it built; the
ceremony baseline stays for comparing two versions of a rule.

**A. Hull parts running (step 3).** One hull parts module at KYV-745 makes
1,176 an hour from 1,120 refined metals, 160 graphene and 320 energy cells:
half the output of one refined metals module and a ninth of one graphene
module, so the methane two gas miners bring is plenty. Surplus is sold:
wharfs and shipyards are where the economy's hull parts go. *Proof:* hull
parts in store and sold, the module not short of graphene.

**B. Defence at KYV-745.** A Teladi defence disc (0.72 M blueprint; 359 hull
parts, 98 claytronics, 196 energy cells to build), then a second if the
first holds. Whether the build fits turrets in its mounts is the first thing
to look at: we hold blueprints for Teladi M gatlings and M shields, none for
L turrets. *Written:* the `defence` expansion (done). *Proof:* turrets on the
disc in the save, and Xenon raiders at KYV-745 driven off without the
player's ship taking to its own defence.

**C. Money for the wharf.** The S/M Ship Fabrication Bay's blueprint is
116.4 M, and the purchase job keeps a 20 % reserve, so it is bought once the
player holds 146 M. The player held 45 M at the baseline; station accounts
now flow back to the player above twice their maximum. At the 2 M a game
hour the rules earn, that is a matter of tens of game hours. *Decision:*
keep the reserve for a purchase the plan sets as its goal, or lower it for
that one. *Proof:* the blueprint held.

**D. The wharf.** The bay at KYV-745 (its 5 km plot has room; GKL-870's 2 km
plot is crowded). Its construction takes 12,112 hull parts, about ten game
hours of one module, 3,312 claytronics, bought at about 2,000 each (6.8 M),
and 6,620 energy cells. A second hull parts module halves the wait and
serves the ships after it. *Written:* a plan entry `wharf: 1` (the expansion
exists). *Proof:* the bay in the save, and what it offers to build
(`GetContainerBuilderMacros`).

**E. The first ship of our own.** A Teladi M gas or solid miner: blueprint
1.19 M, a Teladi M all-round engine 0.13 M. Its hull is 109 hull parts; its
engine is engine parts and antimatter converters, its shields shield
components and field coils, its turrets turret components and advanced
electronics. At average prices that is tens of thousands of credits in wares,
against 1.07 M for a freighter bought at SCY-867. *Written:* `strategy.fleet`
asks our wharf (`buildship`) before a faction's; the save's view of what our
wharf offers. *Open:* whether the station buys the equipment wares itself and
whether a ship we build needs crew from the station's workforce. *Proof:*
the ship delivered, and what left the store for it.

**F. The equipment chain**, in the order the first ships need it, each a
blueprint and a module: engine parts (2.86 M; antimatter cells from
hydrogen, refined metals), antimatter converters (advanced composites from
graphene and refined metals, microchips), then shield components and field
coils (plasma conductors and quantum tubes, from graphene and superfluid
coolant, from helium), then turret components and advanced electronics
(microchips, quantum tubes, scanning arrays). Until a ware is made, it is
bought. *Proof:* a ship built from equipment we made.

**G. Claytronics.** 20.8 M for the blueprint; antimatter cells, microchips
and quantum tubes in. Every station module and every L or XL hull needs it,
so it is the step that frees station building from the market.

**H. Building, not buying.** Miners and traders come from our wharf; NPC
factions buy from it too, which turns our hull parts into sales where the
economy has its largest sink (`docs/forum-findings.md`). Defence fighters
for the stations follow. *Proof:* a game week in which the fleet grew
without a ship bought.

**I. L and XL.** An L fabrication bay is about 244 M. Carriers and
destroyers are what the guides name against the Xenon later in the game;
this is the stage the long horizon is for, and it is planned when H stands.

Through all of it the strategist gets the next unmet stage as its goal
(step 6), and each campaign run is reported by the stages reached, sales,
and the fleet's growth without purchases, with net worth beside them.

## Late game, besides building ships

What the research found (thin: the wiki gave little detail, the 9.00
changelog was not reached, most of this is forum posts):

* The Xenon and Kha'ak grow over time. Xenon capital ships destroy
  stations; Kha'ak mostly harass traders and miners. Posters advise four or
  five defence modules with drones and missiles on production stations,
  defence stations at key gates, and the main fleet near our production and
  miners.
* The Existential Crisis (7.00) is an opt-in endgame challenge in waves that
  grow and stack; opting out costs 500 M.
* Ship mods need research at a Player Headquarters.
* 9.00 adds Allographyne, recycled from S/M Kha'ak wrecks, which can stand in
  for any ware in production.
* Not confirmed: how large a self-sufficient economy has to be, which HQ
  research matters, terraforming, faction wars.

So the step after the wharf is defence: our stations are already attacked
(IJK-742 was lost to Xenon raiders at KYV-745 in the ceremony series), and
the ships we build ourselves are what makes a defence fleet affordable.
