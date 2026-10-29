"""What expansion and purchase decisions need from the save."""

import pytest


def _stations(state):
    return [a for a in state["assets"] if a["cls"] == "station"]


@pytest.mark.parametrize("which", ["small", "large"])
def test_player_blueprints(which, small_state, large_state):
    state = small_state if which == "small" else large_state
    blueprints = set(state["player"]["blueprints"])
    assert blueprints, "no blueprints read"
    # KYV-745 is built from these; holding them is how it was built at all.
    assert {"module_tel_prod_sunriseflowers_01", "module_arg_conn_base_02"} <= blueprints


def test_station_plot(small_state):
    (station,) = _stations(small_state)
    assert station["plot"] == {"x": 5000, "y": 5000, "z": 5000}


def test_built_modules_and_capacity(large_state):
    stations = _stations(large_state)
    assert stations
    for st in stations:
        assert st["modules"], f"{st['code']} has no built modules"
        assert st["capacity"], f"{st['code']} has no storage capacity"
        stock = {}
        for offer in st["offers"]:
            stock[offer["ware"]] = max(stock.get(offer["ware"], 0), offer["amount"] or 0)
        # Every unit held has to fit somewhere. A sum across types, because the
        # ware-to-type mapping is not this test's business.
        assert sum(stock.values()) <= sum(st["capacity"].values()), st["code"]
        assert 1000 <= min(st["plot"].values()) <= 50000, st["plot"]


def test_small_station_modules_and_capacity(small_state):
    # Its whole construction sequence is built; the one storage module is a
    # small Teladi container store.
    (station,) = _stations(small_state)
    assert sorted(station["modules"]) == sorted([
        "pier_tel_harbor_02_macro", "struct_arg_base_02_macro",
        "prod_tel_sunriseflowers_macro", "storage_tel_s_container_01_macro",
        "dockarea_arg_m_station_01_lowtech_macro"])
    assert station["capacity"] == {"container": 50000}


def test_builders_read_from_build_tasks():
    from lxml import etree

    from save_parser import _builders
    elem = etree.fromstring(
        '<component><buildtasks><inprogress>'
        '<build id="[0x1]" type="expand" builder="[0x2e1acd44]"/>'
        '<build id="[0x2]" type="expand" builder="[0x2e1acd44]"/>'
        '</inprogress><queue><build id="[0x3]" type="expand" builder="[0x0]"/>'
        '</queue></buildtasks></component>')
    assert _builders(elem) == ["[0x2e1acd44]"]


def test_a_running_build_is_read_with_its_start_and_its_sequence():
    from lxml import etree

    from save_parser import _build_tasks
    elem = etree.fromstring(
        '<component><buildtasks><inprogress>'
        '<build id="[0x110e]" type="expand" time="561482.53"><sequence>'
        '<entry index="1" macro="pier_tel_harbor_02_macro"/>'
        '<entry index="2" macro="defence_tel_disc_01_macro"/>'
        '</sequence></build></inprogress></buildtasks></component>')
    tasks = _build_tasks(elem)
    assert tasks["in_progress"] == 1 and tasks["queue"] == []
    assert tasks["running"] == [{"since": 561482.53,
                                 "sequence": ["pier_tel_harbor_02_macro", "defence_tel_disc_01_macro"]}]


def test_a_player_build_naming_its_own_storage_has_no_builder():
    from lxml import etree

    from save_parser import _builders
    elem = etree.fromstring(
        '<component id="[0x2b231]"><buildtasks><inprogress>'
        '<build id="[0xe53]" type="expand" builder="[0x2b231]"/>'
        '</inprogress></buildtasks></component>')
    assert _builders(elem) == []


def test_build_storage_linked_to_its_station(small_state, large_state):
    for state in (small_state, large_state):
        stations = {a["code"]: a for a in _stations(state)}
        storages = [a for a in state["assets"] if a["cls"] == "buildstorage"]
        assert storages
        for bs in storages:
            assert bs["station"] in stations, bs["code"]
            assert stations[bs["station"]]["buildstorage"] == bs["code"]
    assert {a["code"]: a["buildstorage"] for a in _stations(small_state)} == {"KYV-745": "XQL-000"}


def test_a_module_still_being_built_is_not_counted():
    from lxml import etree

    from save_parser import _built_modules
    elem = etree.fromstring(
        '<component><connections>'
        '<connection><component class="production" macro="prod_gen_water_macro" state="construction" construction="[0x1]"/></connection>'
        '<connection><component class="dockarea" macro="dockarea_arg_m_station_01_lowtech_macro" construction="[0x2]"/></connection>'
        '<connection><component class="controlroom" macro="control_room_macro"/></connection>'
        '</connections></component>')
    assert _built_modules(elem) == ["dockarea_arg_m_station_01_lowtech_macro"]


