# x4-agent

An agent that plays X4: Foundations according to your own written guidelines,
driven by a **local** LLM. The model plans, deterministic Python does the maths
and the execution.

Status: **Phase 1 works end to end, and the Phase 2 round trip is proven.**
Save parsing, sitrep generation and advice from a local model, plus a working
game to Python and back again loop over named pipes on X4 9.00.

## Standing on someone else's shoulders

The hard part of talking to a running X4 was already solved by
**[bvbohnen/x4-projects](https://github.com/bvbohnen/x4-projects)** (SirNukes'
Mod Support APIs, MIT licensed). That project provides the Named Pipes API, the
Lua and C bridge, and the Python host that let an external process exchange
messages with the game. This repo builds directly on it and reimplements none
of it.

What this project adds on top is the agent: reading game state, condensing it
into a sitrep, asking a local model for decisions under a set of guidelines, and
validating those decisions before anything is allowed near the game.

The pipe host is vendored under [vendor/](vendor/) with its origin and licence
documented. Credit for the IPC layer belongs to that project, not to this one.

## Architecture

```
X4 (Windows)  <--named pipes-->  Python host (Windows)  <--LAN/HTTP-->  Ollama (GPU box)
   MD + Lua                       sitrep + executor                      planner (policy)
```

Three layers:

1. **In-game bridge** (Mission Director XML + Lua) reads state and executes
   orders, through the Named Pipes API from `sn_mod_support_apis`.
2. **Python host** on the game machine: builds a compact sitrep, calls the
   model, validates the JSON it returns and translates it into concrete orders.
3. **Planner** (Ollama, typically on a separate machine with a GPU): strategic
   policy layer, not an optimiser.

The core principle: the LLM decides *where attention goes*, Python works out
*what that means in numbers*. No "find the best trade route among 400 stations"
in the model. It is bad and expensive at that, and Python is neither.

## Phases

| Phase | Contents | Needs MD? |
|-------|----------|-----------|
| 1 | Read-only advisor: parse save, build sitrep, get advice from Ollama | no |
| 2 | One write command through the pipe, proving the closed loop | yes |
| 3 | More order types, higher decision frequency, guardrails | yes |

Phase 1 deliberately postpones the Mission Director, because that was expected
to be the bottleneck. It turned out smaller than feared: see
[docs/phase2-ipc.md](docs/phase2-ipc.md).

## Usage

```bash
python planner.py --latest             # full advice loop on the newest save
python sitrep.py --latest              # just the report
python save_parser.py --latest --json state.json
python explore_save.py census <save>   # explore the save format
python evaluate.py                     # run the loop across every save you own
python deploy_bridge.py                # install the in-game bridge
```

`--latest` locates the newest save itself, including the case where Windows has
redirected your Documents folder somewhere unexpected.

For the pipe host (PowerShell):

```powershell
$env:PYTHONPATH = "vendor"
.venv\Scripts\python.exe -u -m X4_Python_Pipe_Server.Main -v
```

The `-u` matters. Without unbuffered output you see nothing at all when
something goes wrong.

Point the planner at your own Ollama instance with `X4_OLLAMA_URL`, and pick a
model with `X4_PLANNER_MODEL`.

## Layout

```
save_parser.py        streaming extraction of player state from a .xml.gz save
sitrep.py             condenses that state into a compact report, computes margins
planner.py            sitrep + guidelines to Ollama, JSON enforced with pydantic
schemas.py            the two contracts: Sitrep in, PlannerResponse out
gamedata.py           reads the .cat archives, turns macros into real names
explore_save.py       save format explorer (census, dump, find)
evaluate.py           runs the full loop across many saves, Phase 1 definition of done
deploy_bridge.py      copies the in-game bridge into the X4 installation
bridge/               the X4 extension: MD script + Python pipe module
guidelines.md         the strategy rules the model follows (this is yours to edit)
docs/                 what was measured, and what broke while measuring it
vendor/               third-party code, pinned
```

## Requirements

* X4: Foundations with modding enabled. Developed against **9.00, build 611726**.
* Windows for the game machine. Named pipes are Windows only, and
  **Protected UI Mode must be off** or the pipe API is disabled.
* Python 3.10+ (developed on 3.14). See `requirements.txt`, plus `pywin32` for
  the pipe host.
* [Ollama](https://ollama.com) reachable over the network, running a quantised
  14-32B class model. Choose on reliable structured output, not on size.
* `sn_mod_support_apis` installed. Note that the Community Edition on the Steam
  Workshop is **pre-8.0 only**; the maintained route is SirNukes' original.

## Model choice

Measured on a real sitrep, over LAN:

| Model | Time | Note |
|-------|------|------|
| `gemma4:26b-a4b-it-qat` | 5.9 s warm, 171 s cold | default, compact and usable output |
| `qwen3:32b` | 257 s cold | comparable content, but duplicated entries |

Cold time is loading weights into VRAM, not inference. With the model resident,
one advice round costs roughly 15 s plus save parsing. `qwen3:32b` has not been
measured warm.

## Things that will bite you

All measured, not guessed. Details in [docs/](docs/).

* **Prices in the save are in hundredths of a credit.** `energycells price="1900"`
  is 19 Cr. `player.money` from the Mission Director uses the same scale, while
  `info/player money` in the save file uses whole credits. Two sources, two
  scales.
* **Docked ships are nested inside their host object**, not sitting loose in the
  sector. A parser that only walks the sector level finds no ships at all.
* **A schema-valid answer can still be nonsense.** Constrained decoding
  guarantees the shape and nothing else. Three separate failure modes, all
  producing valid JSON, are documented in [docs/contracts.md](docs/contracts.md).
* **The sitrep explodes as your empire grows.** 220 ships listed individually is
  40 kB of prompt. Aggregate by role.
* **A full save will not fit in memory as a tree.** Streaming parse is mandatory,
  not an optimisation.
* **The pipe host refuses unknown extensions** unless their `content.xml` id is
  listed in `permissions.json`. It fails silently.
* **Mods can break on game updates.** Pin a patch version while developing.

## Support

**None.** This is a personal project published in case it is useful to someone
else. It is provided as is: no support, no warranty, no promise that it keeps
working after the next X4 patch. Issues and pull requests may go unanswered.

Fork it, take the parts you want, and run with it.

## Licence

MIT, see [LICENSE](LICENSE).

The vendored pipe server under [vendor/](vendor/) is MIT licensed and belongs to
[bvbohnen/x4-projects](https://github.com/bvbohnen/x4-projects). That project
deserves the credit for the IPC layer that makes any of this possible.
