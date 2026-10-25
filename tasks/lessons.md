# Lessons

One entry per mistake that cost real time, with the rule that prevents it
happening again. Evidence rather than advice: every one of these was measured,
not guessed. The long-form story of most of them is in `docs/`.

## About the game

**L1. X4 omits attributes that are zero.** `<account id="[0x10c]" own="1"/>`
does not mean the balance lives elsewhere; it means everything is zero. Once a
budget was set the same element read `min="135600" max="203400"`. A missing
attribute is a value.

**L2. There are three money scales.** Trade prices and `player.money` are in
hundredths of a credit. The save header and station accounts are in whole
credits. A logbook line once read "500871850 Cr" for a budget of 5,008,718 Cr.
Use `$value / 1Cr` when formatting money in MD.

**L3. Skills run 1 to 15, shown as five stars.** Three points per star, measured
across 101,543 skill entries. A manager on 3 is a one-star manager with about
one jump of trade range, which is why its trader reported "no trades found in
allowed sectors" while suppliers sat two jumps away.

**L4. X4 writes `temp_save.xml.gz` while saving.** It is the newest file in the
folder exactly when the agent asks for a fresh save, and a failed save leaves it
behind indefinitely. Reading it gives "Compressed file ended before the
end-of-stream marker was reached". Skip it by name.

**L5. Do not ask for a save every cycle.** Tens of megabytes into a synced
folder every few minutes, and saves start failing outright. Only ask when the
newest save has actually gone stale.

**L6. The game records why an order failed.** `<failed time=... order=...
message="No buyers found in allowed sectors."/>` sits next to the orders, with a
game timestamp. This beats anything inferable from outside: a miner that cannot
sell is still formally on a mining order, so nothing about its state looks
wrong.

**L6a. The load menu does not rescan the save folder.** X4 reads the folder at
startup and maintains its own list afterwards, adding the saves it writes
itself. A file created by an external tool while the game runs does not appear,
and going back to the menu or reloading does not help: the game has to be
restarted. Symptom: `save_011` and `save_012` absent from a list that happily
showed `save_008` through `save_010`, written by the same tool the day before.

**L6b. The load menu sorts on the date inside the file.** Not on the file's
modification time. A save copied from another one inherits its timestamp and
lands in the middle of the list, next to a nearly identically named autosave.
`edit_save.py` now stamps the current time, which is also the truthful answer,
since the file is written at that moment.

**L6c. A wharf does not look like a wharf.** No faction station macro contains
"wharf" or "shipyard"; only Xenon shipyards carry it in their own macro. Every
other one is an ordinary station that happens to hold a `buildmodule` whose
macro names a ship class, as in `buildmodule_gen_ships_m_dockarea_01_macro`.
Searching the obvious way returns nothing and reads as "we know no shipyards",
which is a wrong answer rather than an empty one.

**L6d. Sector names are not unique.** 92 display names in the lookup table
belong to more than one macro. Most are harmless, a cluster and its sector
sharing a name, but the Timelines missions reuse real sector names for their own
copies, so "Ianamus Zura IV" is both a place the player flies through and a
mission set piece. Macro to name is fine; name to macro is not, and a reverse
lookup silently picks whichever came last. It produced a confident
recommendation to build a station in a sector that turned out to be a scenario
map with no ore in it. `pretty()` now marks scenario macros, and nothing should
ever map a name back to a macro.

**L7. MD file names must be lowercase.** X4 ignores the file otherwise, without
a word.

**L6e. The bridge's `save` is an autosave, and autosaves rotate.** `save`
runs `<trigger_autosave/>`, which writes autosave_01 to 03 in turn, and the game
does the same on its own interval. Those slots hold the newest state of
whatever game was played last. A harness that loads a baseline and asks for a
save overwrites the player's latest autosave with the baseline's future. MD
has no other save action (`libraries/common.xsd`); the menus use the Lua
global `SaveGame(filename, name)` with a slot name such as `save_008`. Copy the
saves a test or a comparison depends on into `saves/reference/` (gitignored)
before running the game, and read them from there.

**L6f. A profile can have more than one save folder.** `Documents/Egosoft/X4`
held an empty numbered `save` folder beside the real one, and the empty one
sorts first. The first `experiment.py` took it: it copied nothing for safety,
watched a slot that never changed and reported its own final save as missing.
Find the folder by the save you are about to use, and refuse to run when the
safety copy is empty.

