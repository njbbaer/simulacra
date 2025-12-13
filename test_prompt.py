import argparse
import asyncio

from src.simulacrum import Simulacrum


def main() -> None:
    args = _parse_args()
    simulacrum = Simulacrum(args.context_file)
    response = asyncio.run(simulacrum.test_prompt(args.prompt_name))
    print(response)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a test prompt for a character")
    parser.add_argument("context_file", type=str, help="Path to context YAML")
    parser.add_argument("prompt_name", type=str, help="Name of test prompt")
    return parser.parse_args()


if __name__ == "__main__":
    main()
