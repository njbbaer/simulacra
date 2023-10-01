import asyncio

from src.prompt_executors import MemoryIntegrationExecutor
from src.context import Context
from src.yaml_config import yaml

ORIGINAL_FILEPATH = 'sync/contexts/test.yml'
NEW_FILEPATH = 'sync/contexts/test_rebuild.yml'


def copy_conversation():
    with open(ORIGINAL_FILEPATH, 'r') as file:
        source = yaml.load(file)

    with open(NEW_FILEPATH, 'r') as file:
        destination = yaml.load(file)

    index = len(destination['conversations']) - 1
    destination['conversations'][index]['messages'] = source['conversations'][index]['messages']

    with open(NEW_FILEPATH, 'w') as file:
        yaml.dump(destination, file)


async def integrate_memory():
    context = Context(NEW_FILEPATH)
    memory_chunks = await MemoryIntegrationExecutor(context).execute()
    context.new_conversation(memory_chunks)
    context.save()


async def main():
    for i in range(100):
        print(f'Rebuilding #{i+1}')
        copy_conversation()
        await integrate_memory()


if __name__ == '__main__':
    asyncio.run(main())
