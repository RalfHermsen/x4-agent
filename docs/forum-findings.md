# What the Egosoft modding forum knows

Read through on 2026-08-19: the
[X4 Scripts and Modding forum](https://forum.egosoft.com/viewforum.php?f=181),
plus two Steam discussions. Collected here because several of these answer open
questions in this project, and one of them answers a question we had already
given up on.

## The one that matters most: telling player orders from script orders

Thread: [Checking whether an order was directly issued by player](https://forum.egosoft.com/viewtopic.php?t=476337)

An agent that issues orders must not stomp on orders the player gave by hand.
Nothing in the Mission Director obviously exposes that difference, and the first
answer in the thread confirms it: the MD language does not expose the parameter,
though the Lua bindings show
`CreateOrder3(UniverseID controllableid, const char* orderid, bool defaultorder, bool isoverride, bool istemp)`.

Then j.harshaw of Egosoft answers: many orders carry an `internalorder`
parameter, "set to true if the order is created by another order", readable as:

```
$order.$internalorder
```

With the caveat, from the same post, that "not all orders have this parameter
and there is no guarantee that it will be present in all order scripts".

That gives us a real mechanism for a rule we want: leave alone what the player
set by hand. It also explains something we had already observed. The Explore
order this agent created showed up in the savegame as `temp="1"`, which lines up
with the `istemp` flag in that Lua signature.

## Live telemetry has prior art

The index thread points at an **X4 RestServer** alongside the Named Pipes API,
described as external HTTP API access. Could not confirm it further from search,
but if it works it is an alternative transport to named pipes: HTTP instead of
Windows-only pipes.

More interesting: an LLM NPC-dialogue mod (see below) says it extracts
"real-time universe telemetry" from X4 rather than reading saves, and credits
mods by SirNukes and **Kuertee** for "telemetry culling". So getting live state
out of the game is a solved problem somewhere, and this project's current
save-based state is not the only option. Worth finding before building our own.

The index thread also mentions `scriptproperties.html` sitting in the unpacked
game folder: the human-readable version of the XML this project has been parsing
in `gamedata.py`. Useful for humans, the XML remains better for code.

## Someone else is running an LLM against X4, on a different problem

Steam: [AI LLM driven NPC interaction](https://steamcommunity.com/app/392160/discussions/0/809098674828297013/)

An alpha-stage mod giving NPCs, crew and diplomats live LLM dialogue with voice
output. Same topology as this project: the model runs on a **separate machine on
the home network** (LM Studio in their case), keeping inference off the gaming
PC. They work with roughly 4096 tokens of context and note that token count
drives latency.

So the plumbing is not unique. What is different is the target: they make NPCs
*talk*, this project makes decisions and issues *orders*. As far as this reading
goes, nobody is publishing an LLM that plays the strategic game.

## The objections are worth keeping

Steam: [Why not try some kind of LLM AI for strategic actions in X4?](https://steamcommunity.com/app/392160/discussions/0/690869123373219452/)

Someone proposed LLM-driven faction AI. The thread is mostly pushback, and the
pushback is good:

* "LLM AI for every ship would murder even the strongest supercomputer."
* "It predicts text... you're trying to shove a flagpole into a pinhole."
* Traditional expert systems or rule-based AI are more efficient and more
  controllable for this.

All three are correct as stated, and all three are arguments against a design
this project deliberately does not use. One planner runs for the whole empire on
a cadence of minutes, not one model per ship. The model chooses between options
and never computes; margins, shortages and validation are plain Python. The
executor is a rule-based system, and the model only picks from what it can do.

The objections are, in other words, a decent summary of how to get this wrong.
Worth rereading whenever the temptation arises to give the model more.

## X4 9.0 changes for modders

Thread: [9.0 Beta modding information](https://forum.egosoft.com/viewtopic.php?t=474578)

Nothing here breaks this project, which ships no assets.

* **Breaking, but not for us:** every model with collisions must be re-exported
  with the new XUConverter; V9 models are incompatible with V8 games. Relevant
  only to mods shipping meshes.
* `move_to` gained `avoidtargetturretrange`, for avoiding station turret range.
* New station types `recyclingfacility` and `factionheadquarters`; many
  find/count commands gained filters; a new `spacelistnozone` type.
* New actions around resource areas, recyclable yields, recycling station build
  tasks, and dynamic influence.

## X4 9.0 changes for play, and what players say about funding

The game these runs use is 9.00 (build 611726, released 2026-06-10, the
"Empire Update"). From its [changelog](https://forum.egosoft.com/viewtopic.php?p=5318116#p5318116),
the lines that touch what the agent does:

* **Mining was reworked.** "Resource distribution overhaul for improved
  prospecting and mining", "Added Prospect behaviour", "Removed effect of
  resource probes on mining efficiency", "Improved mining ship behaviour to
  not go to resource areas that will be empty before they arrive". Resources
  are now local and areas run out, so a mining shortage can be depletion as
  much as too few ships, and probes guide miners rather than speed them up.
* "Fixed miners attempting to mine when cargo hold is full and no buyers can
  be found for current cargo": the state HAQ-304 sat in for five game hours,
  holding ice nobody would buy because GKL-870's account was empty.
* "Fixed station construction stalling in certain situations due to missing
  resource buy offers" and "Fixed construction material buy offers not
  updating when planned station build changes".

How the new resource system works, from staff replies in the 9.00 beta
[economy thread](https://forum.egosoft.com/viewtopic.php?t=474213) (page 3 for
the resource system): resource areas "deplete more quickly and not replenish
until some time later", with larger, richer areas taking longer to come back;
no rates are given. A resource probe is "a simple, optional 'mine here!'
marker": a miner with a matching probe goes there, one without searches by
itself and takes "a little bit longer". Staff do not want sectors covered in
probes, and a penalty for many probes found in the beta was called an
oversight (the release removed probes' effect on efficiency). Players in the
beta saw silicon yields fall sharply in some sectors and belts that could no
longer keep their fabs running. For the agent: a refinery's supply is now a
question of fresh areas within reach, and one probe on a good area near a
station is a cheap way to point its miners there.

[Auto transfer funds to stations?](https://forum.egosoft.com/viewtopic.php?t=477355)
confirms what the runs found: the game never tops up a station account by
itself, and there is no setting for it. Players press "Accept all estimates"
by hand every so often. Transfers between a player's own stations and ships
move no money, so a station that supplies the others drains, while money
above the maximum is swept back to the player. `standing.accounts` is that
button, pressed when an account falls below half its minimum.

[Interview with X4's economists](https://forum.egosoft.com/viewtopic.php?t=477519):
the economy is meant to be out of balance ("controlled chaos"), with regional
shortages and gluts on purpose, and destruction is its main source of demand.
For a player that means local market data counts for more than general advice,
and that ship parts are where demand comes from.

## From a scan of the X4 boards (2026-10-24)

A cheap model listed 36 topics from the first five pages of each English X4
board; these are the ones that held something for the agent.

* **Build storages price down as they fill**, on purpose, so that sites about
  to run dry are served first ([t=476768](https://forum.egosoft.com/viewtopic.php?t=476768)).
  The last tenth of a build then often sits undelivered, traders reporting no
  orders. Players fix the price at its maximum, or start construction before
  everything has arrived. A candidate rule for builds that hang near the end.
* **Resources deplete locally and regenerate slowly** (staff, [t=477391](https://forum.egosoft.com/viewtopic.php?t=477391));
  a mined-out hotspot "does not automatically regenerate or respawn in place"
  (moderator, [t=477479](https://forum.egosoft.com/viewtopic.php?t=477479)).
  One player with hundreds of station-assigned miners saw no station short.
* **A station's manager can stall its miners**: every subordinate miner
  reporting "No resources in range" while other stations' miners worked the
  same fields, cured by unassigning and reassigning the manager
  ([t=477112](https://forum.egosoft.com/viewtopic.php?t=477112)). Not seen in
  our runs; a recovery rule if it ever is. 9.00 also has a known bug with the
  same message for L and M miners on local automine ([t=476838](https://forum.egosoft.com/viewtopic.php?t=476838)).
* **Station trade rules cover buying and selling at once**; splitting them
  takes a per-ware override, e.g. buy internal, sell unrestricted
  ([t=477348](https://forum.egosoft.com/viewtopic.php?t=477348)).
* **Construction plans come only from files**: a mod adds one with a `<diff>`
  on `libraries/constructionplans.xml`, not at runtime
  ([t=477056](https://forum.egosoft.com/viewtopic.php?t=477056)); the game's
  own plans can be used by id.
* **LLM-driven testing with X4Mcp and X4Native**, by their author
  ([t=476309](https://forum.egosoft.com/viewtopic.php?t=476309)): Claude Code
  sends chat commands that call the menus' own Lua handlers, so "there is no
  difference between the test doing it and a player doing it", and reads state
  back as JSON from the debug log. The same principle as lesson L26.
* **Script errors can be logged** with the launch options
  `-debug all -logfile x4debug.log -scriptlogfiles x4scripts.log`
  ([t=473817](https://forum.egosoft.com/viewtopic.php?t=473817)), which would
  show MD mistakes in the bridge during a run.

## Ideas this suggests for the project

1. **Respect player orders.** Check `$order.$internalorder` before overriding.
   The caveat that not all orders carry it means the check must fail safe:
   unknown provenance should count as the player's, not ours.
2. **Find Kuertee's telemetry work** before building live state ourselves. The
   current save-request loop works but costs an autosave every cycle.
3. **Write our own AI script order.** The existing vocabulary is limited to
   vanilla orders. Mods like "Advanced Fleet AI Order" add custom order scripts,
   which would let the agent express things vanilla orders cannot, and would
   sidestep the parameter problem: a custom order can read its parameters from
   somewhere the pipe can reach.
4. **X4 RestServer as an alternative transport**, if named pipes ever become the
   limiting factor, or for a non-Windows setup.
