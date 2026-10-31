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
player's ship taking to its own defence. *Found* in ship4-camp: the disc
expansion armed every production and storage module (636 M gatlings, 48 M
shields) and neither disc; no turret has fired yet. The 270 shields still to
come held every later expansion of KYV-745 (docs/experiments.md, 2026-10-28),
so a plan now carries turrets and no shields. The game does not cancel a
running build (ship6-camp refused it twice); the situation reports one that
waits for equipment only (3765486). The discs stayed empty in ship6-camp too,
with an explicit list of turret wares: 0 of 3 armed.

**C. Money for the wharf.** The S/M Ship Fabrication Bay's blueprint is
116.4 M. The purchase job kept 20 % of the player's money back, which meant
waiting for 146 M; for a blueprint it now keeps 5 % (`BLUEPRINT_RESERVE`), so
122.5 M will do, while ship purchases keep 20 %. The player held 45 M at the
baseline; station accounts now flow back to the player above twice their
maximum. At the 2 M a game hour the rules earn, that is a matter of tens of
game hours. *Reached* in ship3-camp: 49 M to 172 M in 34.5 game hours, most
of it the game's own transfer of KYV-745's surplus (about 22.4 M every four
game hours, `md/notifications.xml`, PlayerOwnedMoneyUpdated). *Proof:* the
blueprint held.

**D. The wharf.** The bay at KYV-745 (its 5 km plot has room; GKL-870's 2 km
plot is crowded). Its construction takes 12,112 hull parts, about ten game
hours of one module, 3,312 claytronics, bought at about 2,000 each (6.8 M),
and 6,620 energy cells. A second hull parts module halves the wait and
serves the ships after it. *Written:* a plan entry `wharf: 1` (the expansion
exists). *Proof:* the bay in the save, and what it offers to build
(`GetContainerBuilderMacros`). *Reached* in ship4-camp: blueprint bought from
the Teladi at YMH-359, bay built.

**D2. A shield supply.** No station we know sells field coils or shield
components, and a ship from our wharf gets the same shields from our
blueprints as a station module does. A
field coils module (12.8 M) and a shield components module (3.2 M) at
KYV-745 take energy cells, plasma conductors and quantum tubes, and those two
are for sale (one Argon seller of plasma conductors, three of quantum tubes,
in the ship5-camp save). Until then `buildship` is to take the shields out
of the loadout it generates (`numshields`, `numshieldgroups`), as a player clearing
the slots would. *Proof:* field coils and shield components in KYV-745's
store, then shields in a plan again and built. *Reached* in ship6-camp, the
first half: both blueprints bought from the Paranid at SCY-867; KYV-745 ended
with four field coils modules (all by margin) and two shield components
modules, GKL-870 with one of each, and in the last 24 game hours KYV-745 sold
42,723 field coils and 11,577 shield components. Someone sells a few: the
build storage received 1,320 field coils and 528 shield components before our
modules ran. Shields in a plan again is the open half; `buildship` leaves
them out (b4037dd).

