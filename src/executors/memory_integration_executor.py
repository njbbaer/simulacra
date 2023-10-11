import asyncio
from dataclasses import dataclass
from typing import Union

from .executor import Executor


@dataclass
class Range:
    min: Union[int, float]
    max: Union[int, float]

    def contains(self, value):
        return self.min <= value <= self.max


class MemoryIntegrationExecutor(Executor):
    CHUNK_SIZE = Range(2000, 4000)
    COMPRESSION_RATIO = Range(0.70, 0.95)
    COMPRESSION_BIAS_TEXT = [
        "much longer than",
        "longer than",
        "slightly longer than",
        "very slightly longer than",
        "the same length as",
        "very slightly shorter than",
        "slightly shorter than",
        "shorter than",
        "much shorter than",
    ]

    async def execute(self):
        tasks = self._build_tasks()
        new_chunks = await asyncio.gather(*tasks)
        self._merge_chunks(new_chunks)
        return new_chunks

    def _build_tasks(self):
        tasks = []
        for chunk in self.context.current_memory_chunks:
            tasks.append(self._compress_chunk(chunk, 20))
        tasks.append(self._fetch_conversation_summary_completion())
        return tasks

    async def _compress_chunk(self, chunk, tries, bias=0):
        if len(chunk) < self.CHUNK_SIZE.min:
            return chunk

        if tries <= 0:
            raise Exception("Failed after max attempts.")

        new_chunk = await self._fetch_chunk_compression_completion(chunk, bias)
        ratio = len(new_chunk) / len(chunk)
        self._log_compression_stats(len(chunk), ratio, tries, bias)

        if ratio > self.COMPRESSION_RATIO.max:
            return await self._compress_chunk(chunk, tries - 1, min(bias + 1, 4))
        elif ratio < self.COMPRESSION_RATIO.min:
            return await self._compress_chunk(chunk, tries - 1, max(bias - 1, -4))

        return new_chunk

    def _log_compression_stats(self, len_chunk, ratio, retries, bias):
        with open("data.csv", "a") as f:
            f.write(f"{len_chunk},{ratio},{retries},{bias}\n")

    async def _fetch_conversation_summary_completion(self):
        return await self._generate_chat_completion(
            self._build_conversation_summarization_messages(),
            {"model": "gpt-3.5-turbo-16k", "max_tokens": 1000, "temperature": 0},
        )

    async def _fetch_chunk_compression_completion(self, chunk, bias):
        return await self._generate_legacy_completion(
            self._build_chunk_compression_prompt(chunk, bias),
            {"model": "gpt-3.5-turbo-instruct", "max_tokens": 2000, "temperature": 1},
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

    def _build_chunk_compression_prompt(self, memory_chunk, bias):
        bias_text = self.COMPRESSION_BIAS_TEXT[bias + 4]
        prompt = self.context.memory_integration_prompt.replace(
            "{BIAS_TEXT}", bias_text
        )
        return "{}\n\n---\n\n{}\n\n---\n\n# Full-length rewritten document:".format(
            memory_chunk, prompt
        )

    def _format_conversation_history(self):
        def format_message(msg):
            name = self.context.get_name(msg["role"])
            return f'{name}:\n\n{msg["content"]}'

        messages = [format_message(msg) for msg in self.context.current_messages]
        return "\n\n".join(messages)
