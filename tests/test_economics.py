"""What a production module costs and earns (economics.py)."""

import copy

import pytest

import economics
import gamedata


def test_a_production_module_is_named_after_its_ware():
    assert economics.product_of("prod_gen_hullparts_macro") == "hullparts"
    assert economics.product_of("prod_tel_sunriseflowers_macro") == "sunriseflowers"
    assert economics.product_of("prod_gen_scrap_recycler_macro") is None
    assert economics.product_of("storage_tel_m_solid_01_macro") is None


def test_payback_counts_the_blueprint_until_it_is_owned(small_state):
    state = copy.deepcopy(small_state)
    rows = {r["macro"]: r for r in economics.economics(state)}
    row = rows["prod_gen_hullparts_macro"]
    assert row["blueprint"] == gamedata.modules()["prod_gen_hullparts_macro"]["maxprice"]
    if row["margin_per_hour"] > 0:
        assert row["payback_hours"] == pytest.approx((row["build_cost"] + row["blueprint"]) / row["margin_per_hour"])
        assert row["payback_hours_built"] == pytest.approx(row["build_cost"] / row["margin_per_hour"])
    state["player"]["blueprints"] = list(state["player"].get("blueprints") or []) + ["module_gen_prod_hullparts_01"]
    owned = {r["macro"]: r for r in economics.economics(state)}["prod_gen_hullparts_macro"]
    assert owned["blueprint"] == 0


def test_the_build_cost_is_the_modules_own_recipe():
    table = gamedata.wares()
    recipe = table["module_gen_prod_hullparts_01"]["recipes"]["default"]["inputs"]
    expected = sum(n * table[w]["avgprice"] for w, n in recipe.items())
    assert economics.build_cost("module_gen_prod_hullparts_01", table) == int(expected)


def test_the_games_own_plans_for_a_ware_are_found():
    if not gamedata.X4_DIR.exists():
        pytest.skip("needs the game installed")
    plans = economics.game_plans("hullparts")
    assert plans and all(any(economics.product_of(m) == "hullparts" for m in mods) for mods in plans.values())
