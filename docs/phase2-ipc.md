# Phase 2: does the IPC bridge still work, and does it work on 9.00?

Researched 2026-08-19. The brief names `sn_mod_support_apis` as a required
building block for the closed loop. The question was whether it is usable on the
version installed here: X4 9.00, build 611726, patched June 2026.

## What the sources said

| Source | Last updated | Statement about versions |
|--------|--------------|--------------------------|
| [Steam Workshop, Community Edition (3514258146)](https://steamcommunity.com/sharedfiles/filedetails/?id=3514258146) | 11 July 2025 | Explicitly **pre-8.0 only**. A comment from 16 Sep 2025: "only compatible with PRE-8.0 versions of X4: Foundations. Please use the updated version of the original mod." |
| [Steam Workshop, SirNukes original (2042901274)](https://steamcommunity.com/workshop/filedetails/?id=2042901274) | 8 December 2025 | No explicit version statement in the description. User comments report "works with 9.0" and an 80-hour 9.0 save, but also isolated errors in the Extensions menu. |
| [GitHub bvbohnen/x4-projects](https://github.com/bvbohnen/x4-projects) | commit 8 December 2025 | The last version-related commit is "Updates for x4 7.0, 7.5, 8.0 changes" (Sep 2025). **9.0 is mentioned nowhere.** |
| [Nexus mod 503](https://www.nexusmods.com/x4foundations/mods/503) | not retrievable | Nexus returns HTTP 403 to automated requests. Check by hand. |

## Conclusion from research alone

The maintained route is **SirNukes' original**, not the Community Edition. The
CE is a dead end for this purpose: it is explicitly for pre-8.0.

But the original had not been touched since **8 December 2025**, while X4 9.00
here dates from **18 June 2026**. That is half a year and a major version step
between the last mod update and the game being run. "9.0 works" was a claim from
forum comments, not from documentation or a release.

That was not a blocker, but it was not a confirmation either. The brief names
patch breakage as an explicit risk, and this was exactly that risk. Only an
empirical test could settle it.

## Installation

Installed from **GitHub master** rather than the Workshop, because the GitHub
releases still date from 2020 (v1.95) while master carries the December 2025
commit. The compiled `winpipe_64.dll` is simply present in master, so nothing
needed building.

| Item | Value |
|------|-------|
| Installed to | `<X4>/extensions/sn_mod_support_apis/` |
| Source | `bvbohnen/x4-projects` master, fetched 2026-08-19 |
| `content.xml` | id `ws_2042901274`, version 195, author SirNukes |
| File names in `md/` | all lowercase, checked |
| Python host | `vendor/X4_Python_Pipe_Server/`, committed to pin the version |
| Host dependency | `pywin32`, works on Python 3.14 |

The extensions folder turned out to be writable without administrator rights.
The install is a single self-contained folder: removing it is deleting that
folder.

**Note:** the `content.xml` carries the Workshop id `ws_2042901274`. If you also
subscribe to the Workshop item later you will have the same mod twice. Pick one.

## The spike: x4_agent_bridge

Built from the locally installed `sn_mod_support_apis`, not from the GitHub
page. The smallest complete example in that mod is `md/time_api.xml` (1,941
bytes) together with `python/Time_API.py`: MD registers a Python module, Python
reads blocking and writes back. That pattern was adopted directly.

**Everything the MD side uses was verified against the game itself**, not
written from memory:

| Used | Verified in |
|------|-------------|
| `write_to_logbook`, `debug_text`, `set_value`, `raise_lua_event` | `libraries/common.xsd` |
| `signal_cue_instantly` | `libraries/md.xsd` |
| `player.money`, `player.age` | `libraries/scriptproperties.xml` |
| valid logbook categories | `logcategorylookup` in `common.xsd`: general, missions, news, upkeep, diplomacy, alerts, tips, guidance |
| `Server_Reader`, `Register_Module`, `Named_Pipes.Write` | `documentation/Named_Pipes_API.md` in the mod |

### What the spike does

Outbound: every 30 seconds X4 writes `state money=... time=...` to the pipe
named `x4_agent`.

Return: the Python host answers, and that answer appears **in the in-game
logbook**. The whole loop is observable without changing anything in the game.

The planner is deliberately not wired in yet. If the loop fails you want to know
whether it is the pipe or the model, not both at once.

### Files

```
bridge/x4_agent_bridge/content.xml
bridge/x4_agent_bridge/md/x4_agent_bridge.xml     (lowercase, checked)
bridge/x4_agent_bridge/python/bridge.py
deploy_bridge.py                                   copies it into the X4 folder
```

The repo is the source; `deploy_bridge.py` copies to the game folder and refuses
if there is an uppercase character in `md/`. `--remove` takes it back out.

### Test order

1. `python deploy_bridge.py`
2. **Turn Protected UI Mode off** in the game settings. Without that the pipe
   API is disabled and you are measuring the wrong failure.
3. Start X4 and check the Extensions menu: are `Mod Support APIs` and
   `X4 Agent Bridge` both listed, without errors?
4. Run the host:
   `$env:PYTHONPATH="vendor"; .venv\Scripts\python.exe -u -m X4_Python_Pipe_Server.Main -v`
5. Load a save, close the menus and let the game run for 30 seconds.

## Result: the loop closes on 9.00

Verified 2026-08-19. In the Extensions menu, `Mod Support APIs` (1.95) and
`X4 Agent Bridge` both showed On without load errors, with Protected UI Mode
off. The host log:

```
Imported .../extensions/x4_agent_bridge/python/bridge.py
[x4-agent] bridge starting, pipe x4_agent
Started serving: \\.\pipe\x4_agent
Connected to client
[x4-agent] X4 connected
[x4-agent] received: state money=20000000 time=200.13
```

And in the in-game logbook:

```
[x4-agent] bridge ok: received capital 20000000, planner not connected yet
```

**So the mod works on X4 9.00**, despite not having been updated since December
2025. That was the largest open uncertainty in the project.

## Three traps this cost

**1. `permissions.json` rejects unknown extensions.** The pipe host only loads
Python modules from extensions whose `content.xml` id is listed in
`X4_Python_Pipe_Server/permissions.json`. By default only `ws_2042901274` is
there, and our module was refused silently. Add:

```json
{ "ws_2042901274": true, "x4_agent_bridge": true }
```

**2. `player.money` is in hundredths of a credit.** The game showed 200,000 Cr,
the pipe delivered `money=20000000`. Same factor of 100 as the trade prices in
the savegame. The savegame's own `info/player money` is in whole credits, so the
two sources disagree: convert at the edge, never halfway.

**3. The documentation example is circular.** The docs show `$Start_Reading`
being signalled only from `Actions_On_Connect`. But `Actions_On_Connect` runs
only after a successful ping, and that ping only happens because of
`$Start_Reading`. The result is silence with no error: X4 writes to the pipe
happily, because the write path works independently of the read loop, but never
reads anything back.

The working mods do it differently. `hotkey_api.xml` line 253 signals
`$Start_Reading` from **`Actions_On_Reload`**. That is where it belongs.

The diagnostic that unravelled this: have the Python side log every incoming
message *before* filtering out pings. If you see `state` but never `ping`, the
read side is dead while the write side lives. Without that ordering in the log
it would have taken far longer.

**Also worth knowing:** cues with a `checkinterval` do not fire while the game is
paused, so standing in a menu makes the loop look dead when it is only waiting.
And MD scripts are only loaded at game start: after editing anything in `md/`
you must restart X4 completely, reloading a save is not enough.

## Not yet proven

A logbook line is not an order. The next step is one real order type through the
pipe, using `create_order` from `common.xsd`, which completes the closed loop as
the brief defines it.
