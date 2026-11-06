"""Checks over one cycle's commands before they go out (tasks/plan-2026-11.md, 0.1).

Each of these went out unseen once: at start9k's first cycle the guard of 30 was
assigned home in one go, its leader no longer recognised; across start9f and start9g
ZXX-974 was asked for a pier four times while the first was still in its build; and
two rules gave the same ships orders in one cycle more than once (a station without a
raid calling the guard to itself, `fleet` and `fighter_posts` on one fighter). A check
names the thing; it does not stop it. `agent.cycle` adds the lines to its notes and
`dryrun.py` turns them into a refusal before a run starts.
"""

from collections import Counter, defaultdict

import executor
import sitrep

# Destroyers one cycle may send home or set free before it is worth a look.
MASS = 5
# Settings, not orders: several rules may set them on one ship (agent.SETTINGS).
SETTINGS = frozenset({"tradeware", "limit", "sellware", "shiprespond", "respond", "turrets", "resupply",
                      "traderule", "autotrade", "ledger", "price", "avoid", "buildmethod"})


def check(state: dict, commands: list[str], by_rule: list[tuple[str, list[str]]]) -> list[str]:
    """`INVARIANT:` lines for what in `commands` looks like a known mistake. `by_rule` is
    `standing.LAST_BY_RULE`: which standing rule gave which command; the rest is "other"."""
    ships = {a["code"]: a for a in state.get("assets", [])
             if (a.get("cls") or "").startswith("ship") and a.get("code")}
    out = []

    # One ship, orders from two places.
    source = {}
    for rule, given in by_rule:
        for command in given:
            source.setdefault(command, rule)
    givers = defaultdict(set)
    for command in commands:
        words = command.split()
        if len(words) > 1 and words[0] not in SETTINGS and words[1] in ships:
            givers[words[1]].add(source.get(command, "other"))
    for code, rules in sorted(givers.items()):
        if len(rules) > 1:
            out.append(f"INVARIANT: {code} has orders from {', '.join(sorted(rules))} in one cycle")

    # Many destroyers sent home or set free at once.
    recalled = [c.split()[1] for c in commands
                if (c.startswith("release ") or (c.startswith("assign ") and c.endswith(" defend")))
                and sitrep.ship_type((ships.get(c.split()[1]) or {}).get("macro")) == "destroyer"]
    recalled = list(dict.fromkeys(recalled))
    if len(recalled) > MASS:
        out.append(f"INVARIANT: {len(recalled)} destroyers sent home or released in one cycle "
                   f"({', '.join(recalled[:6])}, ...)")

    # A module asked for while a build of the station already has it.
    stands = {a["code"]: Counter(a.get("modules") or []) for a in state.get("assets", [])
              if a.get("cls") == "station" and a.get("code")}
    building = defaultdict(Counter)
    for bs in state.get("assets", []):
        if bs.get("cls") == "buildstorage" and bs.get("station"):
            build = bs.get("build") or {}
            for seq in list(build.get("queue") or []) + [r.get("sequence") or [] for r in build.get("running") or []]:
                building[bs["station"]] |= Counter(seq)
    for command in commands:
        words = command.split()
        if words[0] != "expand" or len(words) < 3 or words[1] not in stands:
            continue
        module = (executor.EXPANSION_MODULES.get(words[2]) or (None,))[0]
        if module and building[words[1]][module] > stands[words[1]][module]:
            out.append(f"INVARIANT: {command} while a build of {words[1]} has {module} in it already")
    return out
