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
| 3 | A plan the rules follow (`schemas.Strategy`, `strategy.py`): modules per ware, miners per kind and traders per station, in absolute numbers. `grow` builds what the plan asks first, the margins once its targets stand; `fleet` assigns free ships and buys one a cycle under the purchase brake; `strategy.blueprints` buys a planned module's blueprint; the report gets a STRATEGY section. Plan from `X4_STRATEGY_FILE` until step 4. Seventeen more production wares in the bridge (all without gas inputs) | in `main` since 2026-10-25, offline only; needs a run with a plan |
| 4 | The strategist call (`strategist.py`): when no plan is held or its horizon has passed, a report of each station's modules, stores, stock, account and fleet, `economics.py` for the modules the bridge builds, and whether each missing blueprint can be had (the purchase job's own check of sellers, licences, standing); the plan back as structured output through the API (`X4_STRATEGIST_MODEL`) | built; one call on the 88-hour save: Opus 5.5, 15 s, about $0.07, a plan that fixes GKL-870 first and adds teladianium and wafers at KYV-745 |
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

## Open after step 3

* The purchase job picks the ship for a blueprint errand itself, and on the
  88-hour save it picked MCX-254, a fighter defending KYV-745. Same as for the
  connector before; an errand ship should not be a station defender.
* Not in the game yet: the new expansion wares and `fleet` need a run.

## Notes for step 4

* The game's own single-ware station plans (`arg_hullparts_prefab_06`: six
  production modules, four storage, five habitats, two docks, three piers)
  say how much storage, habitation and docking goes with a number of
  production modules. `economics.game_plans(ware)`.
* Since 9.00, mining areas run out and come back only later; a shortage of a
  mined ware can be depletion, not too few ships (`docs/forum-findings.md`).
* `x4-script-check` (npm, from X4CodeSense) validates MD against the game's
  schema and script properties; worth running before a bridge deploy.