**L6g. Reputation does not grant licences; ceremonies do.** Teladi stood at
0.29 in the 105-hour save, above the 0.1 for "ally", and the player held
neither ceremonyfriend nor ceremonyally, so station_gen_intermediate and every
licence that needs them stayed closed. The ceremony is attended by the player
in person. Almost no licence has a price; tradesubscription does.

## About the bridge

**L8. `Register_OnLoad_Init` only works if the file was loaded before the
game.** It appends to a list the Lua Loader walks once, immediately after
raising its "Ready" signal, and then clears for good. A file loaded *in reaction
to* that signal arrives a frame too late, so its init never runs, `RegisterEvent`
never happens, and every forwarded command is discarded in silence. Load Lua
through `ui.xml`, which is the documented route; the MD-triggered
`Lua_Loader.Load` is legacy support for mods written before X4 7.5.

**L8a. `/refreshmd` reloads MD, but `/reloadui` does not reload our Lua.** The
file is pulled in with `require`, and the loader keeps a `modules_loaded` guard
besides, so a UI reload leaves the previously loaded chunk resident. Measured:
the deployed file contained a new diagnostic, the running code logged the old
lines. MD changes cost a chat command; Lua changes still cost a savegame load.

**L8b. Not everything in the UI layer is an FFI call.** `SetContainerWarePriceOverride` and `GetContainerWarePrice` are Lua wrappers, and they want the id
form the menus use, `ConvertStringTo64Bit(tostring(container))`, not the raw
`UniverseID` that `GetAllFactionStations` returns. Handed the cdata they accept
the call, return nil and change nothing. Three separate causes were diagnosed
and fixed before this one, all of them wrong: the price scale, a global price
factor that the game only ever applies to build storages, and a missing offer
refresh. What settled it was logging what the engine itself reported before and
after the call, rather than logging what had been asked of it. Functions called
with a `C.` prefix take the UniverseID; bare globals may not.

**L9. Space commands out by two seconds.** Sending several back to back drops
the pipe: the log showed the first command going out, then "Pipe client garbage
collected, restarting", and everything after it lost. X4 finishes processing a
command before reading the next, and the matching loop walks every ship and
station. Catch a failed write too, so one loss does not swallow the rest.

**L10. MD cannot parse strings; Lua can.** Every workaround for "the Mission
Director cannot do X" in this project was really a workaround for handling
commands in MD. Ware ids are plain strings in the Lua/C layer. Split by
capability, not by whichever layer the first spike happened to use.

**L11. Settings do not appear in the savegame.** Trade rules, price overrides
and ware toggles are invisible to the parser, so the "is this already true" gate
cannot see them and the agent re-sends them for ever. `memory.py` records them
as subject and value separately, so a value can be changed and later changed
back.

**L11a. There is no prefab construction plan for the player.**
`get_god_production_construction_plan` reads `libraries/god.xml`, where every
production entry is owned by an NPC faction. It returns null for
`faction.player` for every ware, and a `do_if` around it skips quietly, so the
whole expansion path did nothing for two days while being recorded as working.
Build the sequence with `create_construction_sequence` instead, which takes
module macros directly and extends the existing one through `base`.

**L11b. `failsafe` defaults to true, and that is not a safe default.** When the
generator cannot connect the modules it "will be added in free space without any
connections". The build is planned, the logbook says it worked, and the player
finds a module floating beside the station. Pass `failsafe="false"` and supply
every connector the station is actually built from.

**L8c. X4Mcp 1.0.6 needs OpenSSL 3 beside X4.exe.** Its DLL imports
`libcrypto-3-x64.dll` and `libssl-3-x64.dll` and the release does not ship
them. Without them X4Native's log, `x4native/x4native.log` in the X4 profile
folder, says `LoadLibrary failed (error=126)`, the game runs normally and port
7779 never opens. The game's own folder is on the DLL search path, the
extension's folder is not. Read that log first whenever the port is silent.

**L8d. X4Native's MD-event hook does not resolve on build 611726.**
`EventQueue_InsertOrDispatch`, `X4_FrameTick` and
`RadarVisibilityChanged_BuildEvent` log "missing RVA for this build?"; the
2,065 exported game functions do resolve. Typed game events from C++ are not
available on this build, so nothing here may depend on them.

