"""Structure scanner for X4 savegames.

Purpose: find out what a save looks like inside before writing a parser.
Streams the gzip through lxml.iterparse and never holds the whole tree in
memory, because a full X4 save does not fit as an etree on a typical machine.

Three modes:
  census  counts element paths up to a given depth and collects the attribute
          names seen on each path.
  dump    prints the first N elements on a specific path, with attributes.
  find    searches for elements by attribute value, e.g. owner=player.

Examples:
  python explore_save.py census "<save>.xml.gz" --depth 4
  python explore_save.py dump   "<save>.xml.gz" --path savegame/universe --limit 5
  python explore_save.py find   "<save>.xml.gz" --attr owner --value player
"""

from __future__ import annotations

import argparse
import gzip
import sys
from collections import Counter, defaultdict

from lxml import etree

# Depth at which finished subtrees are released. Anything deeper is only freed
# once its ancestor at this level finishes; low enough keeps memory flat, too
# low makes the pruning itself expensive.
CLEAR_DEPTH = 4


def _events(path: str):
    """Stream (event, element) from an .xml.gz or plain .xml save."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        # huge_tree: X4 saves exceed libxml2's default limits.
        yield from etree.iterparse(fh, events=("start", "end"), huge_tree=True)


def _prune(elem, depth: int) -> None:
    """Release a finished subtree, including siblings already processed."""
    if depth != CLEAR_DEPTH:
        return
    elem.clear()
    parent = elem.getparent()
    if parent is not None:
        while len(parent) > 1:
            del parent[0]


def census(path: str, max_depth: int, top: int) -> None:
    counts: Counter[str] = Counter()
    attrs: dict[str, Counter[str]] = defaultdict(Counter)
    stack: list[str] = []
    total = 0

    for event, elem in _events(path):
        if event == "start":
            stack.append(elem.tag)
            total += 1
            if len(stack) <= max_depth:
                key = "/".join(stack)
                counts[key] += 1
                for name in elem.keys():
                    attrs[key][name] += 1
        else:
            depth = len(stack)
            stack.pop()
            _prune(elem, depth)

    print(f"elements total: {total:,}")
    print(f"unique paths up to depth {max_depth}: {len(counts):,}\n")

    for key, count in counts.most_common(top):
        names = ", ".join(name for name, _ in attrs[key].most_common(12))
        print(f"{count:>10,}  {key}")
        if names:
            print(f"{'':>12}attrs: {names}")


def dump(path: str, target: str, limit: int) -> None:
    """Print attributes of the first `limit` elements on path `target`."""
    wanted = target.strip("/").split("/")
    stack: list[str] = []
    seen = 0

    for event, elem in _events(path):
        if event == "start":
            stack.append(elem.tag)
            if stack == wanted:
                seen += 1
                print(f"--- {target} #{seen}")
                for name, value in elem.items():
                    shown = value if len(value) <= 200 else value[:200] + "..."
                    print(f"    {name} = {shown}")
                if seen >= limit:
                    return
        else:
            depth = len(stack)
            stack.pop()
            _prune(elem, depth)

    if seen == 0:
        print(f"no elements found on path: {target}", file=sys.stderr)


def find(path: str, attr: str, value: str, limit: int, max_depth: int) -> None:
    """Search for elements with a specific attribute value, e.g. owner=player.

    Prints the full element path, which makes it obvious where in the tree the
    player's property hangs. Also shows a count per path.
    """
    stack: list[str] = []
    per_path: Counter[str] = Counter()
    shown = 0

    for event, elem in _events(path):
        if event == "start":
            stack.append(elem.tag)
            if elem.get(attr) == value:
                key = "/".join(stack[:max_depth]) if max_depth else "/".join(stack)
                per_path[key] += 1
                if shown < limit:
                    shown += 1
                    print(f"--- {'/'.join(stack)}")
                    for name, val in elem.items():
                        text = val if len(val) <= 160 else val[:160] + "..."
                        print(f"    {name} = {text}")
        else:
            depth = len(stack)
            stack.pop()
            _prune(elem, depth)

    print(f"\nhits per path ({attr}={value}):")
    for key, count in per_path.most_common(40):
        print(f"{count:>8,}  {key}")


def main() -> int:
    # The Windows console runs on cp1252; game names are UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    c = sub.add_parser("census", help="count element paths and attribute names")
    c.add_argument("save")
    c.add_argument("--depth", type=int, default=4)
    c.add_argument("--top", type=int, default=60)

    d = sub.add_parser("dump", help="print elements on a specific path")
    d.add_argument("save")
    d.add_argument("--path", required=True)
    d.add_argument("--limit", type=int, default=5)

    f = sub.add_parser("find", help="search elements by attribute value")
    f.add_argument("save")
    f.add_argument("--attr", default="owner")
    f.add_argument("--value", default="player")
    f.add_argument("--limit", type=int, default=10)
    f.add_argument("--path-depth", type=int, default=0,
                   help="truncate paths at this depth in the tally (0 = full)")

    args = parser.parse_args()
    if args.mode == "census":
        census(args.save, args.depth, args.top)
    elif args.mode == "dump":
        dump(args.save, args.path, args.limit)
    else:
        find(args.save, args.attr, args.value, args.limit, args.path_depth)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
