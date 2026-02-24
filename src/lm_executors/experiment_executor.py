import asyncio
import copy
import random
from typing import Any

import aiofiles

from ..chat_completion import ChatCompletion
from ..response_transform import strip_tags, transform_response
from ..utilities import merge_dicts
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
                variation_context.resolved_data, variation_data
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
            content = transform_response(
                result.content,
                self.context.response_patterns,
                self.context.required_response_tags,
            )
            print(f"\n---------- (#{i + 1}) ----------\n")
            print(strip_tags(content))

        choice = int(input(f"\nSelect response (1-{len(results)}): ")) - 1

        async with aiofiles.open("experiment_log.txt", "a") as f:
            await f.write(f"{variation_names[choice]}\n")

        return results[choice]
