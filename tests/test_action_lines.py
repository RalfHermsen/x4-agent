"""action_lines: the parser in front of call 2, on lines from real cycles."""

import action_lines as bx

REPORT = """# SITUATION
Playtime: 264846s. Capital: 50,000,000 Cr.

# OWN STATIONS
KYV-745 (station_gen_factory_base_01_macro) in Hewa's Twin I
  manager YVA-122: management 3 stars
GKL-870 (station_gen_factory_base_01_macro) in Hewa's Twin I

# FLEET (3 ships)
ASO-629 container freighter (ship_m), working for itself: IDLE, docked at KYV-745
TJL-171 scout (ship_s), working for itself: IDLE, in Hewa's Twin I
PQA-833 scout (ship_s), working for itself: IDLE, in Hewa's Twin I

# KNOWN MARKET
XPP-596 sells majadust at 120 Cr
"""
WARES = {"energycells", "water", "siliconwafers", "microchips", "majadust"}


def parse(line):
    own, ships, _ = bx.vocabulary(REPORT)
    return bx.parse_line(line, own, ships, WARES)


def one(line):
    actions = parse(line)
    assert len(actions) == 1, (line, actions)
    return actions[0]


def test_vocabulary_reads_own_stations_and_ships():
    own, ships, codes = bx.vocabulary(REPORT)
    assert own == {"KYV-745", "GKL-870"}
    assert ships == {"ASO-629", "TJL-171", "PQA-833"}
    assert "XPP-596" in codes and "YVA-122" not in own


def test_price_lines_in_every_form_seen():
    want = {"type": "set_price", "station_id": "KYV-745", "ware": "water",
            "side": "sell", "price": 73.0}
    for line in ("6. KYV-745: set_price water 73 (KYV-745 sell price is 54, best bid 74)",
                 "6. set_price KYV-745 water 73.0",
                 "6. Set KYV-745 sell price for water to 73 Cr",
                 "6. Set sell price for water at `KYV-745` to 73 Cr (Guideline: Manual pricing)"):
        assert parse(line) == [want], line


def test_two_word_ware_names_are_joined():
    assert one("1. KYV-745: set sell price for silicon wafers to 402")["ware"] == "siliconwafers"


def test_several_prices_on_one_line():
    actions = parse("1. Set `set_price` for KYV-745: microchips to 1198, water to 74, "
                    "and energycells to 21 (KYV-745, Pricing).")
    assert [(a["ware"], a["price"]) for a in actions] == [
        ("microchips", 1198.0), ("water", 74.0), ("energycells", 21.0)]
    # A number that belongs to no ware makes the line a reading.
    assert parse("1. KYV-745: set_price water 73, up from 54") == []


def test_budget_needs_a_level_word_not_an_amount():
    assert parse("4. GKL-870: set budget to mid") == [
        {"type": "set_budget", "station_id": "GKL-870", "level": "mid"}]
    assert parse("4. GKL-870: set_operating_budget 1000000") == []
    assert parse("3. KYV-745: Set operational budget to 50,000 Cr.") == []


def test_behaviours_and_assignments():
    assert parse("1. TJL-171: Explore") == [
        {"type": "set_behaviour", "ship_ref": "TJL-171", "behaviour": "explore"}]
    assert one("4. assign PQA-833 to explore")["behaviour"] == "explore"
    assert parse("2. ASO-629: Assign to KYV-745 as a trader to move goods") == [
        {"type": "assign_ship", "ship_ref": "ASO-629", "station_id": "KYV-745", "role": "trade"}]
    two = parse("1. Assign ASO-629 and PQA-833 to Mine for station KYV-745 (ore)")
    assert [(a["ship_ref"], a["role"]) for a in two] == [("ASO-629", "mine"), ("PQA-833", "mine")]
    # "for autotrade" under a station is ambiguous between two types: left alone.
    assert parse("2. ASO-629: Assign to KYV-745 for autotrade") == []


def test_unsure_lines_are_left_to_a_model():
    assert parse("2. ASO-629: Repeat Order: Buy majadust at XPP-596 and sell at KYV-745.") == []
    assert parse("9. PQA-833: assign_as_scout") == []
    # Two numbers for one ware: which is the price is a reading, not a parse.
    assert parse("1. KYV-745: set_price water 73 or 75") == []


def test_a_code_not_in_the_report_cannot_come_out():
    assert parse("1. ZZZ-999: set_price water 73") == []
    assert parse("1. MINER: Explore") == []


def test_aggregated_fleet_names_its_examples_and_idle_ships():
    report = """# OWN STATIONS
KYV-745 (station_gen_factory_base_01_macro) in Hewa's Twin I

# FLEET (29 ships)
trader      10   TradeRoutine_Basic 10
              examples: JFZ-239, CVT-715, FUV-966

# ATTENTION
NUH-323 is a solid miner with no orders at all. It is earning nothing until it is given work.
KYV-745 is low on water: 10 in store, room for 900 (1% full).
"""
    own, ships, _ = bx.vocabulary(report)
    assert own == {"KYV-745"}
    assert ships == {"JFZ-239", "CVT-715", "FUV-966", "NUH-323"}


def test_numbered_lines_stop_at_the_goals():
    analysis = ("thinking...\nACTIONS:\n1. TJL-171: Explore\n2. KYV-745: set_price water 73\n\n"
                "STANDING GOALS:\n1. Grow\n")
    assert bx.numbered_lines(analysis) == ["1. TJL-171: Explore", "2. KYV-745: set_price water 73"]
