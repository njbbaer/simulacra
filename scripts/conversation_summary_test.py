import asyncio
import statistics


from src.context import Context
from src.prompt_executors import MemoryIntegrationExecutor


async def main():
    ratios = []
    for i in range(10):
        class TestContext(Context):
            @property
            def current_conversation(self):
                return self.data['conversations'][i]

        context = TestContext('sync/contexts/test.yml')
        executor = MemoryIntegrationExecutor(context)
        summary = await executor._fetch_conversation_summary_completion()
        ratio = len(summary) / context.current_conversation_size
        ratios.append(ratio)
        print(f"#{i}: {len(summary)}/{context.current_conversation_size}, {format(ratio, '.2f')}")
    print(f"Standard deviation: {format(statistics.stdev(ratios), '.4f')}")

if __name__ == '__main__':
    asyncio.run(main())
