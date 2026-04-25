import argparse
import asyncio
import sys

import dotenv

from src.simulacrum import Simulacrum
from src.utilities import parse_value

dotenv.load_dotenv()


def _parse_overrides(items: list[str]) -> dict:
    overrides: dict = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            raise argparse.ArgumentTypeError(f"Expected key=value: {item!r}")
        target = overrides
        *parents, leaf = key.split(".")
        for part in parents:
            target = target.setdefault(part, {})
        target[leaf] = parse_value(value)
    return overrides


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Get a single response from a character"
    )
    parser.add_argument("context_file", help="Path to the context YAML file")
    parser.add_argument(
        "prompt", nargs="?", help="User prompt (reads stdin if omitted)"
    )
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override a context value (dotted keys for nesting). Repeatable.",
    )
    args = parser.parse_args()

    prompt = args.prompt or sys.stdin.read().strip()
    if not prompt:
        parser.error("No prompt provided")

    overrides = _parse_overrides(args.overrides)
    sim = Simulacrum(args.context_file, ephemeral=True, overrides=overrides)
    response = asyncio.run(sim.chat(prompt, None, None))
    print(response)


if __name__ == "__main__":
    main()
