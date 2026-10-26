"""3.1 a station does not buy what it makes; 3.2 full storage is a fact."""

import copy

import executor
import gamedata


def _station(state, code="KYV-745"):
    return next(a for a in state["assets"] if a["code"] == code)


def test_switch_off_buying_a_ware_we_make_and_nothing_eats(small_state):
    state = copy.deepcopy(small_state)
    st = _station(state)
    st["production_queue"] = ["sunriseflowers", "microchips"]
    st["offers"] = [{"ware": "microchips", "side": "buy", "price": 900, "amount": 0, "desired": 50},
                    {"ware": "energycells", "side": "buy", "price": 16, "amount": 0, "desired": 900}]
    assert executor.own_production_buys(state) == ["tradeware KYV-745 microchips buy off"]


def test_an_input_we_also_make_stays_on(small_state):
    # Sunriseflowers eat energycells and water; making energycells too does not
    # mean the station may stop buying them.
    state = copy.deepcopy(small_state)
    st = _station(state)
    st["production_queue"] = ["sunriseflowers", "energycells"]
    st["offers"] = [{"ware": "energycells", "side": "buy", "price": 16, "amount": 0, "desired": 900}]
    assert executor.own_production_buys(state) == []


def test_workforce_food_stays_on(small_state):
    state = copy.deepcopy(small_state)
    st = _station(state)
    st["production_queue"] = ["medicalsupplies"]
    st["offers"] = [{"ware": "medicalsupplies", "side": "buy", "price": 60, "amount": 0, "desired": 90}]
    assert executor.own_production_buys(state) == []


def test_sent_once_through_the_cycle(run_cycle, small_state, monkeypatch):
    import agent
    monkeypatch.setattr(agent, "MAX_QUIET", 0.0)
    st = _station(small_state)
    st["production_queue"] = ["sunriseflowers", "microchips"]
    st["offers"] = [{"ware": "microchips", "side": "buy", "price": 900, "amount": 0, "desired": 50}]
    first = run_cycle(small_state)
    second = run_cycle(small_state)
    assert "tradeware KYV-745 microchips buy off" in first["commands"]
    assert "tradeware KYV-745 microchips buy off" in second["repeats"]


def test_fill_matches_a_direct_computation(large_state):
    table = gamedata.wares()
    for st in (a for a in large_state["assets"] if a["cls"] == "station"):
        container = sum(n * table[w]["volume"] for w, n in st["cargo"].items()
                        if table.get(w, {}).get("transport") == "container")
        expected = round(container / st["capacity"]["container"], 3)
        assert executor.storage_fill(st)["container"] == expected


def test_full_everywhere_is_a_transport_shortage(small_state):
    state = copy.deepcopy(small_state)
    st = _station(state)
    st["capacity"] = {"container": 1000}
    st["cargo"] = {"sunriseflowers": 180}          # 5 m3 each, so 900 of 1000
    st["offers"] = [{"ware": "sunriseflowers", "side": "sell", "price": 100, "amount": 180, "desired": 0}]
    (line,) = executor.transport_shortage(state)
    assert line.startswith("transport shortage at KYV-745:") and "90% full" in line


def test_partly_full_is_not_a_shortage(large_state):
    assert executor.transport_shortage(large_state) == []


def test_a_ware_is_never_priced_below_what_its_inputs_cost(small_state):
    station = copy.deepcopy(_station(small_state))
    station["modules"] = ["prod_gen_siliconwafers_macro"]
    station["offers"] = [{"ware": "silicon", "side": "buy", "price": 149.0, "amount": 240},
                         {"ware": "energycells", "side": "buy", "price": 16.0, "amount": 90}]
    recipe = gamedata.wares()["siliconwafers"]["recipes"]["default"]
    cost = (recipe["inputs"]["silicon"] * 149.0 + recipe["inputs"]["energycells"] * 16.0) / recipe["amount"]
    assert executor.sell_floor(station, "siliconwafers") == int(cost + 0.999)
    station["offers"] = []                                  # nothing bought: the game's minimum is the floor
    assert executor.sell_floor(station, "siliconwafers") >= gamedata.wares()["siliconwafers"]["minprice"]


def test_a_mined_input_is_not_bought_for_more_than_it_earns(small_state):
    state = copy.deepcopy(small_state)
    station = _station(state)
    station["modules"] = ["prod_gen_siliconwafers_macro"]
    station["offers"] = [{"ware": "silicon", "side": "buy", "price": 150.0, "amount": 240},
                         {"ware": "siliconwafers", "side": "sell", "price": 176.0, "amount": 100}]
    # Wafers at 176 cannot pay for silicon above its minimum: the cap is the minimum.
    assert f"price KYV-745 silicon buy {gamedata.wares()['silicon']['minprice']}" in executor.input_caps(state)
    station["offers"][1]["price"] = 419.0                   # at the maximum they can
    recipe = gamedata.wares()["siliconwafers"]["recipes"]["default"]
    worth = (419.0 * recipe["amount"] - recipe["inputs"]["energycells"] * gamedata.wares()["energycells"]["minprice"]) \
        / recipe["inputs"]["silicon"]
    assert f"price KYV-745 silicon buy {int(worth * executor.INPUT_MARGIN)}" in executor.input_caps(state)
