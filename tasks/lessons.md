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

**L7. MD file names must be lowercase.** X4 ignores the file otherwise, without
a word.

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
