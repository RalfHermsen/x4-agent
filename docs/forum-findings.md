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