**E. The first ship of our own.** A Teladi M gas or solid miner: blueprint
1.19 M, a Teladi M all-round engine 0.13 M. Its hull is 109 hull parts; its
engine is engine parts and antimatter converters, its shields shield
components and field coils, its turrets turret components and advanced
electronics. At average prices that is tens of thousands of credits in wares,
against 1.07 M for a freighter bought at SCY-867. *Written:* `strategy.fleet`
asks our wharf (`buildship`) before a faction's; the save's view of what our
wharf offers. *Open:* whether the station buys the equipment wares itself and
whether a ship we build needs crew from the station's workforce. *Proof:*
the ship delivered, and what left the store for it. *Written* (b4037dd,
05966f3): blueprints the plan names are bought (ships and equipment, at the
menu's price); `own_build` sends `buildship` once an engine blueprint and the
hull's are held; the fleet rule waits for every named blueprint before buying
the hull from a faction; `offers` asks once per faction and tag what a
blueprint's sellers list, thrusters included. *Found* (ship7-camp): both
blueprints were bought and the order went in at 247.5, and nothing built
it. A wharf's queue is worked by its ship trader, which the game gives NPC
wharfs and ours lacked; and the order had no thruster, which the ship menu
does not allow, since no thruster blueprint was ours. The order waited two
game hours, so a Paranid miner was bought as the ninth instead. *Written*
(d18b540, 5b9a817): a ship trader is sent to each wharf of ours; the
plan names the generic M all-round thruster, bought from whoever the
`offers` lines say lists it; `own_build` waits for it; the bridge refuses a
loadout without an engine or a thruster. *Found* (ship7b-camp): the first
ship came. ENF-175, a Teladi solid miner, left KYV-745 8.6 game hours after
the order; the wharf put out a buy offer for the engine parts itself, and
the ship came with a pilot, a defence officer and an engineer. So the two
open questions are answered; what left the store for it is not measured.
At two hours the order counted as stuck, the two miners it was meant for
were bought from the Paranid, and ENF-175 stood idle. *Written* (62cf7b6):
an order at a wharf of ours has twelve hours.

**F. The equipment chain**, in the order the first ships need it, each a
blueprint and a module: engine parts (2.86 M; antimatter cells from
hydrogen, refined metals), antimatter converters (advanced composites from
graphene and refined metals, microchips), then shield components and field
coils (plasma conductors and quantum tubes, from graphene and superfluid
coolant, from helium), then turret components and advanced electronics
(microchips, quantum tubes, scanning arrays). Until a ware is made, it is
bought. *Proof:* a ship built from equipment we made. *Found*
(ship7c-camp): both blueprints bought from the Teladi, the antimatter cells
one on the second errand; the first modules stood at 269.2 and 270.8, and
by margin KYV-745 ended with six engine parts and five antimatter cells
modules, selling about half of what they make. No ship was ordered, so the
proof is still open.
*Found* (ship7d-camp): five Teladi M frigates came from our wharf, each
about half a game hour after its order. By recipe value 83 % of their inputs
are wares KYV-745 makes (hull parts, energy cells, field coils, shield
components, engine parts); advanced electronics, turret and weapon components
and antimatter converters are bought. What left the store for each ship is
not traced, and KYV-745 sells nearly all its hull parts.

**G. Claytronics.** 20.8 M for the blueprint; antimatter cells, microchips
and quantum tubes in. Every station module and every L or XL hull needs it,
so it is the step that frees station building from the market.

**H. Building, not buying.** Miners and traders come from our wharf; NPC
factions buy from it too, which turns our hull parts into sales where the
economy has its largest sink (`docs/forum-findings.md`). Defence fighters
for the stations follow. *Proof:* a game week in which the fleet grew
without a ship bought.
*Written* (188b169, af3344e): the plan sets defenders per station; any
combat ship of ours counts, a new one is an M frigate from our wharf, and a
ship still in the bay is on order, not ours. *Found* (ship7d-camp): 34 game
hours without a ship bought; three frigates defended from 304.9, two were
lost to the Xenon IDQ-917 at 318.9 and replaced within two game hours. One
held off Xenon fighters at GKL-870 through the run. Against an XL an M
frigate is lost, which points at stage I.

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

## Raids on the Xenon (2026-10-31)

Why now: Xenon went from 21 of 141 sectors at game hour 74 to 49 at hour 410,
and from 151 stations to 208. Teladi went from 21 sectors to 10. Two sectors
next to our route, Ianamus Zura IV and VII, were Teladi's. Protecting KYV-745
does nothing about this, and freighters keep being shot down on the way.

Numbers from the save at hour 410 and the game files. Hull, shields and damage
are worked out from the macros and the loadouts in the save, with every weapon
firing: good for comparing, not a forecast. Out of the player's range turrets
fire less (docs/forum-findings.md), for both sides.

| Ship | Hull + shields | Damage per second |
|---|---|---|
| Our Teladi destroyer | 391,000 | 11,000 (7,600 of it two forward guns) |
| Our Teladi frigate | 63,000 | 2,500 |
| Xenon K (XL destroyer) | 535,000 | 13,700 |
| Xenon I (XL carrier) | 1,438,000 | 44,800 |
| Xenon corvette | 22,000 to 24,000 | 400 to 1,700 |
| Xenon heavy fighter | 7,200 | 1,500 |
| Xenon fighter | 3,700 to 4,100 | 550 |

Xenon in all: 85 K, 4 I, 7 terraformers, about 500 corvettes, 2,000 S and 208
stations. We will not beat that, only what stands in one place.

### Can the economy carry it?

Yes on money; the limit is a few wares.

* One destroyer takes 4,960 hull parts, about 7,000 energy cells, 528 advanced
  electronics, 490 weapon components, 541 antimatter converters, 270 engine
  parts, 172 field coils, 146 shield components and 144 turret components, by
  the recipes and its loadout. That is about 2 M Cr of wares at market prices.
  ship7g built five in eight game hours from stock.
* Money: 888 M Cr unspent, and 5.5 M Cr per game hour in ship7e3 (180 M in 33
  hours). Money does not limit this.
* KYV-745's own lines, nominal rates: hull parts 3,528 per hour, so 0.7
  destroyers; advanced electronics 270, so 0.5. About one destroyer per two
  game hours once stocks are gone, unless the plan adds lines. It costs the
  hull parts we now sell. Weapon components and antimatter converters come
  from the market; we have no blueprint for either.
* A fighter is cheap: 152 hull parts and 69 energy cells for the hull. It needs
  blueprints we do not hold yet: the ship, S engine, S thruster, S weapon, S
  shield.
* Turret components were the true limit: thousands wait on the discs, one
  seller on the map holds 45. The blueprint came with the Paranid ally ceremony
  and ship8 builds the line.

### Targets within reach

| Sector | Jumps | Owner | Xenon there |
|---|---|---|---|
| Trinity Sanctum III | 1 | Paranid | 1 K, 5 M, 8 S, one base: 24 turrets, 3 build modules |
| Scale Plate Green I | 3 | Xenon | 1 M, three stations with 74 to 120 turrets each |
| Ianamus Zura IV | 3 | Xenon | 7 M, 23 S, three stations with 77 to 89 turrets |
| Memory of Profit IX | 3 | Xenon | 7 M, 15 S, three stations with 76 to 111 turrets |
| Bright Promise | 2 | Xenon | 8 K, 25 M, 84 S, three stations: the hub on the way |

The first target is the base in Trinity Sanctum III. It is the one Xenon
foothold next to us, on our trade route, in a sector Paranid still owns. Six
destroyers bring 2.3 M hit points and 66,000 damage per second against about
30,000 before the base's turrets. A full Xenon station has three to five times
those turrets, so red sectors come after that, at 20 or more destroyers.
Bright Promise is not a raid: it takes a fleet that can beat eight K.

### Does it help the factions, and can a sector change hands?

* It happens without us: since hour 74 Terran took Faulty Logic VII, Atiya's
  Misfortune I and III, Frontier Edge and Ore Belt from the Xenon, and Teladi
  took Turquoise Sea X. Sector ownership follows stations that can claim it
  (`canclaimownership`, the `defence_*_claim` modules), and factions run
  `factiongoal_hold_space` and `factiongoal_invade_space`.
* From player reports, not proven here: Xenon share one pool of resources, so a
  sector does not starve when cut off, and a destroyed station's build storage
  can rebuild it. A raid has to kill the build storage too.
* We can feed them. Faction wharfs want wares they cannot get: HOW-875 asks
  8,416 turret components at 421 Cr, CXY-258 61,036 hull parts at 276 Cr. Once
  the discs are armed, surplus goes there. A faction with wares builds warships.
* Taking a sector ourselves is not known to be possible. The claim modules are
  wares, but no blueprint for one is listed for sale, and of the faction tags
  only Terran and Kaori carry `claimspace`. To find out before planning on it:
  the game's scripts first, then a probe.

### The fleet: what we can build, and what it takes

Ship tables from the game files, for Teladi and Paranid, whose ally licences we
hold. Hull parts are for the hull alone; the blueprint is paid once.

| Ship | Hull | Turrets | Main guns | Docks | Crew | Hull parts | Blueprint |
|---|---|---|---|---|---|---|---|
| Teladi fighter 02 | 4,100 | 0 | 3 | | 3 | 146 | 1.6 M |
| Teladi frigate | 36,000 | 4 | 3 | | 15 | 985 | held |
| Teladi destroyer 01 | 104,000 | 11 | 2 | 4 S | 50 | 4,960 | held |
| Teladi destroyer 02 | 123,200 | 11 | 2 | 4 S | 44 | 6,857 | 60.3 M |
| Paranid destroyer 02 | 140,000 | 16 | 2 | 2 M, 4 S | 60 | 11,126 | 97.9 M |
| Teladi resupplier | 162,000 | 9 | 0 | 6 M, 12 S | 200 | 7,291 | 77.8 M |
| Teladi carrier | 290,000 | 13 | 0 | 6 M, 24 S | 135 | 10,462 | 111.7 M |
| Paranid carrier 02 | 303,000 | 19 | 0 | 8 M, 24 S | 143 | 16,670 | 175.4 M |

The largest we can build is the Paranid carrier 02. A Xenon I has 480,000 hull.
The carriers and the resupplier need an XL bay on KYV-745: 247.9 M for the
blueprint, and 8,902 hull parts, 2,434 claytronics and 4,866 energy cells for
the module. With 880 M unspent, the bay, a Teladi carrier and a resupplier come
to about 440 M.

**Crew.** Our own builds flew with three officers and nobody else: the bridge
passed the ship menu an empty crew list. L ships bought from a wharf do carry
crew. `buildship` now hires what the menu's own preset hires, half the capacity,
split over service and marines, from the station's workforce: 24 for a
destroyer, none for a fighter, against a workforce of 500. What service crew
brings is unclear: players report repair in the field, capped by skill, and a
developer called the values low. The six destroyers of ship8 stay without crew.
The refit needs a verb of its own.

**Fighters.** `fighters_per_destroyer` in the plan, built at our S/M wharf
(`buildship`, whether it takes S is to be proven), flown under the destroyers as
interception by `standing.wings`. Six destroyers carry 24. A raid waits for them.

**Support.** From the community wiki's page on resupply ships: a carrier repairs
and rearms S and M ships docked at it; a fleet auxiliary serves every size, but
only once assigned to a fleet or set to Supply Fleet. Players report a carrier
does not restock its own materials. The rule so far sends a damaged ship to a
wharf (`repairs`); a resupplier with the fleet is the next step after the first
raid, and needs its order in the bridge.

**What players report on fleet battles** (forums, older patches, anecdotes, no
official guide found):

* Fighters take the swarm and let the big ships work; destroyers without them
  take heavy losses.
* Xenon K close up tear apart a destroyer, whose AI tends to charge.
* A Xenon station: turrets first. Reports: 8 or 9 destroyers, a carrier with 60
  fighters and a supply ship did it; 14 destroyers and 37 heavy fighters did it
  and lost 7; 22 destroyers alone were losing ships too fast.
* Interception goes for S and M; against capital ships fighters need bombardment,
  which the bridge's `command` does not offer yet.
* Enter a Xenon sector with the fighting ships first, the carrier after.

So the sizes to aim at: 6 destroyers and 24 fighters for ships in Trinity Sanctum
III; about 10 destroyers, a carrier and a resupplier before a Xenon station.

### What to build

1. Verbs. Built, not yet proven in the game: `raid <SHIP> <SECTOR>` gives the
   Attack order the interact menu gives, on a Xenon station in that sector, or
   with no station a Patrol of the sector, as priority orders. `command` puts the
   others under it; `release` lets its own orders bring it home.
2. The rule, `standing.raids`, built, not yet proven: gather at KYV-745, go when
   the plan's `destroyers` stand at 90 % hull, come back at 75 % fleet hull, when
   half are lost or no station is left, and defend again; `repairs` takes out a
   single damaged ship. No raid on more than one Xenon XL per six destroyers.
3. Fighters for the plan: blueprints, then a `fighters` number, as `destroyers`
   has. They take the Xenon S off the destroyers, whose big guns miss them.
4. Measure: Xenon sectors and stations within five jumps, ships lost per raid
   and Teladi and Paranid sectors, in the report and in the score of each run.

In ship8-camp the Xenon base in Trinity Sanctum III was gone by game hour 410,
without us, with 6 M and 8 S left in the sector. So the first proof is clearing
those ships off our trade route, and the first station comes after that.

Order: ship8's turret line and six destroyers; the verbs; Trinity Sanctum III
as the proof, reading what it cost; then more destroyers, fighters and a red
sector with no XL. The stage is judged by the sector count around us and
by freighters lost, not by kills.
