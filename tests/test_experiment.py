"""The run harness (experiment.py): what it can check without the game."""

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
