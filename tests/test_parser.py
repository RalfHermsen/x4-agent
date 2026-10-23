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
