import argparse
import asyncio
import sys

import dotenv

from src.simulacrum import Simulacrum

dotenv.load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Get a single response from a character"
    )
    parser.add_argument("context_file", help="Path to the context YAML file")
    parser.add_argument(
        "prompt", nargs="?", help="User prompt (reads stdin if omitted)"
    )
    args = parser.parse_args()

    prompt = args.prompt or sys.stdin.read().strip()
    if not prompt:
        parser.error("No prompt provided")

    sim = Simulacrum(args.context_file, ephemeral=True)
    response = asyncio.run(sim.chat(prompt, None, None))
    print(response)


if __name__ == "__main__":
    main()
