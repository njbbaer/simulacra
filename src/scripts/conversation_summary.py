import asyncio
import statistics

from src.context import Context
from src.executors import MemoryIntegrationExecutor


async def main():
    ratios = []
    for i in range(10):

        def get_context(j=i):
            class TestContext(Context):
                @property
                def current_conversation(self):
                    return self.data["conversations"][j]

            return TestContext("sync/contexts/test.yml")

        context = get_context()
        executor = MemoryIntegrationExecutor(context)
        summary = await executor._fetch_conversation_summary_completion()
        ratio = len(summary) / context.current_conversation_size
        ratios.append(ratio)
        size_ratio_string = f"{len(summary)}/{context.current_conversation_size}"
        print(f"#{i}: {size_ratio_string}, {format(ratio, '.2f')}")
    print(f"Standard deviation: {format(statistics.stdev(ratios), '.4f')}")


if __name__ == "__main__":
    asyncio.run(main())
