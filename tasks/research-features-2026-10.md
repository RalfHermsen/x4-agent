# Research: functionality worth adding beyond the October plan

Written 2026-10-18 against build 611726, as input for `tasks/plan-2026-10.md`.
Nothing here is planned or tested yet.

## Method and gaps

Game side: the UI Lua, `libraries/`, `aiscripts/` and `md/` were extracted with
`gamedata.py`; the UI Lua's `ffi.cdef` blocks give 1,924 C signatures; every
order definition was read with its English name; `libraries/common.xsd` gave MD
actions, events and assignment values with their documentation; for each
candidate the calling menu was read for preconditions and for who pays.
In-game evidence is the agent's latest save (73.6 game hours, 23 ships, 40.4M
Cr), including the logbook lines the bridge's `signals` verb wrote. Community
side: the Egosoft forum, Steam Workshop and discussions, GitHub READMEs, and
the `content.xml` of the four third-party gameplay mods installed here. Not
covered: Reddit (unreachable to the tools), Nexus pages (HTTP 403, known from
search summaries, marked hearsay), any in-game test, or the mission and
diplomacy scripts in full.

## Candidates

Ordered by the roadmap's failure modes: stalls, bleeds, gets shot, then growth,
then trust. A file name without a folder is in `ui/addons/ego_detailmonitor/`
(`helper.lua` in `ego_detailmonitorhelper/`) or in `aiscripts/`.