**L8e. The Lua file is loaded twice, and every command ran twice.** Once
through `ui.xml`, once through the MD fallback cue, each copy with its own
locals, so a file-local "already initialised" guard let both register their
handler. Every Lua verb executed twice: invisible for a price, a double payment
for a purchase. Found by tagging each copy with an id in its log lines; one
command, two ids. The handler now lives in a global both copies see, and the
old one is unregistered before the new one goes on. Any verb that spends money
must be proven to run once before it ships.

**L8f. A host that does not plan must not ask for saves either.** `--no-plan`
turned planning off but left the "refresh the save before planning" request
in, and that request is an autosave: one harness run overwrote the player's
newest autosave (restored from `saves/reference/`). Harness runs now compare
autosave checksums before and after.

**L8g. A test that builds its own data can agree with itself and be wrong.**
`builds` on a known shipyard is `["m"]` in a parsed save; a test that wrote
`["ship_m"]` passed while the code would never have matched a real yard.
Take test data from a parsed save, or check its shape against one once.

**L8h. Declare only what the game declares, character for character.** Our
Lua file and the game's menus share one LuaJIT state, and an ffi type defined
twice must be defined the same way both times. Load ours first with one field
different, and the menu's own `ffi.cdef` fails: the player's menu breaks, far
from anything of ours. Copy struct definitions verbatim from the game's Lua
(and compare them, as was done for UIPosRot and TransactionLogEntry), and for
the ship menu's loadout and crew types declare none at all: use them only once
that menu has.

**L8i. An order that brings something is not a purchase: read who pays in
the order's own script before the first proof.** `LearnBlueprint`,
`AddBuildTask6` and MD's `add_blueprints` take no money, and neither does the
Repair order for a ship of ours: in `order.repair.xml` the transfer for
player-owned ships is commented out, because the ship menu takes the money
up front with its shopping list. The repair verb trusted a comment of ours
saying the order pays, and two repairs were free before a save gave it
away: player money after the proof was exactly the purchase plus the sale.
Every verb that gets something now pays first, at the menu's price without
its discounts, and logs the money before and after.

## About the model

**L12. Put `type` first in a discriminated union, and give it no default.** With
the inherited fields first, the union collapsed and every action came back as
`hold` while its rationale described a concrete thing to do. Valid JSON, wrong
meaning. A default is worse: a field with one is excluded from `required`, so
the model simply omits it. This trap was hit twice, once for `type` and once for
`updated_goals`.

**L13. Run both planner calls at temperature 0.** On an unchanged game state,
three runs gave one command, then none, then two conflicting ones. An agent that
touches a live game should be boring and repeatable.

**L14. Say what each action type requires.** The extraction step was discarding
good actions with reasons it invented ("it is not specified which ware"). Listing
the required fields per type, plus "never drop an action because some detail is
missing that its type does not ask for", fixed it.

