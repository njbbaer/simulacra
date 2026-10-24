import argparse
import os
import re
import sys
from collections import Counter

from src.history import KINDS, LAYERS, History, Scope, render_conversation, render_turn

CHARACTERS_DIR = "~/simulacra-sync/characters"


def search(history: History, args: argparse.Namespace) -> list[str]:
    results = history.search(
        args.pattern,
        [Scope.parse(scope) for scope in args.scopes],
        layer=args.layer,
        kind=args.kind,
        since=args.since,
        ignore_case=args.ignore_case,
    )
    if not args.count:
        return [
            f"{log.id}:{index}  {line}"
            for log, index, lines in results
            for line in lines
        ]
    matched: Counter[str] = Counter()
    searched: Counter[str] = Counter()
    for log, _, lines in results:
        searched[log.id] += 1
        matched[log.id] += bool(lines)
    width = max((len(log_id) for log_id in searched), default=0)
    return [
        f"{log_id:<{width}}  {matched[log_id]}/{n}" for log_id, n in searched.items()
    ]


def show(history: History, args: argparse.Namespace) -> list[str]:
    scope = Scope.parse(args.id)
    log = history.log(scope)
    if scope.index is None:
        return [render_conversation(log)]
    return [render_turn(log, scope.index, args.context)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search and read conversation logs")
    parser.add_argument(
        "--characters", default=CHARACTERS_DIR, help="Characters directory"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    search_parser = commands.add_parser(
        "search", help="Print matching lines under message IDs"
    )
    search_parser.add_argument(
        "pattern",
        nargs="?",
        help="Regex; omit to print the whole layer. A first argument naming a "
        "character, conversation, or message is taken as a scope instead.",
    )
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
        help="Print matching/searched messages per conversation",
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
    if args.command == "search" and args.pattern and _is_scope(history, args.pattern):
        args.scopes.insert(0, args.pattern)
        args.pattern = None
    try:
        lines = (search if args.command == "search" else show)(history, args)
    except (ValueError, re.error) as error:
        parser.exit(1, f"{error}\n")
    if args.command == "search" and args.last:
        lines = lines[-args.last :]
    try:
        print("\n".join(lines))
    except BrokenPipeError:
        sys.stdout = None


def _is_scope(history: History, pattern: str) -> bool:
    try:
        return Scope.parse(pattern).character in history.characters()
    except ValueError:
        return False


if __name__ == "__main__":
    main()
