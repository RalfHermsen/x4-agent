"""The run harness (experiment.py): what it can check without the game."""

import gzip
import os
import time

import experiment


def test_a_stalled_run_reloads_the_newest_save_it_wrote(tmp_path):
    old, new = tmp_path / "autosave_01.xml.gz", tmp_path / "save_008.xml.gz"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    now = time.time()
    os.utime(old, (now - 100, now - 100))
    os.utime(new, (now - 10, now - 10))
    assert experiment.newest_save(tmp_path, now - 50) == new
    assert experiment.newest_save(tmp_path, now - 5) is None      # nothing written since the run began


def test_the_players_ship_is_the_one_the_player_last_controlled(tmp_path):
    save = tmp_path / "save.xml.gz"
    with gzip.open(save, "wt", encoding="utf-8") as handle:
        handle.write('<component class="ship_l" macro="m" code="AAA-111" owner="player" id="[0x10]">\n'
                     '<component class="ship_s" macro="m" code="NBO-436" owner="player" id="[0x2a12b]">\n'
                     '<component class="player" macro="m" code="CKM-779" lastcontrolled="[0x2a12b]" '
                     'controlgroup="pilotcontrol" id="[0x2a136]">\n')
    assert experiment.player_ship(save) == "NBO-436"
    assert experiment.player_ship(tmp_path / "missing.xml.gz") is None


def test_a_hung_game_is_ended_only_with_no_save_being_written(tmp_path, monkeypatch):
    """ship7b-camp: the game thread hung and the run waited out 110 minutes."""
    import launch_game
    killed = []
    monkeypatch.setattr(launch_game, "answers", lambda: False)
    monkeypatch.setattr(launch_game.subprocess, "run", lambda args, **kw: killed.append(args))
    monkeypatch.setattr(launch_game, "running", lambda: not killed)
    save = tmp_path / "save_008.xml.gz"
    save.write_bytes(b"x")
    assert launch_game.kill(tmp_path).startswith("not killed: a save changed")
    old = time.time() - launch_game.SAVE_SETTLE - 1
    os.utime(save, (old, old))
    monkeypatch.setattr(launch_game, "answers", lambda: True)
    assert launch_game.kill(tmp_path) == "not killed: the game thread answers"
    monkeypatch.setattr(launch_game, "answers", lambda: False)
    assert killed == [] and launch_game.kill(tmp_path) == "ended"
    assert killed == [["taskkill", "/F", "/IM", "X4.exe"]]