| # | Candidate | What it lets the agent do | Primitive (exact name, file) | Certainty | Effort | Overlaps | Source |
|---|-----------|---------------------------|------------------------------|-----------|--------|----------|--------|
| 1 | Own traders feed build storages (stalls) | An expansion gets its wares from our ships, not from passing NPC traders | `set_object_commander` with `assignment.tradeforbuildstorage`: "Trades for a station's buildstorage. Only available to station subordinates." (`libraries/common.xsd`) | verified | small | 1.5, 1.6 | game; Steam: uneven when prices are poor (hearsay); Mules, Supply and Warehouses Extended: build storages first (hearsay) |
| 2 | Managers with range (stalls) | Make the best-skilled crew member a manager, or spend a held seminar on the current one | `AssignHiredActor(GenericActor actor, UniverseID targetcontrollableid, const char* postid, const char* roleid, bool checkonly)` with `"manager"` (`menu_map.lua`); `add_skill` then `remove_inventory` (`md/conversations.xml`, giving a seminar) | verified; whether the crew must be docked there: unknown | medium | none | game; L3; guidelines §4; Subordinates config unlocker README, GitHub (read): subordinates' range sliders are locked |
| 3 | Stock, buy and sell limits (stalls, bleeds) | Keep a reserve of what our own modules eat; stop one ware crowding out the rest | `SetContainerBuyLimitOverride(UniverseID containerid, const char* wareid, int32_t amount)`, `SetContainerSellLimitOverride(...)`, Lua global `SetContainerStockLimitOverride(container, ware, value)` (`helper.lua`) | verified | small | 3.1, 3.2 | game; Steam (hearsay) |
| 4 | Revisit known stations (stalls, bleeds) | Refresh offers around our stations without entering unsurveyed space | order `ExploreUpdate`: "Revisit already known stations in a known sector to update trade offers.", params `destination`, `radius`, `timeout`, `deploysatellites` (`order.move.recon.update.xml`) | verified | small | none | game; L18; Steam: offers go stale with no ship or satellite in range (hearsay) |
| 5 | Satellites at trade partners (stalls, bleeds) | Permanent visibility for managers and for repricing | orders `DeployObjectAtPosition` (`destination`, `objectstodeploy`, `amountstodeploy`; `menu.orderDeployAtPosition`, `menu_interactmenu.lua`) and `DeployObjectsAtGates` (`targetsector`, `deployablecategory`) | verified | medium | none | game; Satellite Network mod, Egosoft forum (thread read); guidelines §4, §8 |
| 6 | One-off hauls (stalls) | Buy a named shortage from a known seller under a price cap and bring it home | orders `SingleBuy` (`ware`, `locations`, `maxamount`, `pricethreshold`) and `SingleSell` (`order.trade.single.buy.xml`, `order.trade.single.sell.xml`) | verified; selling into our own station plausible | medium | 3.5 | game; agent log: `purchase` dropped as advice 34 times ("KYV-745 needs 200 smartchips; JAR-836 sells it at 66 Cr.") |
| 7 | Bleed meter (bleeds) | What each station paid NPC sellers, per ware, as a number | `GetTransactionLog(TransactionLogEntry* result, uint32_t resultlen, UniverseID componentid, double starttime, double endtime)`; the entry has `buyerid`, `sellerid`, `ware`, `amount`, `price` (`helper.lua`) | verified | small | 1.7, 3.1 | game; Trade analytics mod, Nexus 764 (search summary, hearsay) |
| 8 | Early warning (gets shot) | Know at once that a hostile entered our sector, or what hit or killed one of ours | `AddPlayerAlert2(PlayerAlertInfo2 alert)` (`menu_playerinfo.lua`); MD events `event_player_alert`, `event_player_owned_attacked`, `event_player_owned_destroyed` (`common.xsd`) | verified | medium | 1.3, 3.3 | game |
| 9 | Repair (gets shot) | Send a damaged ship to a shipyard; the game charges and logs it | order `Repair` ("destination MUST have a ship trader"), pays with `transfer_money from="this.owner"`, logs "They have paid the station" (`order.repair.xml`) | verified; hull share from the save plausible (`<hull value>` only) | small | none | game; Mobile Repair Service mod (Workshop mirror, hearsay) |
| 10 | Automatic resupply (gets shot) | Ships restock missiles, drones and deployables themselves | `SetPlayerGlobalLoadoutLevel(float value)`, "Default setting for automatic resupply": Off, Low, Medium, High = 0, 0.1, 0.5, 1.0; reset sets 0 (`menu_playerinfo.lua`) | verified | small | none | game |
| 11 | Patrol home sectors (gets shot) | Spare fighters patrol where our stations are | order `Patrol` (`space`, `pursuetargets`, `pursuedistance`) (`order.fight.patrol.xml`) | verified | small | 3.4 | game; Sector Patrol mod (installed, `content.xml` read): vanilla patrol "way too slow to react on threat" |
| 12 | Combat standing settings (gets shot) | Station turrets engage; fire authorisation per faction | `SetAllTurretModes(UniverseID defensibleid, const char* mode)`, modes `defend`, `attackenemies`, `attackcapital`, `attackfighters`, `missiledefence` (`menu_map.lua`); `CreateFightRule(FightRuleInfo info)`, `SetPlayerFightRuleDefault(FightRuleID id, "attack", bool)` (`menu_playerinfo.lua`) | verified | small | 3.3 | game; Steam (hearsay) |
| 13 | Derelicts: claim and sell (growth) | Turn abandoned ships into cash, open lockboxes | existing verb: `respond foundabandonedship claim`, `respond foundlockbox collect`; `ClaimShip(UniverseID shipid, UniverseID shiptobeclaimedid)` (`menu_interactmenu.lua`); price `GetTotalValue(ship, true, shipyard)`, `TransferMoneyToPlayer(totalprice, shipyard, "sellship")`, then `SellPlayerShip(UniverseID shipid, UniverseID shipyardid)` (`menu_map.lua`) | verified | small, then medium | none (schema has `claim_ship`) | game; guidelines Phase A.1; Steam (hearsay) |
| 14 | Mimic fleets (growth) | Change one leader, the fleet follows; fewer pipe commands (L9) | `assignment.assist`: "Inherits the commander's default order" (`common.xsd`) | verified | small | 3.4 | game; Autotrader Skill Rebalance (installed, `content.xml` read) recommends it |
| 15 | Prospecting (growth) | Find dense fields for miners and new stations | order `Prospect`: "Find resource areas and mark them with resource probes." (`order.mining.prospect.xml`); `assignment.prospect` | verified; reading the results plausible | medium | none | game |
| 16 | Own builder finds our builds (growth) | A construction vessel we own serves our expansions unasked | order `FindBuildTasks`, `playeronly` defaults to `this.ship.isplayerowned` (`order.build.find.task.xml`) | verified | small | 2.2 | game |
| 17 | Trade subscriptions (growth) | One faction's offers visible everywhere | licence type `tradesubscription` (`libraries/factions.xml`: 10k to 16M Cr, precursor `ceremonyally`), via the 2.1b verb | verified data; effect plausible | small after 2.1b | 2.1b | game; Steam (hearsay) |
| 18 | Missions we already fulfil (growth) | Income and reputation from supply, satellite and resource missions | `SignalObject(menu.missionData.offeractor, "accept", ...)` (`menu_missionbriefing.lua`); `GetCurrentMissionOffers`, `AbortMission(MissionID)` (`menu_map.lua`) | verified accept; completion tracking unknown | large | 2.1b | game; guidelines Phase A.4 |
| 19 | Research at the HQ (growth) | Keep research modules busy | `StartResearch(const char* wareid, UniverseID researchmoduleid)` (`menu_research.lua`) | verified; needs the HQ | medium | none | game |
| 20 | New station on a plot (growth) | Phase B's first stations | `ReserveBuildPlot(UniverseID sectorid, const char* factionid, ...)` (`menu_map.lua`), `GetBuildPlotPrice`, `PayBuildPlotSize` (`helper.lua`) | plausible | large | 2.3 | game |
| 21 | Diplomacy (growth) | Improve relations, negotiate trade deals | MD `create_diplomacy_action_operation` (`common.xsd`); actions and costs in `libraries/diplomacy.xml` | plausible | large | 2.1b | game |
| 22 | Boarding (growth) | Capture L and XL ships | `CreateBoardingOperation(UniverseID defensibletargetid, const char* boarderfactionid, uint32_t approachthreshold, uint32_t insertionthreshold)`, `StartBoardingOperation` (`menu_map.lua`) | verified | large | none | game; guidelines Phase C.2 |
| 23 | SETA in measured runs (trust) | Run 2.4's experiments at up to 6x game speed | MD `toggle_timewarp` ("Activation requires that SETA is in the player's inventory"), `set_timewarp_factor` ("limited to between 0.1 and 6.0") (`common.xsd`) | verified; needs `inv_timewarp`, absent from the latest save | small | 2.4, which says SETA is not scriptable | game |

