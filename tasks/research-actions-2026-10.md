# Research: what a commander can do in X4, and when

Written 2026-10-19 for the action catalog (`tasks/plan-catalog-2026-10.md`,
item 5.1; the situations in the last section feed 5.2). Three sources:

* **The game's files** (build 611726): every `<order>` definition in
  `aiscripts/*.xml`, 88 in all, of which 44 are player-facing and 44 are
  `internal` building blocks. Names and descriptions are the game's own
  texts. This list is complete by construction.
* **The bridge**: every Lua verb (`x4agent.lua`) and MD verb
  (`x4_agent_bridge.xml`), with its proof state from `tasks/plan-2026-10.md`.
* **The official wiki and guides** (sources at the end). The wiki's orders
  page is solid; the station and strategy material is thinner and mostly
  2020 to 2022, so numbers from it are marked unverified.

Status words: **proven** (seen working in the game with no one at the
keyboard), **built** (code and offline tests, not seen in the game),
**missing** (no verb), **not for us** (with the reason).

## Ship orders, from the game's files

| Order id | In the game | What it does | Bridge | Status |
|---|---|---|---|---|
| AssignCommander | Assign to new Commander | Put a ship under a station or a ship | `assign`, `command` (MD `set_object_commander`) | proven |
| DockAndWait | Dock and Wait | Dock at a ship or station and wait | `dockat`, `docked`, `release` | proven |
| Explore | Explore | Explore unknown space | `explore` (picks an unseen sector) | proven |
| ExploreUpdate | Revisit known stations | Refresh trade offers of known stations | `revisit` | proven |
| Patrol | Patrol | Patrol an area | `patrol` | proven |
| TradeRoutine_Basic | Local AutoTrade | Trade one ware, no gates crossed | `autotrade` | built; sent in the August live runs |
| TradeRoutine_Advanced | Advanced AutoTrade | Trade several wares; range by pilot skill (3 stars) | `autotrade` | built; sent in the August live runs |
| MiningRoutine_Basic | Local AutoMine | Mine and sell one resource locally | `automine` | built; sent in the August live runs |
| MiningRoutine_Advanced | Advanced AutoMine | Mine and sell within range (3 stars) | `automine` | built; sent in the August live runs |
| MiningRoutine_Expert | Expert AutoMine | Same, wider (4 stars, wiki) | `automine` | built; sent in the August live runs |
| SingleBuy | Buy | Buy a ware at a station | `haul` (buy leg) | built; orders left the queue unrun in the proof |
| SingleSell | Sell | Sell a ware at a station | `haul` (sell leg) | built; not run |
| FindBuildTasks | Find Build Tasks | Look for stations under construction | `findbuilds` | built; **the wiki calls this order non-functional**, to check before relying on it |
| Middleman | Fill Shortages | Bulk-buy one ware, sell to stations short of it (2 stars) | none | missing; fits a wharf short of field coils |
| GetSupplies | Get Supplies | Buy what is needed to supply other ships | none | missing |
| SupplyFleet | Supply Fleet | Supply ammunition, deployables, units to a fleet | none | missing |
| Attack | Attack | Attack a target | none (the `attack` role under a commander exists) | missing |
| AttackInRange | Attack targets in range | Attack all hostiles in an area | none | missing |
| TacticalOrder | Coordinate Attack | Fleet attack | none | missing |
| ProtectStation | Protect Station | Guard a station until told otherwise | none; `assign ... defend` covers our own stations | partly |
| ProtectShip | Protect Ship | Guard a ship | none | missing |
| ProtectPosition | Protect Position | Guard a point (a gate) | none | missing |
| Follow | Follow Ship | Follow, never defend | none | missing |
| MoveWait | Fly and Wait | Fly to a point and hold | none | missing; the safe "bring it home" order |
| MoveToObject | Fly to Object | Fly to an object and wait | none | missing |
| Wait | Hold Position | Hold | none | missing |
| Collect, CollectDropsInRadius | Collect, Collect Drops | Pick up containers | none | missing |
| CollectLockbox | Collect Lockbox | Open and collect a lockbox | `respond foundlockbox collect` (the automatic response) | proven (August) |
| CollectDeployables | Collect Deployables | Pick up our deployables | none | missing |
| MiningPlayer | Mine | Mine until full, no selling | none | not for us: AutoMine does it better (wiki) |
| Prospect | Prospect | Mark resource areas with probes | none | missing |
| Police | Police | Enforce the law in a sector | none | not for us: costs faction relations (wiki) |
| RescueShip, RescueInRange | Rescue | Pick up people in space suits | none | not for us |
| SalvageRoutine, SalvageCollect, SalvageCrush, SalvageInRadius, SalvageDeliver_NoTrade | AutoSalvage and the salvage steps | Wrecks to scrap, scrap to a processor | none | not for us yet: needs tugs and a scrap processor (ruled out in the October research) |
| DepositInventory | Deposit Inventory | Hand in the captain's inventory | none | not for us |
| Player_DockToTrade | Dock to Trade | Dock and call the player to trade | none | not for us: needs the player |
| SectorExplorer, SectorPatrol | (DLC, texts not loaded) | Default exploring and patrolling in a sector | none | missing; to look at |

