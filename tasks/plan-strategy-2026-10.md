# Plan: a strategist above the rules (2026-10-24)

The rules nearly double what the game earns alone, and the model adds little
on top: in catalog mode it picks from about one situation a cycle, and its
best thinking lands in notes nothing carries out. The idea here is a slow,
strong model (Opus 5.5 or Fable 5.1, through the API) that sets goals for the
next two to four hours, in a form the rules act on. The model decides what;
Python works out how, as everywhere else in this project.

## Steps

| # | Step | Status |
|---|------|--------|
| 1 | What players and Egosoft say about mid and late game | done: thin on numbers; `docs/forum-findings.md` has what holds for 9.00 |
| 2 | `economics.py`: per production module, build cost, blueprint, margin per game hour at known prices, payback, known demand and stock in hours of output | done (offline) |
| 3 | A plan the rules follow: build order per station, fleet targets per station, sectors to avoid or explore, where money goes. `grow` takes the next module from the plan instead of the margin ranking; purchases keep fleets at their targets; the gates stay | open, after the running series |
| 4 | The strategist call: every few game hours, a richer report (timeline, `economics.py`, the game's own plans for a ware), the plan back as JSON through the API | open |
| 5 | Measure: strategist and rules against rules alone, same baseline, same code | open |

## What the numbers say already

From the 88-hour save of the Claude run (`economics.py`, prices the player
knows, build costs at the game's average prices):

* The chains we have pay back in about one game hour per module (silicon
  wafers 0.6, refined metals and water 1.0, energy cells 3.5), but we already
  hold 10 to 22 hours of their output, so the limit is selling, not making.
* The scarce end products the guides name pay back slowly at these prices,
  mostly because of the blueprint: hull parts 50 to 110 game hours, advanced
  electronics 55, weapon components 43, shield components 52. Without the
  blueprint, which is paid once for every later module, a module pays back
  in 12 to 15 hours. Known demand is large: advanced electronics 302 hours of
  one module's output, weapon components 193.
* Claytronics, microchips and smart chips lose money at these prices: their
  inputs earn more sold as they are.
* Build costs are at average prices; in the runs the build storages spent
  about 0.76 million per expansion, so these may be two to three times low.
  To be calibrated against what build storages actually spend.

## Notes for step 4

* The game's own single-ware station plans (`arg_hullparts_prefab_06`: six
  production modules, four storage, five habitats, two docks, three piers)
  say how much storage, habitation and docking goes with a number of
  production modules. `economics.game_plans(ware)`.
* Since 9.00, mining areas run out and come back only later; a shortage of a
  mined ware can be depletion, not too few ships (`docs/forum-findings.md`).
* `x4-script-check` (npm, from X4CodeSense) validates MD against the game's
  schema and script properties; worth running before a bridge deploy.
