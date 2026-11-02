import edit_save


SMALL_FACTION = ('<faction id="player">\n<relations>\n<relation faction="terran" relation="-0.032"/>\n'
                 '<booster faction="teladi" relation="1" time="5"/>\n</relations>\n<licences>\n'
                 '<licence type="generaluseship" factions="argon teladi"/>\n</licences>\n</faction>')


def test_a_relation_is_set_or_added_before_the_boosters():
    xml = edit_save.set_relations(SMALL_FACTION, {"terran": 0.1, "argon": 0.1})
    assert '<relation faction="terran" relation="0.1"/>' in xml and "-0.032" not in xml
    assert xml.index('faction="argon"') < xml.index("<booster")


def test_a_licence_adds_factions_to_its_type_or_a_new_type():
    xml, added = edit_save.add_licences(SMALL_FACTION, {"generaluseship": ["argon", "terran"],
                                                        "capitalship": ["argon"]})
    assert added == ["generaluseship terran", "capitalship argon"]
    assert '<licence type="generaluseship" factions="argon teladi terran"/>' in xml
    assert '<licence type="capitalship" factions="argon"/>' in xml
