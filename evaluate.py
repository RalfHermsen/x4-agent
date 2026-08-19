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

import planner
import sitrep as sitrep_mod
from save_parser import SHIP_CLASSES, documents_dir, parse_save


def all_saves() -> list[Path]:
    root = documents_dir() / "Egosoft" / "X4"
    return sorted(root.glob("*/save/*.xml.gz"), key=lambda p: p.stat().st_mtime)


def evaluate(save: Path, model: str, guidelines: str, out_dir: Path | None) -> dict:
    row: dict = {"save": save.name}
    start = time.perf_counter()

    state = parse_save(save)
    row["version"] = state["meta"].get("version")
    row["credits"] = state["player"].get("money") or 0
    row["ships"] = len([a for a in state["assets"] if a["cls"] in SHIP_CLASSES])
    row["parse_s"] = time.perf_counter() - start

    report = sitrep_mod.build(state)
    row["sitrep_b"] = len(report.encode("utf-8"))

    analysis, reason_s = planner.reason(report, guidelines, model)
    plan, extract_s = planner.extract(analysis, report, model)
    ok, rejected = planner.check_actions(plan, state)

    row["llm_s"] = reason_s + extract_s
    row["actions"] = len(ok)
    row["rejected"] = len(rejected)
    row["types"] = ",".join(sorted({a.type for a in ok})) or "-"

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        text = (f"### {save.name}\n\n{report}\n\n# REASONING\n{analysis}\n\n"
                + planner.render(plan, ok, rejected, model, (reason_s, extract_s)))
        (out_dir / f"{save.stem}.txt").write_text(text, encoding="utf-8")
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
              f"{'sitrep':>9}{'parse':>8}{'llm':>8}{'actions':>9}{'rej.':>6}  types")
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
              f"{row['actions']:>9}{row['rejected']:>6}  {row['types']}")

    if rows:
        print("-" * len(header))
        total_actions = sum(r["actions"] for r in rows)
        total_rejected = sum(r["rejected"] for r in rows)
        share = total_rejected / max(total_actions + total_rejected, 1) * 100
        print(f"{len(rows)}/{len(saves)} saves processed. "
              f"{total_actions} actions, {total_rejected} rejected ({share:.0f}%). "
              f"Largest sitrep: {max(r['sitrep_b'] for r in rows):,} bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