## The top eight, as this agent would do them

**1. Own traders feed build storages.** Python, not the model: a build storage
with a build queued and open buy offers (parsed for 1.5) is about to stall.
Python picks a trader already assigned to that station, or an idle freighter
of the right cargo type, and sends `assign <ship> <station> buildstorage`: one
more branch in the MD assign cue, beside `trade`, `mine` and `defend`. Proof:
the next save shows the commander and assignment (3.4 reads them), and 1.6's
stage 4 moves. Money: the build storage buys at market prices from its own
account, which 1.5 funds. When 1.6 reaches stage 5, Python sends the ship back
to `trade`.

**2. Managers with range.** The report already prints TOO LOW for managers (0
and 2 stars in the comparison runs) and nothing acts on it; L3 is the cost.
Python looks for (a) a management seminar of the matching level in the
player's inventory, which MD applies as the conversation does, `add_skill` of
3 points capped at 15 and then `remove_inventory`, so the seminar is used up;
or (b) a better
manager among our crews (person and ship from the save), moved with
`AssignHiredActor(..., "manager", nil, false)` once the `checkonly` call
returns no reason. The model only decides whether a seminar is worth spending.
Proof: the manager's skill in the next save. Money: none.

**3. Stock, buy and sell limits.** From the station's recipes (3.2's ware
table) and stock, Python sets a sell limit of a few hours' own use on every
input it also produces, so the manager never sells what the next cycle needs,
and, when 3.2 finds one ware filling storage, a stock limit that leaves room
for the rest. A Lua verb `limit <station> <ware> buy|sell|stock
<amount|clear>` logs the game's own getters (`GetContainerBuyLimit`,
`GetContainerSellLimit`) before and after, as `price` does since L8b; the
stock setter is a bare global, so it gets the menu's id form. `memory.applied`
dedupes it, because settings are not in the save (L11). Proof: the logbook
line and the next save's offer amounts. Money: none.

**4. Revisit known stations.** Repricing will not cut a price with fewer than
two known buyers, and the only way to learn more buyers was Explore, which
cost five scouts (L18). `ExploreUpdate` revisits stations already known, in a
known sector. Python names the station of ours whose sector has the fewest
known buyers of our wares; the model decides whether a free scout is better
used that way. MD finds the station by its code, as `assign` does, and creates
the default order (`destination` its sector, `radius` 350 km, `timeout` -1 s
for indefinite, `deploysatellites` off). Proof: the default order in the next
save. Money: none while `deploysatellites` is off.

