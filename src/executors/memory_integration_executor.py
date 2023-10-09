import asyncio
from dataclasses import dataclass
from functools import wraps
from typing import Union

from .executor import Executor


@dataclass
class Range:
    min: Union[int, float]
    max: Union[int, float]

    def contains(self, value):
        return self.min <= value <= self.max


def retry(max_tries):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for retries in range(max_tries):
                kwargs["retries"] = retries
                result = await func(*args, **kwargs)
                if result is not None:
                    return result
            raise Exception(f"Failed after {max_tries} attempts.")

        return wrapper

    return decorator


class MemoryIntegrationExecutor(Executor):
    CHUNK_SIZE = Range(2000, 4000)
    COMPRESSION_RATIO = Range(0.80, 0.97)

    async def execute(self):
        tasks = self._build_tasks()
        new_chunks = await asyncio.gather(*tasks)
        self._merge_chunks(new_chunks)
        return new_chunks

    def _build_tasks(self):
        tasks = []
        for chunk in self.context.current_memory_chunks:
            tasks.append(self._compress_chunk(chunk))
        tasks.append(self._fetch_conversation_summary_completion())
        return tasks

    @retry(max_tries=10)
    async def _compress_chunk(self, chunk, retries=0):
        if len(chunk) < self.CHUNK_SIZE.min:
            return chunk

        new_chunk = await self._fetch_chunk_compression_completion(chunk)
        ratio = len(new_chunk) / len(chunk)
        self._log_compression_stats(len(chunk), ratio, retries)
        if self.COMPRESSION_RATIO.contains(ratio):
            return new_chunk

    def _log_compression_stats(self, len_chunk, ratio, retries):
        with open("data.csv", "a") as f:
            f.write(f"{len_chunk},{ratio},{retries}\n")

    async def _fetch_conversation_summary_completion(self):
        return await self._generate_chat_completion(
            self._build_conversation_summarization_messages(),
            {"model": "gpt-3.5-turbo-16k", "max_tokens": 1000, "temperature": 0},
        )

    async def _fetch_chunk_compression_completion(self, chunk):
        return await self._generate_legacy_completion(
            self._build_chunk_compression_prompt(chunk),
            {"model": "gpt-3.5-turbo-instruct", "max_tokens": 1000, "temperature": 1},
        )

    def _merge_chunks(self, chunks):
        i = 0
        while i < len(chunks) - 1:
            if len(chunks[i]) + len(chunks[i + 1]) < self.CHUNK_SIZE.max:
                chunks[i] += "\n\n" + chunks.pop(i + 1)
            else:
                i += 1

    def _build_conversation_summarization_messages(self):
        return [
            {
                "role": "system",
                "content": self.context.conversation_summarization_prompt,
            },
            {
                "role": "user",
                "content": "\n\n".join(
                    [
                        "# Memory context:",
                        self.context.current_memory,
                        "---",
                        "# Conversation:",
                        self._format_conversation_history(),
                    ]
                ),
            },
            {
                "role": "user",
                "content": self.context.conversation_summarization_prompt,
            },
        ]

    def _build_chunk_compression_prompt(self, memory_chunk):
        return "{}\n\n---\n\n{}".format(
            memory_chunk, self.context.memory_integration_prompt
        )

    def _format_conversation_history(self):
        def format_message(msg):
            name = self.context.get_name(msg["role"])
            return f'{name}:\n\n{msg["content"]}'

        messages = [format_message(msg) for msg in self.context.current_messages]
        return "\n\n".join(messages)
