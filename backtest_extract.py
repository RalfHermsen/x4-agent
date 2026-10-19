"""Backtest of the translation step on stored reasoning, without the game.

The planner works in two calls: call 1 reasons and ends in a numbered ACTIONS
list, call 2 copies that list into the schema. Call 2 is where proposals got
lost: placeholder codes in the log review (`MINER`, `N/A`), and on 2026-10-18 a
cycle whose four clear actions came back as none at all. This replays stored
call-1 texts through up to three translators and counts what each makes of
them:

    local   call 2 as the agent runs it: planner.extract on the local model
    hosted  the same call on a hosted model (`openai:<alias>`, X4_OPENAI_URL
            and X4_OPENAI_KEY in the environment)
    parser  no model: fills the simple action types from the words of a line,
            and only with codes that appear in that cycle's situation report,
            so an invented code cannot come out of it

Inputs are every stored pair of situation report and reasoning: the files in
out/cmp-*/ and the model cycles in out/experiments/*/agent.log. Nothing is
sent to the game.

Usage:
    python backtest_extract.py --translators parser
    python backtest_extract.py --translators hosted,parser --repeat 2
    python backtest_extract.py --translators local,hosted,parser --repeat 2

Results go to out/backtest-extract/<stamp>/: results.json (every input and
every answer) and summary.md.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent
CODE = re.compile(r"\b[A-Z]{3}-\d{3}\b")
LEVELS = {"low": "low", "mid": "mid", "medium": "mid", "high": "high"}
ROLES = {"trade": "trade", "trader": "trade", "trading": "trade",
         "mine": "mine", "miner": "mine", "mining": "mine",
         "defend": "defend", "defence": "defend", "defense": "defend",
         "buildstorage": "buildstorage"}
# Fields that must hold a code from the report. A word there (MINER, N/A,
# other) is the placeholder failure the log review counted.
REF_FIELDS = ("ship_ref", "station_id", "from_station", "to_station")
LOCAL_MODEL = "gemma4:26b-a4b-it-qat"
HOSTED_MODEL = "openai:gpt-4"


# ---------------------------------------------------------------- inputs

def _split_report(text: str) -> tuple[str, str] | None:
    """The situation report and the reasoning that follows it."""
    start, middle = text.find("# SITUATION"), text.find("# REASONING")
    if start < 0 or middle < start:
        return None
    return text[start:middle], text[middle + len("# REASONING"):]


def cmp_inputs() -> list[dict]:
    """The model comparison files: report, reasoning, then call 2's advice."""
    out = []
    for path in sorted(REPO.glob("out/cmp-*/*.txt")):
        parts = _split_report(path.read_text(encoding="utf-8", errors="replace"))
        if not parts:
            continue
        report, rest = parts
        out.append({"source": f"{path.parent.name}/{path.name}", "report": report,
                    "analysis": rest.split("# ADVICE")[0].strip()})
    return out


