"""One unattended run of the agent in the real game, measured.

Launch the game, load a baseline save, start the host in advise or execute
mode, let the game run, save into the agent's own slot, stop, and compare the
result with the baseline on the scorecard. Everything the run produces goes
into one folder under out/experiments/, and the player's own saves are put
back exactly as they were.

The player's saves: the game autosaves on its own interval during a long run,
and those slots hold the newest state of whatever the player played last. So
before launching, autosave_01 to 03 and the quicksave are copied into the run
folder, and after the game has exited, any of them that changed is copied
back. The run writes only save_008, the agent's slot (tasks/lessons.md L6e).

Usage:
    python experiment.py --load save_007 --mode advise --minutes 120
    python experiment.py --load save_007 --mode execute --minutes 120
    python experiment.py --load quicksave --mode execute --script s.json \\
        --until-blueprint module_tel_conn_cross_01 --minutes 30
    python experiment.py --baseline-file saves/reference/baseline_seta.xml.gz \\
        --seta --mode execute --minutes 120

--baseline-file copies a save into the agent's slot before the game starts
(the game reads the save folder only at startup) and loads it from there.
--seta asks for six-times time warp after loading and every five minutes,
which needs the SETA item in that save (edit_save.py --inventory).

The Ollama URL comes from X4_OLLAMA_URL; a scripted run needs no model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import launch_game
import score
from save_parser import documents_dir, parse_save

REPO = Path(__file__).parent
OUTBOX = REPO / "logs" / "outbox.txt"
AGENT_SLOT = "save_008"
# The game end of the pipe can go and not come back: "Pipe client garbage
# collected" in the host log, the host serving again, and the game sending
# nothing more. leanplan-test stood still for 80 of its 120 minutes so, and
# leancat2-long for its last seven hours. Loading the run's newest save starts
# the game's Lua and MD afresh, and they connect again. A planner thinking for
# five minutes is the longest the host has been silent while working.
STALL_AFTER = 600
MAX_RELOADS = 3
PROTECTED = ("autosave_01", "autosave_02", "autosave_03", "quicksave")


def save_dir(load: str) -> Path:
    """The profile's save folder that holds the save to load.

    Not simply the first one: a profile can have more than one numbered folder
    (an empty numbered folder sorted before the real one here), and the first version
    of this picked the empty one, snapshotted nothing and watched a slot that
    never changed.
    """
    root = documents_dir() / "Egosoft" / "X4"
    holding = sorted(p.parent for p in root.glob(f"*/save/{load}.xml.gz"))
    if not holding:
        raise SystemExit(f"no {load}.xml.gz in any save folder under {root}")
    return holding[0]


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def snapshot(folder: Path, into: Path) -> dict[str, str]:
    into.mkdir(parents=True, exist_ok=True)
    sums = {}
    for name in PROTECTED:
        src = folder / f"{name}.xml.gz"
        if src.exists():
            shutil.copy2(src, into / src.name)
            sums[src.name] = _md5(src)
    return sums


def restore(folder: Path, frm: Path, sums: dict[str, str]) -> list[str]:
    """Put back every protected save that changed. Only after the game exited."""
    restored = []
    for name, digest in sums.items():
        live = folder / name
        if not live.exists() or _md5(live) != digest:
            shutil.copy2(frm / name, live)
            restored.append(name)
    return restored


def player_piloting(save: Path) -> bool | None:
    """Whether the save has the player in a pilot seat (controlgroup
    "pilotcontrol"), None if the player is not found. SETA is offered only
    from a pilot seat: the ceremony baseline had the player aboard NBO-436
    but standing, and two runs on it went at normal speed, 5.8 game hours in
    six real ones."""
    import gzip
    try:
        with gzip.open(save, "rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '<component class="player"' in line:
                    return 'controlgroup="pilotcontrol"' in line
    except OSError:
        return None
    return None


def player_ship(save: Path) -> str | None:
    """The code of the ship the player last controlled, None if not found.
    The ship's component line comes before the player's, who sits inside it."""
    import gzip
    import re
    codes = {}
    try:
        with gzip.open(save, "rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '<component class="ship_' in line:
                    code, ident = re.search(r' code="([^"]+)"', line), re.search(r' id="([^"]+)"', line)
                    if code and ident:
                        codes[ident.group(1)] = code.group(1)
                elif '<component class="player"' in line:
                    last = re.search(r' lastcontrolled="([^"]+)"', line)
                    return codes.get(last.group(1)) if last else None
    except OSError:
        return None
    return None


def game_version(save: Path) -> str | None:
    """"9.00 (611726)" from a save's header: the version of the game that wrote it.

    Runs on different game versions are not comparable: the bridge calls the
    game's own Lua and MD, and an update can change what a verb does.
    """
    import gzip
    import re
    try:
        with gzip.open(save, "rt", encoding="utf-8", errors="replace") as handle:
            head = handle.read(4096)
    except OSError:
        return None
    m = re.search(r'<game [^>]*version="(\d+)"[^>]*build="(\d+)"', head)
    return f"{int(m.group(1)) / 100:.2f} ({m.group(2)})" if m else None


def log(run_dir: Path, message: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {message}"
    print(line, flush=True)
    with (run_dir / "run.log").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def start_host(run_dir: Path, mode: str, interval: int, script: Path | None) -> subprocess.Popen:
    env = dict(os.environ)
    env["X4_AGENT_MEMORY"] = str(run_dir / "memory.json")
    env["X4_AGENT_LOG"] = str(run_dir / "agent.log")
    env["X4_AGENT_SAVE_VERB"] = "savegame"
    if script:
        env["X4_AGENT_SCRIPT"] = str(script)
    args = [sys.executable, str(REPO / "run_host.py"), "--interval", str(interval)]
    if mode == "execute":
        args.append("--execute")
    out = (run_dir / "host.log").open("w", encoding="utf-8")
    return subprocess.Popen(args, env=env, stdout=out, stderr=subprocess.STDOUT, cwd=REPO)


def wait_connected(run_dir: Path, timeout: float = 90) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            if "X4 connected" in (run_dir / "host.log").read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            pass
        time.sleep(2)
    return False


def request_save(slot: Path, timeout: float = 300) -> bool:
    # 150 s was not enough: a run under SETA wrote its final save 4 s after.
    before = slot.stat().st_mtime if slot.exists() else 0
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    with OUTBOX.open("a", encoding="utf-8") as handle:
        handle.write("savegame\n")
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if slot.exists() and slot.stat().st_mtime > before:
            return True
        time.sleep(2)
    return False


def newest_save(folder: Path, since: float) -> Path | None:
    """The newest save the game wrote into `folder` after `since` (epoch s)."""
    saves = [p for p in folder.glob("*.xml.gz") if p.stat().st_mtime > since]
    return max(saves, key=lambda p: p.stat().st_mtime) if saves else None


def stop_host(proc: subprocess.Popen) -> None:
    import run_host
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    stale = run_host.running_hosts()
    if stale:
        run_host.stop(stale)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--load", default="save_007")
    parser.add_argument("--mode", choices=("advise", "execute"), default="advise")
    parser.add_argument("--minutes", type=float, default=120)
    parser.add_argument("--interval", type=int, default=180, help="host planning interval, s")
    parser.add_argument("--script", type=Path, help="scripted planner responses (JSON list)")
    parser.add_argument("--until-blueprint", help="stop early once this ware is held")
    parser.add_argument("--name", default="", help="suffix for the run folder")
    parser.add_argument("--baseline-file", type=Path,
                        help="a save to copy into the agent's slot and load from there")
    parser.add_argument("--seta", action="store_true", help="run at six-times time warp")
    args = parser.parse_args()

    if args.baseline_file:
        args.load = AGENT_SLOT
    folder = save_dir(args.load) if not args.baseline_file else save_dir("autosave_01")
    slot = folder / f"{AGENT_SLOT}.xml.gz"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = REPO / "out" / "experiments" / f"{stamp}-{args.mode}{'-' + args.name if args.name else ''}"
    run_dir.mkdir(parents=True, exist_ok=True)
    baseline = REPO / "saves" / "reference" / f"{args.load}.xml.gz"
    if args.baseline_file:
        baseline = args.baseline_file
    elif not baseline.exists():
        baseline = folder / f"{args.load}.xml.gz"
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                            capture_output=True, text=True).stdout.strip()
    (run_dir / "run.json").write_text(json.dumps({
        "load": args.load, "baseline": str(baseline), "mode": args.mode,
        "minutes": args.minutes, "interval": args.interval,
        "script": str(args.script) if args.script else None,
        "until_blueprint": args.until_blueprint, "commit": commit,
        "baseline_file": str(args.baseline_file) if args.baseline_file else None,
        "seta": args.seta, "catalog": os.environ.get("X4_CATALOG") == "1",
        "rules_only": os.environ.get("X4_RULES_ONLY") == "1",
        "no_pricing": os.environ.get("X4_NO_PRICING") == "1",
        "rules_off": os.environ.get("X4_RULES_OFF", ""),
        "planner_model": os.environ.get("X4_PLANNER_MODEL") or "default",
        "strategy_file": os.environ.get("X4_STRATEGY_FILE"),
        "strategist_model": os.environ.get("X4_STRATEGIST_MODEL"),
        "baseline_game": game_version(Path(baseline)),
        "started": datetime.now().isoformat(timespec="seconds")}, indent=2), encoding="utf-8")

    if launch_game.running():
        log(run_dir, "X4 is already running; not starting an experiment on top of it")
        return 2
    if args.seta and player_piloting(Path(baseline)) is False:
        log(run_dir, f"{Path(baseline).name} has the player out of the pilot seat, where SETA is not "
                     f"offered; not starting a run that would go at normal speed")
        return 2
    # The run tests the bridge in this checkout, not whatever a proof left in
    # the game folder: a run on 2026-10-23 spent half an hour on a probe build
    # of the Lua and an MD without the verb the rules were sending.
    deployed = subprocess.run([sys.executable, "deploy_bridge.py"], cwd=REPO,
                              capture_output=True, text=True, encoding="utf-8")
    if deployed.returncode != 0:
        log(run_dir, f"could not deploy the bridge: {deployed.stderr.strip()}")
        return 1
    log(run_dir, "bridge deployed from this checkout")
    sums = snapshot(folder, run_dir / "player-saves")
    if not sums:
        log(run_dir, f"no protected saves found in {folder}; refusing to run without a copy")
        return 2
    log(run_dir, f"protected saves copied: {', '.join(sums)}")
    proc = None
    code = 1
    try:
        if args.baseline_file:
            shutil.copy2(args.baseline_file, slot)
            log(run_dir, f"{args.baseline_file.name} copied into {AGENT_SLOT} before launch")
        if launch_game.launch(180) != 0 or launch_game.load(args.load, 180) != 0:
            log(run_dir, "could not launch or load")
            return 1
        proc = start_host(run_dir, args.mode, args.interval, args.script)
        if not wait_connected(run_dir):
            log(run_dir, "host did not connect")
            return 1
        log(run_dir, f"running {args.mode} for up to {args.minutes:.0f} min from {args.load}")
        end = time.monotonic() + args.minutes * 60
        next_seta = time.monotonic()
        seen = slot.stat().st_mtime if slot.exists() else 0
        next_note = time.monotonic() + 600
        started, reloads = time.time(), 0
        # The player's own ship can be shot down while the run goes on around
        # it. The player then floats in a spacesuit, without SETA, and in three
        # runs (2026-10-23 to 10-26) the game ended about half an hour of game
        # time later; a reload replays the same death. So the run stops there,
        # while the game can still save.
        ship, read_to = player_ship(Path(baseline)), 0
        while time.monotonic() < end:
            time.sleep(20)
            if ship:
                with (run_dir / "host.log").open(encoding="utf-8", errors="replace") as handle:
                    handle.seek(read_to)
                    news = handle.read()
                    read_to = handle.tell()
                if f"event destroyed {ship}" in news:
                    log(run_dir, f"the player's ship {ship} was destroyed; stopping the run while the game can save")
                    break
            if launch_game.restore_window():
                log(run_dir, "the game window was minimized, so the game stood still; restored it")
            quiet = time.time() - (run_dir / "host.log").stat().st_mtime
            if quiet > STALL_AFTER and reloads < MAX_RELOADS:
                save = newest_save(folder, started)
                if save is None:
                    log(run_dir, f"host log quiet for {quiet / 60:.0f} min and no save of this run to reload")
                else:
                    reloads += 1
                    log(run_dir, f"host log quiet for {quiet / 60:.0f} min; reloading {save.name} "
                                 f"({reloads} of {MAX_RELOADS})")
                    if launch_game.load(save.name.removesuffix(".xml.gz"), 180) != 0:
                        log(run_dir, f"reloading {save.name} failed")
                    next_seta = time.monotonic()
            if args.seta and time.monotonic() >= next_seta:
                OUTBOX.parent.mkdir(parents=True, exist_ok=True)
                with OUTBOX.open("a", encoding="utf-8") as handle:
                    handle.write("seta on\n")
                next_seta = time.monotonic() + 300
            if time.monotonic() >= next_note:
                log(run_dir, f"{(end - time.monotonic()) / 60:.0f} min left")
                next_note += 600
            if args.until_blueprint and slot.exists() and slot.stat().st_mtime > seen:
                seen = slot.stat().st_mtime
                held = args.until_blueprint in (parse_save(slot)["player"].get("blueprints") or [])
                try:
                    jobs = json.loads((run_dir / "memory.json").read_text(encoding="utf-8")).get("purchases", {})
                except (OSError, json.JSONDecodeError):
                    jobs = {"?": 1}
                # Done means bought and the job closed, which is when the ship
                # is released: both halves are part of the proof.
                if held and not jobs:
                    log(run_dir, f"{args.until_blueprint} is held and the job is closed; stopping early")
                    break
        if request_save(slot):
            log(run_dir, f"final state saved into {AGENT_SLOT}")
            shutil.copy2(slot, run_dir / f"result-{AGENT_SLOT}.xml.gz")
            # The game that ran, from the save it wrote last.
            record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            record["game"] = game_version(slot)
            (run_dir / "run.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            log(run_dir, f"game {record['game']}")
            card = score.compare(score.score(parse_save(baseline)), score.score(parse_save(slot)))
            (run_dir / "score.txt").write_text(card, encoding="utf-8")
            log(run_dir, "scorecard:\n" + card)
            code = 0
        else:
            log(run_dir, "the final save did not arrive")
    finally:
        if proc is not None:
            stop_host(proc)
        if launch_game.running():
            launch_game.stop(120)
        if not launch_game.running():
            restored = restore(folder, run_dir / "player-saves", sums)
            log(run_dir, f"player saves restored: {', '.join(restored) or 'none had changed'}")
        else:
            log(run_dir, "X4 still running: player saves NOT restored; copies are in player-saves/")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
