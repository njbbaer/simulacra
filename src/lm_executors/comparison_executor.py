import asyncio
import random
from typing import Any, Dict

from ..chat_completion import ChatCompletion
from ..response_scaffold import ResponseScaffold
from .chat_executor import ChatExecutor


class ComparisonExecutor(ChatExecutor):
    VARIATIONS = {
        "sonnet-4": {"model": "anthropic/claude-sonnet-4"},
        "sonnet-3.7": {"model": "anthropic/claude-3.7-sonnet"},
    }

    def __init__(self, context) -> None:
        super().__init__(context)

    async def execute(self, params: Dict[str, Any] | None = None) -> ChatCompletion:
        tasks = []
        variation_names = list(self.VARIATIONS.keys())
        random.shuffle(variation_names)

        for name in variation_names:
            variation = self.VARIATIONS[name]
            variation_params = {**params, **variation} if params else variation
            tasks.append(super().execute(variation_params))

        print("Generating variations...")
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            scaffold = ResponseScaffold(result.content, self.context.response_scaffold)
            print(f"\n---------- (#{i+1}) ----------")
            print(scaffold.extract_output())

        choice = int(input("\nSelect response (1-" + str(len(results)) + "): ")) - 1

        with open("comparison_log.txt", "a") as f:
            f.write(f"{variation_names[choice]}\n")

        return results[choice]