**5. Satellites at trade partners.** The latest save holds 5 satellites or
probes of ours against 32 Argon satellites; guidelines §4: a partner the
manager cannot see does not exist. Python ranks the gaps: stations that
trade our wares, in sectors without a satellite of ours. Lua creates
`DeployObjectAtPosition` as the interact menu does (the sector plus an offset
near the station, `eq_arg_satellite_01_macro`, amount 1) for a ship with
satellites aboard; `DeployObjectsAtGates` signals the game's resupply for its
deployable category itself. Proof: a new satellite of ours near that station
in the next save. Money: satellites come through the game's own resupply at
market price (4,885 Cr average in `wares.xml`), never spawned.

**6. One-off hauls.** The model already asks for this; the executor drops it
as advice. Python validates and sizes it: the seller is known with stock at
or under the cap, the shortfall sets the amount, the hold caps it, and the
ship is a free trader of the right cargo type. Lua creates `SingleBuy`
(`locations` the seller, `maxamount`, `pricethreshold`) and then `SingleSell`
to our station, through `CreateOrder` as `dockat` does. Proof: the cargo, then
the station's stock, in the next saves. Money: the game's own trade at the
seller's price, never above the cap. Build it as the first half of 3.5: the
same two orders without the loop.

**7. Bleed meter.** The save's economy log (`<log type="trade">`) records
owner, ware and value but no counterparty, so the parser cannot tell an NPC
purchase from a delivery by our own miners. A Lua verb `ledger <hours>` sums
`GetTransactionLog` per own station over that window, purchases whose seller
is not ours, per ware, and writes one logbook line per station, which the
parser reads as 2.1a reads Lua refusals. Python puts it in the scorecard (1.7)
and checks 3.1 and the own-faction rule against it: NPC purchases of a ware our
miners deliver should go to zero. Money: none.

**8. Early warning.** A destroyed ship vanishes from the save with its killer.
X4Native's events do not resolve (L8d); these are MD events. MD cues on
`event_player_owned_attacked` (throttled per object),
`event_player_owned_destroyed` and `event_player_alert` write a logbook line
(object, attacker faction, sector) and send `event <kind> <code>` up the pipe;
the host then runs a model cycle past 1.3's quiet time. Lua sets one player
alert per sector holding a station of ours, with the hostile factions from
3.3 as the space-separated `objectowner`, so an arrival is news before
anything is shot. Proof: the logbook lines and the forced cycle in the host
log. Money: none.

## Checked and ruled out

* **Lost ship replacement** (`SetFleetManagement`, "Enable Lost Ship
  Replacement"): `md/fleet_reconstitution.xml` enables it only once the player
  owns a station that can build ships; a forum mod thread says default orders
  never request one (hearsay). Revisit with an own wharf.
* **Ventures** (`AreVenturesEnabled`, `IsOnlineEnabled`, `WasSessionOnline`):
  online, results come from a server, nothing provable from a save.
* **Refuelling**: X4 ships burn no fuel. "Fuel" in `wares.xml` is engine mod
  parts and the consumer ware Space Fuel; there is no fuel API.
* **Station drones** (`SetSupplyManual(container, "units_trade", ...)`,
  `UpdateSupplyOverrides`): automatic unless switched to manual; nothing
  observed failing.
* **Recycling and salvage**: `Recycle` needs a shipyard build task (selling,
  row 13, is simpler); `SalvageRoutine` and `assignment.salvage` need a scrap
  processor and tugs we lack.
* **Ship stances** (`SetShipStance`): the only stance defined, in a small DLC,
  is one ship's cloak.
* **Workforce fill** (`SetContainerWorkforceFillCapacity`): belongs to 3.7.
* **Buying seminars**: the inventory menu pays and then calls
  `TransferInventoryToPlayer(ware, amount, trader)` with the player at the
  trader; its remote drone variant is commented out. Applying held seminars
  (row 2) stays.
* **Hiring crew** for a claimed ship: the map menu pays `$HiringFee` with
  `TransferPlayerMoneyTo`, then calls `AssignHiredActor`; a step of row 13.
* **Repeat orders**: already 3.5, but its open question is answered in
  `menu_map.lua`: `RemoveAllOrders`, `CreateOrder(ship, "Wait", true)`,
  `EnablePlannedDefaultOrder(ship, false)`, `SetOrderLoop(ship, 0, false)`;
  `SetCurrentLoopOrder` moves the loop index.