def test_the_trade_book_keeps_our_trades_with_others_only():
    from types import SimpleNamespace as S
    import save_parser
    assets = [S(id="[st]", cls="station", code="KYV-745", station=None),
              S(id="[bs]", cls="buildstorage", code="XQL-000", station="KYV-745"),
              S(id="[st2]", cls="station", code="GKL-870", station=None)]
    trades = [(10.0, "water", "[npc]", "[st]", 5000, 100),      # sold 100 at 50 Cr
              (20.0, "ice", "[st]", "[npc]", 2500, 200),        # bought 200 at 25 Cr
              (30.0, "claytronics", "[bs]", "[npc]", 200000, 2),  # the build storage buys for its station
              (40.0, "water", "[st2]", "[st]", 5000, 999)]      # between two of ours: no money moves
    book = save_parser._trade_book(trades, assets)
    kyv = book["stations"]["KYV-745"]
    assert kyv["water"]["sold"] == 100 and kyv["water"]["sold_cr"] == 5000
    assert kyv["ice"]["bought_cr"] == 5000 and kyv["claytronics"]["bought_cr"] == 4000
    assert "GKL-870" not in book["stations"] and (book["since"], book["until"]) == (10.0, 30.0)


def test_a_ship_trader_is_read_from_the_station_posts():
    from lxml import etree

    from save_parser import _shiptrader
    ours = etree.fromstring('<component><control><post id="manager" component="[0x2969d]"/>'
                            '<post id="defence" component="[0x29059]"/></control></component>')
    npc = etree.fromstring('<component><control><post id="shiptrader" component="[0xa7e4]"/>'
                           '<post id="manager" component="[0xa7e5]"/></control></component>')
    assert (_shiptrader(ours), _shiptrader(npc)) == (False, True)


def test_the_drones_a_station_keeps_are_read_from_its_supply_orders():
    from lxml import etree

    from save_parser import _supplies
    elem = etree.fromstring('<component><supplies><orders>'
                            '<ware ware="ship_gen_xs_repairdrone_01_a" amount="3"/>'
                            '<ware ware="ship_gen_xs_cargodrone_empty_01_a" amount="10"/>'
                            '</orders></supplies></component>')
    assert _supplies(elem) == {"ship_gen_xs_repairdrone_01_a": 3, "ship_gen_xs_cargodrone_empty_01_a": 10}
    assert _supplies(etree.fromstring("<component/>")) == {}


def test_upkeep_missions_are_read_for_the_station_or_its_manager(tmp_path):
    """GKL-870 was asked for a miner and for cargo drones from game hour 77
    on; the miner's mission hangs on the station's manager, not the station."""
    from save_parser import parse_save
    station = ('<component class="station" macro="station_tel_m_01_macro" code="GKL-870" id="[0x80a8d]" '
               'owner="player"><control><post id="manager" component="[0x80a97]"/></control></component>')
    nest = station
    for cls in ("zone", "sector", "cluster", "galaxy"):
        nest = f'<component class="{cls}" macro="{cls}_macro"><connections><connection>{nest}</connection></connections></component>'
    save = tmp_path / "save.xml"
    save.write_text(
        '<savegame><info><game time="900000"/><player money="1"/></info>'
        f'<universe>{nest}</universe><missions>'
        '<mission id="1" time="277236" name="Assign subordinate" description="Assign a mining ship" '
        'faction="player" type="upkeep_subordinates" associated="[0x80a97]"/>'
        '<mission id="2" time="276924" name="Restock Cargo Drones" description="Restock cargo drones" '
        'faction="player" type="upkeep_subordinates" associated="[0x80a8d]"/>'
        '<mission id="3" time="1" name="Hyperion Sightings" faction="civilian" type="story"/>'
        '</missions></savegame>', encoding="utf-8")
    assert [(m["station"], m["name"]) for m in parse_save(save)["upkeep"]] == [
        ("GKL-870", "Assign subordinate"), ("GKL-870", "Restock Cargo Drones")]


def test_ships_paid_for_and_not_delivered_are_read_from_the_wharf_queue():
    from lxml import etree

    from save_parser import _ships_on_order
    elem = etree.fromstring(
        '<component><buildtasks><queue>'
        '<build id="[0x1]" type="buildship" faction="player" macro="ship_par_m_miner_solid_01_a_macro" '
        'time="309643.2" price="912950" transferred="912950"><resources><insufficient>'
        '<ware ware="advancedelectronics" amount="12"/></insufficient></resources></build>'
        '<build id="[0x2]" type="buildship" faction="paranid" macro="ship_par_m_fighter_01_a_macro" time="1"/>'
        '</queue></buildtasks></component>')
    assert _ships_on_order(elem, "SCY-867") == [
        {"wharf": "SCY-867", "macro": "ship_par_m_miner_solid_01_a_macro", "since": 309643.2,
         "paid": 912950, "missing": ["advancedelectronics"]}]
