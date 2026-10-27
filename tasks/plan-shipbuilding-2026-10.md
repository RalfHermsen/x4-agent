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
| 1 | Read in the game what the bays' blueprints cost at the Teladi representative, what a ship blueprint costs, whether S/M engines and shields are still fitted as wares in 9.00, and how a ship is ordered at our own wharf (who pays, what it draws from the station's store). Manual and the game's scripts first, a probe for what they leave open | open |
| 2 | The gas chain in the bridge and the rules: graphene, antimatter cells, superfluid coolant, plasma conductors and liquid storage as expansions; gas miners bought and assigned like solid ones; the first module that eats a gas adds a liquid store, as solid and container do | open |
| 3 | Hull parts first: the one end product the wharf, the bays and every hull need, and the usual shortage. A station that makes hull parts from our own refined metals and graphene | open |
| 4 | The wharf: an S/M Ship Fabrication Bay and Maintenance Bay at a station of ours, supplied with hull parts; the first ship built there, a freighter or a miner, from a blueprint we hold | open |
| 5 | The equipment chain, in the order the first ships need it: engine parts, then shields, then weapons | open |
| 6 | The strategist plans toward this, on a horizon of game weeks: the milestones above as its goal, its history judged against what the rules alone did over the same hours (the ceremony series showed it credits plans with the growth time brings) | open |
| 7 | Measure on that horizon: runs of a game week (about 30 hours of wall time under SETA), scored by the milestones reached and by sales, with net worth beside them rather than above them | open |

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
