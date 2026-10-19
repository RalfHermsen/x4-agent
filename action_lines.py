"""Read the reasoning's numbered actions without a model, where that is certain.

The planner's call 1 ends in a numbered ACTIONS list; call 2 used to copy all
of it into the schema, and that copy was where proposals got lost: placeholder
codes, sell prices turned into buy prices, cycles whose every action came back
as none (docs/contracts.md, "The translation step, replayed"). Most lines are
simple enough to read directly. This module reads those and only those:

* only the simple types (price, budget level, behaviour, assignment);
* only with codes that appear in that cycle's situation report, so an
  invented code cannot come out of it;
* only when every slot is filled unambiguously. Anything else is left for
  call 2, which then sees just the lines read here could not.

`planner.translate` puts this in front of call 2; `backtest_extract.py` runs it
against the stored cycles.
"""

from __future__ import annotations

import re

CODE = re.compile(r"\b[A-Z]{3}-\d{3}\b")
LEVELS = {"low": "low", "mid": "mid", "medium": "mid", "high": "high"}
ROLES = {"trade": "trade", "trader": "trade", "trading": "trade",
         "mine": "mine", "miner": "mine", "mining": "mine",
         "defend": "defend", "defence": "defend", "defense": "defend",
         "buildstorage": "buildstorage"}
ACTIONS_HEADING = "ACTIONS"
GOAL_MARKERS = ("STANDING GOALS", "GOALS")


def actions_section(analysis: str) -> str | None:
    """The text under ACTIONS up to the goals, or None without the heading."""
    _, found, tail = analysis.partition(ACTIONS_HEADING)
    if not found:
        return None
    for marker in GOAL_MARKERS:
        tail = tail.split(marker)[0]
    return tail


def numbered_lines(analysis: str) -> list[str]:
    """The numbered lines under ACTIONS, as planner._decisions finds them."""
    section = actions_section(analysis)
    if section is None:
        return []
    return [line for line in section.splitlines() if re.match(r"^\s*\d+[.)]\s", line)]


def says_none(analysis: str) -> bool:
    """ACTIONS is there and holds nothing, or says none."""
    section = actions_section(analysis)
    if section is None:
        return False
    text = re.sub(r"[\s:*.\-`]", "", section).lower()
    return text in ("", "none", "nothing")


def goals_from(analysis: str) -> list[str]:
    """The standing goals the reasoning ends with, as plain lines.

    Call 2 used to copy these too. When every action line is read here, call
    2 does not run, and the goals must still reach the next cycle.
    """
    for marker in GOAL_MARKERS:
        if marker in analysis:
            tail = analysis.split(marker, 1)[1]
            goals = []
            for line in tail.splitlines():
                text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip(" *`:")
                if text:
                    goals.append(text)
            return goals[:3]
    return []


def summary_from(analysis: str, limit: int = 300) -> str:
    """The reasoning's first paragraph, for the log where call 2's assessment was."""
    head = analysis.split(ACTIONS_HEADING, 1)[0].strip()
    first = next((p.strip() for p in re.split(r"\n\s*\n", head) if p.strip()), "")
    return first[:limit]


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
    one of our stations and each ware with its own number for prices (a price
    that names no side is a sell price: call 2 made 87 of them buy prices);
    a level word for a budget (an amount is a judgement about levels, left to
    the model); our ships and no station for a behaviour; our ships, one
    station and one role word for an assignment. Anything else is [] and goes
    to a model.
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