Repeat Orders is not an order but a flag on a ship's queue (`<orders
loop="0">`): the bridge's `loop`, proven (3.5).

Orders the bridge uses that the game files list as `internal`: Repair
(`repair`, proven with its payment since 2026-10-19), DeployObjectAtPosition
(`satellite`, refusal proven), the build and trade steps under `haul` and
`hire`.

## Stations, spending and crew

| Action | What it does | Prerequisites | Bridge | Status |
|---|---|---|---|---|
| Operating budget | Money the manager may spend on purchases | credits | `budget <station> low/mid/high` | proven |
| Fund a build storage | Money for an expansion's wares | credits | `fund` | built |
| Prices | Sell and buy prices of a ware | manager | `price`; Python owns sell prices | proven |
| Trade rules | Who may trade with a station, per ware | none | `traderule` | built |
| Buy or sell a ware at all | Offer on or off per ware | manager | `tradeware`, `sellware` | proven |
| Limits | Stock thresholds for buying and selling | manager | `limit` (raise only) | proven |
| Expand production | Add a production module to an own station | blueprint, money, a builder | `expand` for energycells, water, refined metals, silicon wafers | built; the Claude models also asked for storage and end products |
| Storage modules | More solid, container or liquid storage | blueprint, builder | none | **missing; the first action of every Claude model on the 73-hour save** |
| Habitation | Workforce for more output | blueprint, builder | `expand ... habitation_<race>` | built |
| New station on a plot | A second site | plot, blueprints, money | none | missing (belongs with 2.3) |
| Construction plan | Apply a designed layout | holomap | none | blocked (2.3) |
| Hire a builder | NPC construction vessel for a build | money (50k on the wiki, unverified) | `hire` | built |
| Supply our build storage | A freighter brings a build's wares | a free freighter | `assign ... buildstorage` | proven |
| Buy a ship | At a wharf, with a loadout | licence, money, the wharf's stock | `buyship` | purchase proven; the wharf waits for wares; price now as the menu |
| Sell a ship | At a shipyard | ship docked or nearby | `sellship` | proven |
| Buy a blueprint | Module blueprint from a faction | licence, a docked ship | `blueprint` | proven |
| Licences | From faction ceremonies the player attends | reputation, presence | `licence` | refusal proven; not buyable unattended |
| Refit or upgrade | New equipment at an equipment dock | money | none | missing |
| Repair | Hull back to full at a wharf | money | `repair` (priority, paid) | proven |
| Resupply | Ammunition and deployables level | money | `resupply` | proven |
| Crew skill | Seminars for a manager or pilot | the seminar in the player's inventory | `seminar` | refusal proven |
| Crew transfer | Move a good pilot to a better ship | two own ships | none | missing |
| Turrets | Station turret behaviour | none | `turrets` | proven |
| Encounter responses | Claim abandoned ships, collect lockboxes, react to police and pirates | none | `respond` | proven (August) |
| Satellites | Deploy for trade information | satellites aboard | `satellite` | refusal proven |
| Blacklists | Keep traders out of dangerous sectors | none | `avoid hostile` | built |
| Research, diplomacy, boarding, terraforming | HQ research, embassy and agents, marines, planet projects | the HQ, marines | none | not for us yet (October research) |

Bridge verbs that report or run the harness rather than act in the game:
`ledger` (a station's purchases from NPCs, proven), `signals` (lists the
signals the engine accepts), `panel` (the in-game panel, proven), `save` and
`savegame` (saves for the cycle and the harness), `seta` (time warp for
measured runs).

## Situations and what the guides do there

The starting point for 5.2. Each row still needs a detector against the
parsed save; the third column says what in the save shows it.

| Situation | In the save | Actions guides recommend | Source |
|---|---|---|---|
| A ship with no orders | first order Wait or none, no assignment | a default behaviour (AutoTrade, AutoMine, Patrol) or an assignment | S1, S2 |
| A station's storage nearly full, production stalls | storage fill per transport type, `executor.storage_fill` | more storage, more traders or consumers, less production | S5, S6 |
| A station without operating budget | no `account` amount on the station | set a budget | S4, guidelines |
| A station with too few traders or miners | subordinates per role against its wares | assign free ships of the right type | S4, S7 |
| A station not selling | open sales, outside traders zero | Python's prices, a trader, a better manager | S4, S6 |
| A build waiting for resources | build storage processor `waitingforresources` | a freighter for the build storage, funding | S4, 4.1 |
| A build waiting for a vessel | processor `vessel_required` with no builder | hire a builder | 2.2 |
| A ship under fire or damaged | logbook ATTACKED lines, hull below 70 % | bring it home, repair, defenders | S3, S8, 4.8, 4.9 |
| A trader keeps dying in a sector | DESTROYED lines in one sector | blacklist the sector; escape as the pirate response | S3, S8 |
| Idle capital | player money above the reserve | ships at known wharfs, a blueprint, an expansion | S5, guidelines phases |
| A ware the market lacks | known buy offers with no known seller | produce it, or Fill Shortages with a trader | S7 |
| A market already flooded | many sellers at low prices | do not add production of it | S5, S7 |
| Scouts on covered ground | explorer in an explored sector | send to unseen sectors, satellites | S1, 4.4, 4.5 |
| Crew too weak for a behaviour | pilot skill under the behaviour's stars | seminars, swap pilots | S1, S2 |
| A manager too weak for range | management stars under 3 | seminar | S6, S7, 4.2 |
| An abandoned ship seen | encounter response not set to claim | set Claim | S2, 4.13 |
| Wares needed for our own build sold to others | build storage short of a ware the station sells | trade rule own faction for that ware | S4, S9 |

## Mistakes the guides warn about

Building or buying too much too early (a large warship fleet, blueprints that
pay back only in bulk); letting storage fill; neglecting energy cells; one
giant factory instead of linked smaller ones; flooding low-price markets;
small miners where Kha'ak roam; expensive stations in hostile sectors; a
shipyard before its supply chain; changing a built module (it is recycled
with a loss); clearing a combat ship's orders without a Fly and Wait (it goes
back to its target); Police as a default (it costs relations); and, per the
wiki, Find Build Tasks, which it calls non-functional.

## Gaps and conflicts

* **Find Build Tasks**: the wiki calls it non-functional; the bridge's
  `findbuilds` (4.15) relies on it. Check in the game before 4.15 counts.
* **Repeat Orders** needs 0 or 1 pilot stars; the two wiki pages disagree.
* Not found in readable form: the wiki pages on stations, trade rules and
  budgets; licence rules and costs; workforce mechanics; how claiming works
  in detail; anything 9.0-specific. The numbers on plot tax, the builder fee,
  "ten miners for a first station" and "three traders per station" are single
  sources from 2020 to 2022.

## Sources

| | Page | Used for |
|---|---|---|
| S1 | Egosoft wiki, "Orders, Behaviours and Assignments" (wiki.egosoft.com, X4 Foundations Wiki, Manual and Guides) | orders, behaviours, assignments, skill stars |
| S2 | Egosoft wiki, X4 Manual, "NPC Behaviours" | behaviours, removing orders, crew skills, encounter responses |
| S3 | ludo.guide, X4 fleet logistics and supply chains | hubs, supply ships, repair, blacklists |
| S4 | magicgameworld.com station building guide | build steps, manager, build storage, pricing |
| S5 | alittlebithuman.com X4 tips, October 2025 | phase advice, mistakes (generic) |
| S6 | Steam discussion 4402812641372446918, June 2021 (a developer quoted) | station pricing, managers |
| S7 | Steam discussion 3770112515497894744 | manager range, economy gaps, shipyard cost |
| S8 | Steam discussions on Xenon and Kha'ak defence (search snippets) | defence tactics, anecdotal |
| S9 | Steam discussions on trade rules and blueprints (search snippets) | trade rules, blueprints, wharf economics |
| S10 | Egosoft wiki, Feature Development Overview | which version added what |
| S11 | news coverage of the 7.00 and 8.00 updates | Timelines, diplomacy |
