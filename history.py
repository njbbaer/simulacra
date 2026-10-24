import argparse
import os
import re
import sys
from collections import Counter

from src.history import KINDS, LAYERS, History, Scope, render_conversation, render_turn

CHARACTERS_DIR = "~/simulacra-sync/characters"


def search(history: History, args: argparse.Namespace) -> tuple[list[str], bool]:
    """Return the output lines and whether anything matched."""
    results = history.search(
        args.pattern,
        [Scope.parse(scope) for scope in args.scopes],
        layer=args.layer,
        kind=args.kind,
        since=args.since,
        ignore_case=args.ignore_case,
    )
    if not args.count:
        hits = [
            f"{log.id}:{index}  {line}"
            for log, index, lines in results
            for line in lines
        ]
        return hits[-args.last :] if args.last else hits, bool(hits)
    matched: Counter[str] = Counter()
    searched: Counter[str] = Counter()
    for log, _, lines in results:
        searched[log.id] += 1
        matched[log.id] += bool(lines)
    rows = [(log_id, f"{matched[log_id]}/{n}") for log_id, n in searched.items()]
    rows = [row for row in rows if matched[row[0]]]
    total = f"{sum(matched.values())}/{sum(searched.values())}"
    rows.append(("total", f"{total} in {len(rows)} of {len(searched)} conversations"))
    width = max(len(log_id) for log_id, _ in rows)
    lines = [f"{log_id:<{width}}  {count}" for log_id, count in rows]
    return lines, any(matched.values())


def show(history: History, args: argparse.Namespace) -> tuple[list[str], bool]:
    scope = Scope.parse(args.id)
    log = history.log(scope)
    if scope.index is None:
        return [render_conversation(log)], True
    return [render_turn(log, scope.index, args.context)], True


def main() -> None:
    parser = argparse.ArgumentParser(description="Search and read conversation logs")
    parser.add_argument(
        "--characters", default=CHARACTERS_DIR, help="Characters directory"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    layers = "\n".join(f"  {name:<11} {about}" for name, about in LAYERS.items())
    search_parser = commands.add_parser(
        "search",
        help="Print matching lines under message IDs",
        description="Print matching lines under message IDs, exiting 1 if none.",
        epilog=f"layers:\n{layers}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    search_parser.add_argument("pattern", help="Regex, or '' to print the whole layer")
    search_parser.add_argument(
        "scopes", nargs="*", help="Characters, conversations, or messages"
    )
    search_parser.add_argument("--in", dest="layer", choices=LAYERS, default="text")
    search_parser.add_argument("--role", dest="kind", choices=KINDS)
    search_parser.add_argument(
        "--since", type=int, default=0, help="First conversation number"
    )
    search_parser.add_argument("--last", type=int, help="Keep only the last N lines")
    search_parser.add_argument("-i", "--ignore-case", action="store_true")
    search_parser.add_argument(
        "--count",
        action="store_true",
        help="Print matching/searched messages per conversation with a match",
    )

    show_parser = commands.add_parser(
        "show", help="Print a conversation, or one message in full"
    )
    show_parser.add_argument(
        "id", help="Character (latest conversation), conversation, or message"
    )
    show_parser.add_argument(
        "-C", "--context", type=int, default=1, help="Messages on each side"
    )

    args = parser.parse_args()
    history = History(os.path.expanduser(args.characters))
    try:
        lines, found = (search if args.command == "search" else show)(history, args)
    except (ValueError, re.error) as error:
        parser.exit(2, f"{error}\n")
    try:
        if lines:
            print("\n".join(lines))
    except BrokenPipeError:
        sys.stdout = None
    sys.exit(0 if found else 1)


if __name__ == "__main__":
    main()