def log_inputs() -> list[dict]:
    """Every cycle in the experiment logs where the model ran.

    A cycle is a block between two lines of `=`; it holds the report, then
    `# REASONING` with call 1's text, then `# CYCLE` with what came of it. A
    quiet cycle has no reasoning and is skipped, and so is a block still being
    written.
    """
    out = []
    for path in sorted(REPO.glob("out/experiments/*/agent.log")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for block in re.split(r"^={20,}$", text, flags=re.M):
            parts = _split_report(block)
            if not parts or "# CYCLE" not in parts[1]:
                continue
            report, rest = parts
            out.append({"source": path.parent.name, "report": report,
                        "analysis": rest.split("# CYCLE")[0].strip()})
    return out


def collect() -> list[dict]:
    seen, inputs = set(), []
    for item in cmp_inputs() + log_inputs():
        if item["analysis"] in seen:
            continue
        seen.add(item["analysis"])
        inputs.append(item)
    return inputs


# ---------------------------------------------------------------- the parser

def numbered_lines(analysis: str) -> list[str]:
    """The numbered lines under ACTIONS, as planner._decisions finds them."""
    _, found, tail = analysis.partition("ACTIONS")
    if not found:
        return []
    for marker in ("STANDING GOALS", "GOALS"):
        tail = tail.split(marker)[0]
    return [line for line in tail.splitlines() if re.match(r"^\s*\d+[.)]\s", line)]


def vocabulary(report: str) -> tuple[set[str], set[str], set[str]]:
    """Our stations, our ships, and every code the report mentions.

    Stations are the lines under OWN STATIONS that start with a code. Ships
    are the lines under FLEET that start with one; above the sitrep's detail
    limit the fleet is listed by role, and then only its `examples:` lines and
    the ATTENTION lines that start with a code (idle ships, failing ships)
    name ships. A ship the report does not name is unknown here, and actions
    for it are left to a model, which is the safe side.
    """
    own, ships, section = set(), set(), ""
    attention = []
    for line in report.splitlines():
        if line.startswith("# "):
            section = line
            continue
        start = re.match(r"([A-Z]{3}-\d{3})\b", line)
        if section.startswith("# OWN STATIONS") and start:
            own.add(start.group(1))
        elif section.startswith("# FLEET"):
            if start:
                ships.add(start.group(1))
            elif "examples:" in line:
                ships.update(CODE.findall(line))
        elif section.startswith("# ATTENTION") and start:
            attention.append(start.group(1))
    ships.update(code for code in attention if code not in own)
    return own, ships, set(CODE.findall(report))


def _clean(line: str) -> str:
    """Drop the number, markup and the justification after the action."""
    line = re.sub(r"^\s*\d+[.)]\s*", "", line).replace("`", "").replace("*", "")
    for cut in (" (", " [", " Guideline", " guideline"):
        if cut in line:
            line = line[:line.index(cut)]
    return line.strip()


def _tokens(text: str, wares: set[str]) -> list[str]:
    """Words and numbers in order; two words that make a ware id become one."""
    raw = re.findall(r"[a-z]+|\d[\d,]*(?:\.\d+)?", text.lower())
    out, i = [], 0
    while i < len(raw):
        pair = raw[i] + raw[i + 1] if i + 1 < len(raw) else ""
        if pair in wares and raw[i].isalpha() and raw[i + 1].isalpha():
            out.append(pair)
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return out


def _prices(tokens: list[str], wares: set[str]) -> list[tuple[str, float]]:
    """Each ware with the number that follows it, or nothing if any is unclear.

    "microchips to 1198, refinedmetals to 204" is two prices. A number with
    no ware before it, a ware without a number, or a second number after a
    ware ("73, up from 54") makes the whole line a reading, not a parse.
    """
    pairs, pending = [], None
    for token in tokens:
        if token in wares:
            if pending:
                return []
            pending = token
        elif token[0].isdigit():
            if not pending:
                return []
            pairs.append((pending, float(token.replace(",", ""))))
            pending = None
    return [] if pending else pairs


def parse_line(line: str, own: set[str], ships: set[str], wares: set[str]) -> list[dict]:
    """One numbered line to its actions, or [] when it is not certain.

    Only the simple types, and only when every slot is filled unambiguously:
    one of our stations and each ware with its own number for prices; a level
    word for a budget (an amount is a judgement about levels, left to the
    model); our ships and no station for a behaviour; our ships, one station
    and one role word for an assignment. Anything else is [] and would go to
    a model.
    """
    text = _clean(line)
    low = text.lower()
    found = list(dict.fromkeys(CODE.findall(text)))
    stations = [c for c in found if c in own]
    fleet = [c for c in found if c in ships]
    if len(found) != len(stations) + len(fleet):
        return []  # a code that is not ours: not a simple action
    tokens = _tokens(CODE.sub(" ", text), wares)
    words = set(tokens)

    if "price" in words and len(stations) == 1 and not fleet:
        side = "buy" if "buy" in words and "sell" not in words else "sell"
        return [{"type": "set_price", "station_id": stations[0], "ware": ware,
                 "side": side, "price": price} for ware, price in _prices(tokens, wares)]
    if "budget" in words and len(stations) == 1 and not fleet:
        levels = {LEVELS[w] for w in words if w in LEVELS}
        if len(levels) == 1:
            return [{"type": "set_budget", "station_id": stations[0], "level": levels.pop()}]
        return []
    if fleet and not stations:
        behaviour = ("explore" if words & {"explore", "exploring"} else
                     "autotrade" if "autotrade" in words or "auto trade" in low
                     or "auto-trade" in low else
                     "automine" if "automine" in words or "auto mine" in low
                     or "auto-mine" in low else None)
        if behaviour:
            return [{"type": "set_behaviour", "ship_ref": ship, "behaviour": behaviour}
                    for ship in fleet]
    if "assign" in words and fleet and len(stations) == 1:
        roles = {ROLES[w] for w in words if w in ROLES}
        if "build storage" in low:
            roles.add("buildstorage")
        if len(roles) == 1:
            role = roles.pop()
            return [{"type": "assign_ship", "ship_ref": ship, "station_id": stations[0],
                     "role": role} for ship in fleet]
    return []


def parse_actions(analysis: str, report: str, wares: set[str]) -> list[list[dict]]:
    """One entry per numbered line: its actions, or [] where it is unsure."""
    own, ships, _ = vocabulary(report)
    return [parse_line(line, own, ships, wares) for line in numbered_lines(analysis)]


# ---------------------------------------------------------------- the model calls

def _plain(action) -> dict:
    data = action.model_dump(exclude={"priority", "rationale"})
    return {k: v for k, v in data.items() if v not in (None, [], "")}


class DailyLimit(Exception):
    """The provider's tokens-per-day budget is spent: stop asking."""


def run_model(item: dict, model: str, retries: int = 2) -> dict:
    """One call 2 on one input. A rate limit per minute is waited out; a limit
    per day ends the run for that model, because every further call fails too
    and the key may be shared: the first full run spent a shared hosted key's
    whole daily budget (200,000 tokens on the free tier) retrying."""
    import httpx
    import planner
    for attempt in range(retries + 1):
        try:
            plan, seconds = planner.extract(item["analysis"], item["report"], model)
            return {"actions": [_plain(a) for a in plan.actions], "seconds": round(seconds, 2)}
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:600]
            if exc.response.status_code == 429 and ("per day" in body or "TPD" in body):
                raise DailyLimit(body) from exc
            if exc.response.status_code == 429 and attempt < retries:
                time.sleep(30 * (attempt + 1))
                continue
            return {"error": f"HTTP {exc.response.status_code}"}
        except Exception as exc:  # noqa: BLE001 - every failure is a result here
            return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return {"error": "rate limited"}


