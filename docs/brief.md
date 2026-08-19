# Design brief: X4 Foundations, local-LLM agent

The original design document for this project, written 2026-08-19 and extended
the same day with section 8. Kept as the reference for scope: when something in
the code and something here disagree, this document says what was intended and
the code says what turned out to be true.

Goal: build a system that plays X4: Foundations largely autonomously according
to guidelines written by the user, driven by a **local** LLM (Ollama). The LLM
acts as the strategic policy layer; deterministic Python does the numerical
optimisation and the order execution.

This is partly uncharted territory: as far as is known there is no published,
fully autonomous LLM-driven X4 player. The building blocks (an IPC bridge, save
parsers, a modding framework) do exist and are maintained.

---

## 1. Architecture

Three loosely coupled layers:

1. **In-game bridge**: Mission Director (XML) plus Lua scripts that read game
   state and execute orders. It talks to the outside world through the **Named
   Pipes API** from `sn_mod_support_apis`.
2. **External Python host**: a named pipe client on the Windows game machine. It
   builds a compressed situation report (sitrep), calls the local model, and
   translates the structured output (JSON) back into concrete orders.
3. **Local model (planner)**: Ollama. It receives no raw game dump but a sitrep,
   and returns structured decisions consistent with the guidelines.

### Core principle

