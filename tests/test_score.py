"""The scorecard counts what the report counts."""

import copy

import score


def test_small_save_card(small_state):
    card = score.score(small_state)
    assert card["stations"] == 1
    assert card["ships"] == 2
    assert card["credits"] == 200_000
    assert card["idle"] == 2          # both ships sit on Wait in this save
    assert card["fleet"] == ["ASO-629", "TJL-171"]


def test_large_save_card(large_state):
    card = score.score(large_state)
    assert card["stations"] == 2
    assert card["ships"] > 20
    assert sum(card["roles"].values()) == card["ships"]


def test_compare_lists_ships_gone(small_state):
    before = score.score(small_state)
    after_state = copy.deepcopy(small_state)
    after_state["assets"] = [a for a in after_state["assets"] if a["code"] != "TJL-171"]
    after_state["player"]["money"] = 250_000
    text = score.compare(before, score.score(after_state))
    assert "ships gone (1): TJL-171" in text
    assert "+50,000" in text


def test_net_worth_counts_accounts_and_stock(small_state):
    import copy
    state = copy.deepcopy(small_state)
    station = next(a for a in state["assets"] if a["code"] == "KYV-745")
    station["account"] = {"amount": "1000"}
    station["cargo"] = {"energycells": 100}
    card = score.score(state)
    assert card["accounts"] >= 1000
    assert card["stock_min"] > 0 and card["stock_avg"] >= card["stock_min"]
    assert card["net_worth"] == card["credits"] + card["accounts"] + card["stock_min"]