# ---------------------------------------------------------------- scoring

def invented(action: dict, codes: set[str]) -> list[str]:
    bad = []
    for field in REF_FIELDS:
        value = action.get(field)
        if value in (None, ""):
            continue
        if not (CODE.fullmatch(str(value)) and value in codes):
            bad.append(f"{field}={value}")
    return bad


def _same_price(a: dict, b: dict) -> bool:
    return (a.get("type") == b.get("type") == "set_price"
            and a.get("station_id") == b.get("station_id") and a.get("ware") == b.get("ware")
            and a.get("side") == b.get("side")
            and abs(float(a.get("price") or 0) - float(b.get("price") or 0)) < 0.5)


def summarise(results: list[dict], translators: list[str]) -> str:
    rows = ["| | " + " | ".join(translators) + " |",
            "|---|" + "---|" * len(translators)]

    def row(label, values):
        rows.append(f"| {label} | " + " | ".join(str(v) for v in values) + " |")

    stats = {}
    for name in translators:
        runs = [r["answers"].get(name, []) for r in results]
        if not any(runs):
            continue
        first = [run[0] for run in runs if run]
        ok = [a for a in first if "actions" in a]
        lines = sum(len(r["lines"]) for r, run in zip(results, runs) if run and "actions" in run[0])
        actions = sum(len(a["actions"]) for a in ok)
        empty = sum(1 for r, run in zip(results, runs)
                    if run and "actions" in run[0] and r["lines"] and not run[0]["actions"])
        unmatched = sum(max(0, len(r["lines"]) - len(run[0]["actions"]))
                        for r, run in zip(results, runs) if run and "actions" in run[0])
        bad = sum(len(invented(a, r["codes"])) for r, run in zip(results, runs)
                  if run and "actions" in run[0] for a in run[0]["actions"])
        seconds = [a["seconds"] for a in ok if "seconds" in a]
        repeat = [run for run in runs if len(run) > 1 and all("actions" in x for x in run)]
        same = sum(1 for run in repeat
                   if all(sorted(map(json.dumps, x["actions"])) == sorted(map(json.dumps, run[0]["actions"]))
                          for x in run[1:]))
        stats[name] = {
            "inputs answered": f"{len(ok)} of {len(results)}",
            "numbered lines": lines,
            "actions out": actions,
            "answers with lines but no action": empty,
            "lines without an action": unmatched,
            "invented references": bad,
            "identical on repeat": f"{same} of {len(repeat)}" if repeat else "n/a",
            "median seconds per call": f"{statistics.median(seconds):.2f}" if seconds else "n/a",
            "errors": len(first) - len(ok),
        }
    translators = [t for t in translators if t in stats]
    rows[0] = "| | " + " | ".join(translators) + " |"
    rows[1] = "|---|" + "---|" * len(translators)
    for label in next(iter(stats.values())):
        row(label, [stats[t][label] for t in translators])

    if "parser" in translators:
        # How often a model agrees with a price the parser read off the line.
        for name in (t for t in translators if t != "parser"):
            hits = total = 0
            for r in results:
                parsed = [a for a in (r["answers"]["parser"][0]["actions"]) if a["type"] == "set_price"]
                model = (r["answers"].get(name) or [{}])[0].get("actions")
                if model is None:
                    continue
                total += len(parsed)
                hits += sum(1 for p in parsed if any(_same_price(p, m) for m in model))
            row(f"parser prices also given by {name}", [f"{hits} of {total}"] + [""] * (len(translators) - 1))
    return "\n".join(rows)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--translators", default="parser",
                        help="comma-separated: local, hosted, parser")
    parser.add_argument("--repeat", type=int, default=1, help="runs per model translator")
    parser.add_argument("--gap", type=float, default=3.0, help="seconds between hosted calls")
    parser.add_argument("--limit", type=int, default=0, help="only the first N inputs")
    args = parser.parse_args()
    translators = [t.strip() for t in args.translators.split(",") if t.strip()]
    if os.environ.get("X4_EXTRACT_MODEL"):
        parser.error("unset X4_EXTRACT_MODEL: it overrides the model under test")

    import gamedata
    wares = set(gamedata.wares())
    inputs = collect()
    if args.limit:
        inputs = inputs[:args.limit]
    out_dir = REPO / "out" / "backtest-extract" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{len(inputs)} inputs, translators {translators}, results in {out_dir}", flush=True)

    results = []
    stopped: set[str] = set()

    def write(final: bool) -> None:
        # After every input, so a run cut short still leaves what it measured.
        for r in results:
            r["codes"] = set(r["codes"])
        summary = summarise(results, translators) if results else ""
        for r in results:
            r["codes"] = sorted(r["codes"])
        (out_dir / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        note = "" if final else "\n(partial)"
        if stopped:
            note += f"\nstopped at a daily limit: {', '.join(sorted(stopped))}"
        (out_dir / "summary.md").write_text(summary + note + "\n", encoding="utf-8")
        if final:
            print("\n" + summary + note)

    for number, item in enumerate(inputs, 1):
        own, ships, codes = vocabulary(item["report"])
        lines = numbered_lines(item["analysis"])
        answers = {}
        if "parser" in translators:
            start = time.perf_counter()
            parsed = parse_actions(item["analysis"], item["report"], wares)
            answers["parser"] = [{"actions": [a for actions in parsed for a in actions],
                                  "unparsed": [l for l, a in zip(lines, parsed) if not a],
                                  "seconds": round(time.perf_counter() - start, 4)}]
        for name, model in (("local", LOCAL_MODEL), ("hosted", HOSTED_MODEL)):
            if name not in translators or name in stopped:
                continue
            runs = []
            try:
                for _ in range(args.repeat):
                    runs.append(run_model(item, model))
                    if name == "hosted":
                        time.sleep(args.gap)
            except DailyLimit as exc:
                stopped.add(name)
                print(f"{name}: daily limit reached, no more calls: {str(exc)[:160]}", flush=True)
            if runs:
                answers[name] = runs
        results.append({"source": item["source"], "lines": lines, "codes": sorted(codes),
                        "analysis": item["analysis"], "answers": answers})
        brief = ", ".join(f"{n}: {len(a[0].get('actions', []))}" if "actions" in a[0]
                          else f"{n}: {a[0].get('error')}" for n, a in answers.items())
        print(f"[{number}/{len(inputs)}] {item['source']}: {len(lines)} lines; {brief}", flush=True)
        write(final=False)

    write(final=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
