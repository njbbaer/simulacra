import asyncio
import copy
import random
from typing import Any

import aiofiles

from ..chat_completion import ChatCompletion
from ..response_scaffold import ResponseScaffold
from .chat_executor import ChatExecutor


class ExperimentExecutor(ChatExecutor):
    """Patched version of ChatExecutor for use in development to run multiple variations
    of Context data and choose the best response."""

    def __init__(self, context) -> None:
        super().__init__(context)

    async def execute(self, params: dict[str, Any] | None = None) -> ChatCompletion:
        async def execute_variation(variation_data):
            variation_context = copy.deepcopy(self.context)
            variation_context._data = merge_dicts(
                variation_context._data, variation_data
            )

            executor = ChatExecutor(variation_context)
            return await executor.execute(params)

        tasks = []
        variation_names = list(self.context.experiment_variations.keys())
        random.shuffle(variation_names)

        for name in variation_names:
            variation = self.context.experiment_variations[name]
            tasks.append(execute_variation(variation))

        print("Generating variations...")
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            scaffold = ResponseScaffold(result.content, self.context.response_scaffold)
            print(f"\n---------- (#{i + 1}) ----------\n")
            print(scaffold.extract())

        choice = int(input("\nSelect response (1-" + str(len(results)) + "): ")) - 1

        async with aiofiles.open("experiment_log.txt", "a") as f:
            await f.write(f"{variation_names[choice]}\n")

        return results[choice]


def merge_dicts(dict1, dict2):
    result = copy.deepcopy(dict1)
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
