"""Which commander a subordinate serves: every commander numbers its groups itself."""

import copy

import catalog
import executor
import save_parser


def _two_stations(state):
    """KYV-745 with group 1 for trade, GKL-870 with group 1 for mining: what the
    leanclaude-long run had when four miners were sent to sell wafers."""
    state = copy.deepcopy(state)
    kyv = next(a for a in state["assets"] if a["code"] == "KYV-745")
    kyv["assignment"] = {"groups": {1: "trade", 2: "mining"}}
    gkl = dict(copy.deepcopy(kyv), code="GKL-870", cargo={}, offers=[],
               assignment={"groups": {1: "mining"}})
    state["assets"].append(gkl)
    return state, kyv


def _ship(state, code, macro, group):
    ship = dict(copy.deepcopy(next(a for a in state["assets"] if a["code"] == "ASO-629")),
                code=code, macro=macro, assignment={} if group is None else {"group": group})
    state["assets"].append(ship)
    return ship


def test_the_last_assignment_line_names_the_commander():
    log = [[10.0, "[x4-agent] ORDER: EBR-694 now mines for GKL-870"],
           [20.0, "[x4-agent] ORDER: EBR-694 now mines for KYV-745"],
           [15.0, "[x4-agent] ORDER: FTR-001 under LDR-001 as defence, commander now LDR-001"],
           [16.0, "[x4-agent] ORDER: JUN-174 now supplies the build storage of GKL-870"],
           [17.0, "[x4-agent] ORDER: JUN-174 now supplies Silicon Wafers only"],
           [18.0, "[x4-agent] COMMANDER: QNL-869 works for KYV-745"]]
    assert save_parser._assigned_to(log) == {"EBR-694": "KYV-745", "FTR-001": "LDR-001",
                                             "JUN-174": "GKL-870", "QNL-869": "KYV-745"}


def test_the_bridge_names_every_commander_on_load_in_a_line_the_parser_reads():
    import re
    from pathlib import Path
    bridge = Path(__file__).resolve().parents[1] / "bridge" / "x4_agent_bridge" / "md" / "x4_agent_bridge.xml"
    text = bridge.read_text(encoding="utf-8")
    cue = text[text.index('<cue name="Log_Commanders"'):]
    cue = cue[:cue.index("</cue>")]
    assert "<event_game_loaded/>" in cue
    line = re.search(r"text=\"'(\[x4-agent\] COMMANDER: [^']+)'", cue).group(1)
    assert save_parser._assigned_to([[1.0, line % ("QNL-869", "KYV-745")]]) == {"QNL-869": "KYV-745"}


def test_a_miner_assigned_before_the_bridge_logged_is_still_its_stations(small_state):
    # ship6-camp: four of KYV-745's miners in its group 2 had no ORDER line;
    # GKL-870 got a group 2 for trade, a miner can trade, so nobody could say,
    # and four more miners were bought in their place.
    state, kyv = _two_stations(small_state)
    gkl = next(a for a in state["assets"] if a["code"] == "GKL-870")
    gkl["assignment"] = {"groups": {1: "tradeforbuildstorage", 2: "trade"}}
    miner = _ship(state, "QNL-869", "ship_par_m_miner_solid_01_a_macro", 2)
    state["assigned_to"] = {}
    assert executor.serves(miner, state) == (None, None)
    state["assigned_to"] = save_parser._assigned_to([[1.0, "[x4-agent] COMMANDER: QNL-869 works for KYV-745"]])
    assert executor.serves(miner, state) == ("KYV-745", "mining")


def test_a_group_number_is_read_on_the_ships_own_commander(small_state):
    state, _ = _two_stations(small_state)
    miner = _ship(state, "MNR-001", "ship_arg_m_miner_solid_01_a_macro", 1)
    state["assigned_to"] = {}
    assert executor.serves(miner, state) == (None, None)    # group 1 on both: nobody can say
    state["assigned_to"] = {"MNR-001": "GKL-870"}
    assert executor.serves(miner, state) == ("GKL-870", "mining")
    miner["assignment"] = {"group": 2}
    state["assigned_to"] = {}
    assert executor.serves(miner, state) == ("KYV-745", "mining")   # only KYV-745 has a group 2


def test_without_a_logbook_line_the_hull_decides(small_state):
    state, _ = _two_stations(small_state)
    state["assigned_to"] = {}
    freighter = _ship(state, "TRD-001", "ship_arg_m_trans_container_01_a_macro", 1)
    miner = _ship(state, "MNR-001", "ship_arg_m_miner_solid_01_a_macro", 1)
    assert executor.serves(freighter, state) == ("KYV-745", "trade")   # it cannot mine
    assert executor.serves(miner, state) == (None, None)               # it could do either


def test_a_miner_of_another_station_is_not_sent_to_sell(small_state):
    state, kyv = _two_stations(small_state)
    kyv["cargo"] = {"siliconwafers": 50000}
    kyv["offers"] = [{"ware": "siliconwafers", "side": "sell", "price": 200, "amount": 50000}]
    trader = _ship(state, "TRD-001", "ship_arg_m_trans_container_01_a_macro", 1)
    _ship(state, "MNR-001", "ship_arg_m_miner_solid_01_a_macro", 1)
    state["assets"] = [a for a in state["assets"] if a["code"] in ("KYV-745", "GKL-870")
                       or a is trader or a["code"] == "MNR-001"]
    state["assigned_to"] = {"TRD-001": "KYV-745", "MNR-001": "GKL-870"}
    assert executor.focus_fleet(state) == ["sellware TRD-001 siliconwafers"]


def test_a_miner_working_for_one_station_is_not_offered_to_the_other(small_state):
    state, kyv = _two_stations(small_state)
    gkl = next(a for a in state["assets"] if a["code"] == "GKL-870")
    gkl["offers"] = [{"ware": "ore", "side": "buy", "desired": 10000, "amount": 10000}]
    gkl["cargo"] = {"ore": 100}
    _ship(state, "MNR-001", "ship_arg_m_miner_solid_01_a_macro", 2)   # KYV-745's miner
    _ship(state, "MNR-002", "ship_arg_m_miner_solid_01_a_macro", None)
    state["assets"] = [a for a in state["assets"] if a["code"] != "ASO-629"]
    state["assigned_to"] = {"MNR-001": "KYV-745"}
    found = {s.key: s for s in catalog.situations(state)}
    commands = [o.command for o in found["short:GKL-870:ore"].options]
    assert "assign MNR-002 GKL-870 mine" in commands
    assert not any(c.startswith("assign MNR-001") for c in commands)


def test_a_purchase_just_sent_holds_the_next_before_the_save_shows_it(small_state):
    state = copy.deepcopy(small_state)
    state["logbook"] = []
    state["sent_at"] = {"buyship": state["meta"]["playtime_s"]}
    assert catalog._bought_recently(state)
    state["sent_at"] = {"buyship": state["meta"]["playtime_s"] - catalog.PURCHASE_GAP - 1}
    assert not catalog._bought_recently(state)
