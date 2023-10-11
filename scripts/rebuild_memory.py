import argparse
import asyncio

from src.context import Context
from src.executors import MemoryIntegrationExecutor
from src.yaml_config import yaml


class YamlHandler:
    @staticmethod
    def load(filepath):
        with open(filepath, "r") as file:
            return yaml.load(file)

    @staticmethod
    def save(filepath, content):
        with open(filepath, "w") as file:
            yaml.dump(content, file)


class MemoryIntegrator:
    def __init__(self, filepath):
        self.context = Context(filepath)

    async def integrate(self):
        self.context.load()
        memory_chunks = await MemoryIntegrationExecutor(self.context).execute()
        self.context.new_conversation(memory_chunks)
        self.context.save()


class MemoryRebuilder:
    def __init__(self, source_path, dest_path):
        self.source_path = source_path
        self.dest_path = dest_path
        self.integrator = MemoryIntegrator(dest_path)

    async def process(self):
        while self._copy_conversation():
            await self.integrator.integrate()

    def _copy_conversation(self):
        source, destination = self._load_conversations()
        index = self._get_latest_index(destination)

        if not self._has_messages(source, index):
            print("All conversations are copied.")
            return False

        print(f"Rebuilding #{index + 1}")

        if self._conversation_already_copied(destination, index):
            return True

        self._update_messages(source, destination, index)
        YamlHandler.save(self.dest_path, destination)
        return True

    def _load_conversations(self):
        return YamlHandler.load(self.source_path), YamlHandler.load(self.dest_path)

    def _get_latest_index(self, destination):
        return len(destination["conversations"]) - 1

    def _conversation_already_copied(self, destination, index):
        return destination["conversations"][index]["messages"]

    def _has_messages(self, source, index):
        if index >= len(source["conversations"]):
            return False
        return "messages" in source["conversations"][index]

    def _update_messages(self, source, destination, index):
        destination["conversations"][index]["messages"] = source["conversations"][
            index
        ]["messages"]


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Rebuild conversations from a source to a destination file."
    )
    parser.add_argument("source_path", type=str, help="Path to the source file.")
    parser.add_argument("dest_path", type=str, help="Path to the destination file.")
    return parser.parse_args()


async def main():
    args = parse_arguments()
    rebuilder = MemoryRebuilder(args.source_path, args.dest_path)
    await rebuilder.process()


if __name__ == "__main__":
    asyncio.run(main())