Do **not** use the LLM as an optimiser ("compute the best trade route out of 400
stations"). LLMs are bad and expensive at that. The LLM is the *strategic policy
layer* (goals, priorities, "what do I focus on given my rules"); deterministic
Python is the *executor* that crunches the numbers and issues the orders. The
classic LLM agent pattern: the model plans, tools execute.

### Network topology

- **Game and Python host run on Windows** (named pipes are Windows only, see
  section 5).
- **Ollama runs on a separate machine with a GPU.**
- The Python host talks to Ollama over the LAN (`http://<host>:11434`).

This keeps the heavy inference off the game machine.

---

## 2. Phased requirements

Build in this order; each phase de-risks the next.

### Phase 1: read-only advisor (no order execution)

Avoid Mission Director complexity entirely; only read state and generate advice.

- Parse the savegame offline (XML, `.xml.gz`) OR have the mod dump a state
  snapshot periodically.
- Python builds the sitrep (capital, core stations, threats, opportunities,
  current fleet assignments).
- Ollama returns recommendations (structured JSON).
- Output to console or a chat channel.
- **Goal:** validate the state representation and the LLM layer without writing
  a single line of order execution.

### Phase 2: one write command (prove the closed loop)

- One order type through the pipe, for example "assign ship X to auto-trade in
  sectors Y".
- An MD cue receives the command and executes it.
- **Goal:** prove that the full loop (state, LLM, order, game) works.

### Phase 3: expand the vocabulary

- More order types (mining assignment, station trade rules, fleet
  reorganisation, build orders).
- More autonomy, higher decision frequency.
- Guardrails: budget limits, whitelists of permitted actions, dry-run mode.

---

## 3. Technical requirements

### Runtime and software

- **X4: Foundations**, current patch. Modding ("extensions") enabled in the game
  settings.
- **Windows** for the game machine (named pipes requirement).
- **Python 3.10+** on the game machine (named pipe host).
  - libraries: `lxml` (save parsing), `httpx` (Ollama call), `pydantic`
    (JSON schema validation of LLM output), optionally `duckdb` for state
    history.
- **Ollama** on the GPU machine.
  - Model class: 4-bit quantised, roughly 14-32B, fits in 24 GB VRAM. Latency is
    not critical (a cadence of seconds to minutes). Choose on reliable tool
    calling and structured JSON output, not on raw size.
- **RAM (important):** offline save parsing is memory hungry. A save of about
  1 GB uncompressed can cost 16 GB of RAM. Budget for that on whichever machine
  does the parsing.

### Mod installation

- Extensions live in `.../X4 Foundations/extensions/<mod>/`.
- **File names must be lowercase** in the `md/` folder, or X4 ignores them
  silently (a classic trap).
- `sn_mod_support_apis` consists of two parts: the in-game extension and an
  optional external program that runs the named pipe host.

---

## 4. External dependencies, repos and sources

### 4a. Core: the IPC bridge (required for the closed loop)

- **bvbohnen/x4-projects**: the primary source of `sn_mod_support_apis`,
  including the Named Pipes API and working Python host examples. Start here for
  the IPC skeleton.
  https://github.com/bvbohnen/x4-projects
  Specifically: `extensions/sn_mod_support_apis` plus the `documentation/` folder.
- **Nexus, Mod Support APIs (original, SirNukes)**
  https://www.nexusmods.com/x4foundations/mods/503
- **Nexus, Mod Support APIs Community Edition**
  https://www.nexusmods.com/x4foundations/mods/1699
  Note: the CE GitHub is archived and the CE itself is pre-8.0 only. The
  maintained route is SirNukes' version. Verify which build matches your patch
  before installing.

### 4b. Save parsing and data extraction (Phase 1)

- **TuxInvader/X4-Info-Miner**: Python, only needs `lxml`. Extracts information
  from save files and has an interactive mode that loads the save into an
  `lxml.etree`. The best starting point for Python save parsing.
  https://github.com/TuxInvader/X4-Info-Miner
- **Mistralys/x4-savegame-parser**: PHP. Watches the save folder, auto-backups,
  extracts to JSON. A good reference model for which fields are useful.
  https://github.com/Mistralys/x4-savegame-parser
- **BeamerMiasma/X4-Foundations**: Python and R, save analysis and
  visualisation. Warns explicitly about memory usage (16 GB+ for large saves).
  https://github.com/BeamerMiasma/X4-Foundations
- **xixasdev gist, savegame XML analyzer**: works out the deserialisation
  structure of a save; useful for learning the XML tag and attribute layout.
  https://gist.github.com/xixasdev/f0632aab83972985adcc7d2e11bdd6fe

### 4c. Static game data (recipes, hulls, macros, for the executor layer)

- **bno1/X4FProjector**: a CLI that reads `.cat`/`.dat` game files and exports
  raw stats of game objects in machine-readable form.
  https://github.com/bno1/X4FProjector
- **Mistralys/x4-core**: PHP OOP access to X4 game data (factions, wares), with
  data as JSON.
  https://github.com/Mistralys/x4-core
- **ratilicus/x4**: a Python toolset to extract game scripts and XML from
  `.cat`/`.dat` and to pack mods. Useful for reading the game's own MD and Lua.
  https://github.com/ratilicus/x4
- **zakky2k/x4shipqueue**: a Python parser that exports ship and equipment
  recipes to Excel (resource planning for build orders).
  https://github.com/zakky2k/x4shipqueue
- More tools: https://github.com/topics/x4foundations

### 4d. Existing automation as reference

- **Mules, Supply and Warehouses Extended** and related auto-trade and auto-mine
  mods show how order behaviours are defined in MD. Useful as an MD reference
  for Phases 2 and 3.

---

## 5. Constraints and traps (read before starting)

- **Named pipes are Windows only** and require *Protected UI Mode to be
  disabled*. In protected mode the pipes API is switched off. This determines
  the network topology (section 1).
- **X4 online features stop working with this mod**: irrelevant for
  singleplayer, but worth knowing.
- **MD is the real bottleneck.** The Mission Director is an idiosyncratic XML
  language with a steep learning curve and thin, partly outdated documentation
  (many tutorials are from 2013 to 2019). The Python and LLM sides are routine;
  the MD cues that read state and execute orders are the time-consuming part.
  Hence Phase 1, which postpones MD entirely.
- **Case sensitivity:** XML files in `md/` must be lowercase.
- **Patch breakage:** mods, including the community APIs, can break on X4
  updates. Pin a patch version during development.
- **Memory when parsing:** large saves need 16 GB+ RAM (section 3).
- **Modding is unsupported by Egosoft** in the sense that these APIs are
  community maintained; expect to debug them yourself.

---

## 6. Reference documentation

- **Mission Director Guide (Egosoft X Community Wiki)**, the canonical MD reference.
  https://wiki.egosoft.com/X%20Rebirth%20Wiki/Modding%20support/Mission%20Director%20Guide/
- **Egosoft forum, Scripting and Modding (X4)**, active help for MD and Lua.
  https://forum.egosoft.com/ (subforum "Scripts and Modding")
- **Practical modding intro including traps (case sensitivity, pipe server):**
  https://beko.famkos.net/2021/05/01/getting-into-x4-foundations-modding-on-linux/
- **Ollama docs**, structured outputs and API: https://ollama.com

---

## 7. Phase 1 deliverables

A read-only advisor with these components:

1. `save_parser.py`: reads an `.xml.gz` X4 save through `lxml` and extracts
   player capital, own stations (including wares and production), own ships and
   fleets with their current orders, and known trade opportunities.
2. `sitrep.py`: condenses the parsed state into a compact, token-efficient
   summary. Not a raw dump.
3. `planner.py`: sends the sitrep plus the guidelines to Ollama over the LAN,
   enforces a JSON schema through `pydantic`, and returns recommendations.
4. `guidelines.md`: a separate, user-editable file with the strategic rules the
   model follows (system prompt input).
5. Output to the console.

No pipes, no MD, no order execution yet. The point is to validate the state
representation and the quality of the LLM output.

---

## 8. Architecture v2: improvements

This layer on top of the basics is the difference between a reflex bot and a
robust, learning agent. Grouped by impact.

### 8.1 Enforce the contract: constrained decoding (from Phase 1)

Do not rely on parse-and-pray. Ollama binds decoding to a JSON schema through
the `format` parameter and strips fences and preamble automatically; under the
hood it runs XGrammar with full schema compliance. So send
`PlannerResponse.model_json_schema()` and validate with
`PlannerResponse.model_validate_json(...)`.

* **Two-call pattern.** Heavy constraints can lower reasoning quality, because
  the model cannot think out loud first. So split it: call 1 is free reasoning
  about the sitrep, call 2 is constrained extraction into the schema. For a
  strategic planner this is worth the extra call.
* **Semantic validation on top of schema validation.** Valid JSON can still
  contain a hallucinated or stale id. The executor checks every action against
  the current state (does this ship or station still exist?) and skips invalid
  actions rather than executing them.

> Measured outcome: see [contracts.md](contracts.md). Schema compliance held
> perfectly and still produced three distinct classes of wrong answer. The
> semantic validation in this section turned out to be the load-bearing part.

### 8.2 Skill library (the Voyager pattern): the compounding improvement

Build a growing library of reusable, parameterised playbooks as code
(`establish_energy_station(sector)`, `rebalance_starved_station(id)`) that the
model stores, indexes and retrieves, rather than deriving everything again each
cycle.

* **It compensates for a smaller model.** A good skill library lets smaller
  models reach performance comparable to much larger ones. So invest in the
  indexing and retrieval layer rather than in domain-specific training. That
  suits local inference on a single GPU.
* **Safe write-back is mandatory.** In a game a failed skill does not reset the
  way a sandbox does. New or changed skills should be dry-run against a
  development save first, and only made available to the live empire after
  verification.

### 8.3 Curriculum and reflection (extending the goals loop)

Lift the `active_goals` / `updated_goals` pair from `schemas.py` into:

* **An automatic curriculum:** the model proposes next goals scaled to the
  current phase and capital, and decomposes them into subtasks.
* **Reflection:** failed actions and stalled goals go back into the next cycle
  as an outcome log, so the model can reflect on them. This doubles as the
  observability and evaluation layer.

### 8.4 Efficiency and cadence

* **Event-driven instead of a fixed timer:** run the LLM on meaningful state
  deltas (a threat, a starved station, capital crossing a phase threshold), not
  on the clock. In steady state the in-game behaviours and skill macros do the
  work. This saves tokens and improves responsiveness.
* **Cache static context:** production chain graph, sector map and blueprint
  list in a stable prompt segment; send only the dynamic (or delta) sitrep each
  cycle.

### 8.5 Deliberately not doing (for now)

* **No multi-agent decomposition** at the start: a single planner with a skill
  library and curriculum is simpler and captures most of the value. Split only
  when a concrete bottleneck appears.
* **No hardcoded "best model":** the strongest agentic and tool-use models shift
  monthly. Check a current leaderboard when building, and record measurements
  rather than claims.
* **No real-time combat through the LLM:** the strategic loop (seconds to
  minutes) is far too slow. The LLM sets doctrine; in-game Protect and Defend
  behaviours handle combat micro.
