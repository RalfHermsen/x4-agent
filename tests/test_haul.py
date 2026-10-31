"""4.6 one-off hauls and 3.5 the loop around them: checked and sized in Python."""

import copy

import executor
from schemas import PlannerResponse


def _haul(**over):
    action = {"type": "haul", "ware": "microchips", "from_station": "SEL-001",
              "to_station": "KYV-745", "amount": 200, "repeat": False, "rationale": "t"}
    action.update(over)
    return PlannerResponse.model_validate({"assessment": "", "updated_goals": [],
                                           "actions": [action]}).actions[0]


def _market(state, sell_price=900, buy_price=1000, stock=150):
    state = copy.deepcopy(state)
    state["known_stations"] = [{"code": "SEL-001", "owner": "argon", "cls": "station",
                                "place": {"sector": "x"},
                                "offers": [{"ware": "microchips", "side": "sell",
                                            "price": sell_price, "amount": stock, "desired": 0}]}]
    home = next(a for a in state["assets"] if a["code"] == "KYV-745")
    home["offers"] = [{"ware": "microchips", "side": "buy", "price": buy_price,
                       "amount": 0, "desired": 200}]
    return state


def test_haul_is_sized_and_capped(small_state):
    command, reason = executor.plan_haul(_haul(), _market(small_state))
    # 150 in stock caps the 200 asked; the cap is the seller's price, rounded up.
    assert reason is None and command == "haul ASO-629 microchips SEL-001 argon 150 901 KYV-745"


def test_no_haul_at_a_loss(small_state):
    command, reason = executor.plan_haul(_haul(), _market(small_state, sell_price=1100))
    assert command is None and "more than KYV-745 pays" in reason


def test_no_haul_from_a_station_that_does_not_sell(small_state):
    command, reason = executor.plan_haul(_haul(), _market(small_state, stock=0))
    assert command is None and "has no microchips for sale" in reason


def test_no_haul_of_ore_in_a_container_ship(small_state):
    state = _market(small_state)
    state["known_stations"][0]["offers"][0]["ware"] = "ore"
    next(a for a in state["assets"] if a["code"] == "KYV-745")["offers"][0]["ware"] = "ore"
    command, reason = executor.plan_haul(_haul(ware="ore"), state)
    assert command is None and "solid" in reason


def test_repeat_adds_a_loop(run_cycle, fake_planner, small_state, monkeypatch):
    import agent
    monkeypatch.setattr(agent.executor, "repricing", lambda state: [])
    monkeypatch.setattr(agent.executor, "focus_fleet", lambda state: [])
    fake_planner.plan["actions"] = [{"type": "haul", "ware": "microchips",
                                     "from_station": "SEL-001", "to_station": "KYV-745",
                                     "amount": 100, "repeat": True, "rationale": "t"}]
    result = run_cycle(_market(small_state))
    assert result["commands"][-2:] == ["haul ASO-629 microchips SEL-001 argon 100 901 KYV-745",
                                       "loop ASO-629"]


def test_sale_at_the_nearest_yard_for_that_size(small_state):
    from schemas import PlannerResponse
    state = copy.deepcopy(small_state)
    sector = next(a for a in state["assets"] if a["code"] == "ASO-629")["place"]["sector"]
    # Sizes as the parser writes them (save_parser._shipyard): "s", "m", ...
    state["known_stations"] = [{"code": "YRD-S", "owner": "argon", "builds": ["s"],
                                "place": {"sector": sector}, "offers": []},
                               {"code": "YRD-M", "owner": "teladi", "builds": ["m"],
                                "place": {"sector": sector}, "offers": []}]
    sale = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "sell_ship", "ship_ref": "ASO-629", "rationale": "t"}]}).actions[0]
    assert executor.plan_sale(sale, state) == ("sellship ASO-629 YRD-M teladi", None)
    occupied = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "sell_ship", "ship_ref": "TJL-171", "rationale": "t"}]}).actions[0]
    assert "the player sits in" in executor.plan_sale(occupied, state)[1]


def test_ship_purchase_at_a_wharf_for_that_size(small_state):
    from schemas import PlannerResponse
    state = copy.deepcopy(small_state)
    sector = next(a for a in state["assets"] if a["code"] == "KYV-745")["place"]["sector"]
    state["known_stations"] = [{"code": "WRF-001", "owner": "argon", "builds": ["s", "m"],
                                "place": {"sector": sector}, "offers": []}]
    buy = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "purchase", "item": "ship", "spec": "ship_arg_s_scout_01_a_macro",
         "max_spend": 500000, "rationale": "t"}]}).actions[0]
    command, reason = executor.plan_ship_purchase(buy, state)
    # 200,000 Cr in the small save: the cap is 80 percent of it, not the 500,000 asked.
    assert reason is None
    assert command == "buyship WRF-001 argon ship_arg_s_scout_01_a_macro x4-agent-sco 160000"
    seminar = PlannerResponse.model_validate({"assessment": "", "updated_goals": [], "actions": [
        {"type": "purchase", "item": "seminar", "spec": "x", "max_spend": 1, "rationale": "t"}]}).actions[0]
    assert "advice only" in executor.plan_ship_purchase(seminar, state)[1]