**L18. Automate arithmetic, never risk.** Which ware fills a hold, what a rival
charges, whether a price is above the market: sums, and the model forgot to do
them, so Python does them every cycle and the empire runs better for it. Sending
a ship into space nobody has surveyed is not a sum. It was automated on the same
reasoning ("re-issuing an order to a ship that is demonstrably idle is not a
judgement") and it killed five scouts in an afternoon: every explorer that
actually went somewhere new was destroyed, and the only survivor was the one
that never left its own sector. The report now states the situation and leaves
the decision where it belongs.

**L19. A rule about what may never get an order goes where every command
passes, not into each thing that makes commands.** Hauls, sales, purchases and
the standing rules each skipped the ship the player sits in. The model's own
proposals did not, and the sitrep even listed that ship as idle and earning
nothing, so the first cycle with the player in the pilot seat proposed
exploring with it. The command filter in `agent.cycle` is the one place all
commands pass, and the reserved ships were already refused there; the
player's ship is now too, with a reason the next report shows.

**L20. Before a batch against a hosted model, do the sum against its daily
limit, and stop at the first per-day refusal.** The hosted route ran on a
free tier with 200,000 tokens per day, shared with another service; one
translation call is about 4,400 tokens, so the whole budget is some 45
calls. A backtest of 142 calls ran into the limit and kept retrying into
it until it was stopped, three and a half hours after it began, with every
result held back until the end. A per-day 429 now ends that model's part of the run, and
results are written after each input. The same sum rules the hosted route
out for unattended runs on that tier: at 25 cycles an hour the budget lasts
under two hours.

**L21. Score what the empire holds, not what the player's wallet shows.** Ten
runs were judged by player money. When a station grew, its store filled and
the game drew the station's budget from the player, so the run that did most
looked worst: 1.37 million per game hour against 1.82 for the game alone,
and 2.07 against 1.82 once the stations' accounts and stock were counted.
Before believing that a change costs money, look for where the money went:
an account, a store, a ship. A metric that cannot see an investment always
favours doing nothing.

**L22. Unattended runs need the game's Steam Cloud sync off.** Each run puts
the player's saves back, and Steam then finds local saves that differ from
its cloud copies. Twice in two days a launch hung on a Steam dialog waiting
for a click ("Unable to Sync", then "Cloud Conflict"), and a series stopped
for hours. Answering it is the player's choice, since one side is
overwritten; turning cloud sync off for the game is what keeps it from
coming back. The launcher's retries cannot get past it; when a launch fails
three times, look at the screen first.

**L23. Confirm a single-run finding before acting on it, and take the noise
from runs of the same kind.** Two single ablations each earned 0.22 million
credits per game hour more, four times the spread between advise runs, and
both rules were switched off by default and written down as costing income.
The run with both off then came out between the others. Runs in which a
station grows spread far more than runs of the game alone, because an
expansion finishes sooner or later and a ship is lost or not. The noise
that counts is that of the arm being compared; measure it, or run the
combination, before changing a default and before writing the cause down.

**L24. Before explaining why a thing does not work, check that it exists.**
GKL-870 refused a budget, a defender and a manager, and each refusal got its
own explanation: no manager, then no dock. The station had never been
built. Its modules sat in the save as components with state="construction",
which the parser counted as built, and the build had waited for money at
step 1 of 9 through every run since the baseline: with no money a build
storage offers to buy 0 of everything (`amount`) while it wants the lot
(`desired`), and the funding rule read `amount`, saw nothing missing, and
never sent a credit. Read what a save field means before computing on it,
and look at the object's own state before the reasons around it.

**L26. When something is suddenly easy, look at what it cost.** The first
proof run with the connector in place grew 28 modules in five game hours,
and the build storages had not spent a credit; the bridge's
`apply_construction_sequence` had been placing finished modules for free
on every working station since it was written, and the growth measured in
every run was partly that. A result that jumps should be checked against
the money before it is believed, and an action a game script uses only for
setting up a world (`apply_construction_sequence` appears in gamestarts and
story set-ups) is no way to play it. Copy what the game's own logic does in
play, here the faction logic, not the first action that works.

**L27. A group number belongs to its commander.** The save gives a
subordinate `<subordinate group="1"/>` and no commander, and each commander
numbers its groups itself. With one station that never mattered; with two,
group 1 was trade on KYV-745 and mining on GKL-870, and the fleet focus
sent four miners and a fighter of GKL-870 to sell wafers, while the report
told the model that KYV-745's traders were miners. And `set_object_commander`
is not how the game assigns: it changes the commander and leaves the ship's
order alone, where the player's menu and the faction logic use the
`AssignCommander` order, which asks `lib.request.orders` for the matching
one. Who a ship works for now comes from the bridge's own logbook line
(`executor.serves`), and assignments go through `AssignCommander`.

**L28. Value what was built at what it cost.** Net worth counted modules at
their module ware's minimum price, two to three times what building one
takes, so the run that built fifteen expensive microchip modules looked 25 %
better than two runs that ended with 29 million more in money. A score that
counts an investment above its cost rewards spending; count it at cost (or
at what it earns), and check a lead against the cash before believing it.

## About working on this

**L15. A log line must say whether it worked, not what happened.** "sending:
assign QNL-869 KYV-745 mine" looks like success and means nothing of the sort.
Three separate failures hid behind lines like that in one day.

**L16. Search in the right language before concluding something is impossible.**
Setting prices and trade rules was written off as UI-only after searching the MD
schemas. It is one Lua call. The conclusion was not wrong about MD; it was wrong
about X4.

**L17. Check which repository you are in before committing.** A commit intended
for this project landed in an unrelated one, with a message describing work that
was not in it.

**L25. A run deploys the code it measures.** The bridge was copied into the
game only by proof scripts, so a run tested whatever the last proof had left
there: half an hour of rules sending `expand ... dock` to an MD that did not
know the word, and a Lua with a probe still in it. `experiment.py` now
deploys the bridge from the checkout before it starts the game.
