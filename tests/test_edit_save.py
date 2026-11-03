import edit_save


SMALL_FACTION = ('<faction id="player">\n<relations>\n<relation faction="terran" relation="-0.032"/>\n'
                 '<booster faction="teladi" relation="1" time="5"/>\n</relations>\n<licences>\n'
                 '<licence type="generaluseship" factions="argon teladi"/>\n</licences>\n</faction>')


def test_a_relation_is_set_or_added_before_the_boosters():
    xml = edit_save.set_relations(SMALL_FACTION, {"terran": 0.1, "argon": 0.1})
    assert '<relation faction="terran" relation="0.1"/>' in xml and "-0.032" not in xml
    assert xml.index('faction="argon"') < xml.index("<booster")


def test_a_factions_own_value_toward_the_player_is_set_too():
    """The new start kept Terran's -0.032 toward the player, -15 in the menu."""
    terran = ('<faction id="terran">\n<relations>\n<relation faction="argon" relation="0.5"/>\n'
              '<relation faction="player" relation="-0.032"/>\n</relations>\n</faction>\n')
    xml = edit_save.set_relations(terran + SMALL_FACTION, {"terran": 0.1})
    assert "-0.032" not in xml and xml.count('relation="0.1"') == 2
    assert '<relation faction="argon" relation="0.5"/>' in xml


def test_a_licence_adds_factions_to_its_type_or_a_new_type():
    xml, added = edit_save.add_licences(SMALL_FACTION, {"generaluseship": ["argon", "terran"],
                                                        "capitalship": ["argon"]})
    assert added == ["generaluseship terran", "capitalship argon"]
    assert '<licence type="generaluseship" factions="argon teladi terran"/>' in xml
    assert '<licence type="capitalship" factions="argon"/>' in xml


def test_know_stations_marks_only_that_sector():
    xml = ('<component class="sector" macro="A"><component class="station" code="X"/>'
           '<component class="station" knownto="player" code="Y"/>'
           '<component class="sector" macro="B"><component class="station" code="Z"/>')
    out, count = edit_save.know_stations(xml, "A")
    assert count == 1 and 'knownto="player" code="X"' in out
    assert '<component class="station" code="Z"/>' in out
