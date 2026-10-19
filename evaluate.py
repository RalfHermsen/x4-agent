"""Runs the full advice loop across multiple saves and summarises the outcome.

This is the definition of done for Phase 1: not "it works on my save", but "it
produces defensible recommendations across varied game states". A profile folder
that has been played for a while already contains that corpus, often spanning
several X4 versions and everything from a fresh start to a large empire.

Measured per save:
  - does it parse without intervention
  - how large does the sitrep get (token budget)
  - how many actions come out, and how many die on the semantic check
  - how long it takes

Usage:
    python evaluate.py
    python evaluate.py --limit 3 --out out/
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

import os

import action_lines
import catalog
import executor
import planner
import sitrep as sitrep_mod
from save_parser import SHIP_CLASSES, documents_dir, parse_save


def all_saves() -> list[Path]:
    """Every save the game itself would list.

    `edit_save.py` keeps the file it replaced as `*.replaced-<stamp>.xml.gz`.
    The game does list those (seen through its own save list), but they are
    near-duplicates of a neighbouring save and would count twice here.
    """
    root = documents_dir() / "Egosoft" / "X4"
    return sorted((p for p in root.glob("*/save/*.xml.gz")
                   if ".replaced-" not in p.name),
                  key=lambda p: p.stat().st_mtime)


def evaluate(save: Path, model: str, guidelines: str, out_dir: Path | None) -> dict:
    row: dict = {"save": save.name}
    start = time.perf_counter()

    state = parse_save(save)
    row["version"] = state["meta"].get("version")
    row["credits"] = state["player"].get("money") or 0
    row["ships"] = len([a for a in state["assets"] if a["cls"] in SHIP_CLASSES])
    row["parse_s"] = time.perf_counter() - start

    use_catalog = os.environ.get("X4_CATALOG") == "1"
    found = catalog.situations(state) if use_catalog else []
    report = sitrep_mod.build(state, situations=catalog.render(found))
    row["sitrep_b"] = len(report.encode("utf-8"))

    analysis, reason_s = planner.reason(report, guidelines, model, catalog=use_catalog)
    if use_catalog:
        commands, notes, counts = catalog.decide(found, analysis)
        row.update({"llm_s": reason_s, "lines": counts["situations"], "actions": counts["chosen"],
                    "rejected": counts["unreadable"], "skipped": 0,
                    "types": ",".join(sorted({c.split()[0] for c in commands})) or "-",
                    "catalog": counts})
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            text = (f"### {save.name}\n\n{report}\n\n# REASONING\n{analysis}\n\n# CHOSEN\n"
                    + "\n".join(f"    {c}" for c in commands) + "\n\n# NOTES\n" + "\n".join(notes)
                    + f"\n\n# COUNTS\n{counts}\n")
            (out_dir / f"{save.name.split(chr(46))[0]}.txt").write_text(text, encoding="utf-8")
        return row
    plan, extract_s = planner.translate(analysis, report, model)
    ok, rejected = planner.check_actions(plan, state)
    # The executor's gates are the last filter before the game, and in a live
    # run they swallowed more proposals than the semantic check did: a ship
    # that is already busy, a freighter assigned to mine. Those count too.
    _, skipped = executor.to_commands(ok, state)

    row["llm_s"] = reason_s + extract_s
    row["lines"] = len(action_lines.numbered_lines(analysis))
    row["actions"] = len(ok)
    row["rejected"] = len(rejected)
    row["skipped"] = len(skipped)
    row["types"] = ",".join(sorted({a.type for a in ok})) or "-"

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        text = (f"### {save.name}\n\n{report}\n\n# REASONING\n{analysis}\n\n"
                + planner.render(plan, ok, rejected, model, (reason_s, extract_s)))
        if skipped:
            text += "\n\n# SKIPPED (executor gates)\n" + "\n".join(
                f"    {action.type}: {why}" for action, why in skipped)
        (out_dir / f"{save.name.split(chr(46))[0]}.txt").write_text(text, encoding="utf-8")
    return row


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="only the N newest saves")
    parser.add_argument("--model", default=planner.DEFAULT_MODEL)
    parser.add_argument("--out", default="out", help="folder for the full advice")
    args = parser.parse_args()

    saves = all_saves()
    if args.limit:
        saves = saves[-args.limit:]
    guidelines = planner.GUIDELINES.read_text(encoding="utf-8")
    out_dir = Path(args.out) if args.out else None

    header = (f"{'save':<20}{'ver':>5}{'credits':>14}{'ships':>7}"
              f"{'sitrep':>9}{'parse':>8}{'llm':>8}{'lines':>7}{'actions':>9}{'rej.':>6}"
              f"{'skip':>6}  types")
    print(header)
    print("-" * len(header))

    rows = []
    for save in saves:
        try:
            row = evaluate(save, args.model, guidelines, out_dir)
        except Exception as exc:  # noqa: BLE001 - we want to see everything
            print(f"{save.name:<20}  FAILED: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=1)
            continue
        rows.append(row)
        print(f"{row['save']:<20}{row['version']:>5}{row['credits']:>14,}"
              f"{row['ships']:>7}{row['sitrep_b']:>9,}"
              f"{row['parse_s']:>7.1f}s{row['llm_s']:>7.1f}s"
              f"{row['lines']:>7}{row['actions']:>9}{row['rejected']:>6}{row['skipped']:>6}"
              f"  {row['types']}")

    if rows:
        print("-" * len(header))
        total_actions = sum(r["actions"] for r in rows)
        total_rejected = sum(r["rejected"] for r in rows)
        total_skipped = sum(r["skipped"] for r in rows)
        share = total_rejected / max(total_actions + total_rejected, 1) * 100
        print(f"{len(rows)}/{len(saves)} saves processed, cap {planner.MAX_ACTIONS}. "
              f"{sum(r['lines'] for r in rows)} lines proposed, "
              f"{total_actions} actions, {total_rejected} rejected ({share:.0f}%), "
              f"{total_skipped} of the actions skipped by the executor gates. "
              f"Largest sitrep: {max(r['sitrep_b'] for r in rows):,} bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
