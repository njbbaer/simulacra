import asyncio
import math
from dataclasses import dataclass
from typing import Union

from .executor import Executor

DEFAULT_CONVERSATION_SUMMARIZATION_PROMPT = """\
Create a comprehensive and information-dense summary of the latest conversation. \
Describe important events, facts, and the character's emotional reasoning.

Carefully follow these guidelines:
- Include all important information from the conversation.
- Report the conversation dispassionately without editorializing.
- Longer and more important conversations should have longer summaries.
- Do not describe the summary as the "latest" conversation.
- Use the past memory for context only. Do not include it in your summary.
"""

DEFAULT_MEMORY_INTEGRATION_PROMPT = """\
Improve the document above by rewriting it to be clearer and more efficent.

The new document should be {BIAS_TEXT} the original document.

Carefully follow these guidelines:
- Use concise, information-dense language, avoiding transitional statements and filler \
words.
- Write in your own words, not plagiarized the original document.
- Comprehensively cover the entire document without omitting important details.
- Fix confusing, awkward, or repetitive phrasing.
- Improve sentence flow by reordering or rephrasing.
- Break or combine paragraphs to group related topics and improve readability.
- Write dispassionately without editorializing.
- Do not infer events that are not supported by the original document.
- Preserve important details and eliminate trivial ones.
"""


@dataclass
class Range:
    min: Union[int, float]
    max: Union[int, float]

    def contains(self, value):
        return self.min <= value <= self.max


class MemoryIntegrationExecutor(Executor):
    CHUNK_SIZE = Range(2000, 4000)
    COMPRESSION_RATIO = Range(0.70, 0.90)
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
            tasks.append(self._compress_chunk(chunk, retries=10))
        tasks.append(self._fetch_conversation_summary_completion())
        return tasks

    async def _compress_chunk(self, chunk, retries, bias=0):
        if len(chunk) < self.CHUNK_SIZE.min:
            return chunk

        if retries <= 0:
            raise Exception("Failed after max attempts.")

        new_chunk = await self._fetch_chunk_compression_completion(chunk, bias)
        ratio = len(new_chunk) / len(chunk)
        self._log_compression_stats(len(chunk), ratio, retries, bias)

        if ratio > self.COMPRESSION_RATIO.max:
            return await self._compress_chunk(
                chunk, retries - 1, self._increment_bias(bias)
            )
        elif ratio < self.COMPRESSION_RATIO.min:
            return await self._compress_chunk(
                chunk, retries - 1, self._decrement_bias(bias)
            )

        return new_chunk

    def _log_compression_stats(self, len_chunk, ratio, retries, bias):
        with open("data.csv", "a") as f:
            f.write(f"{len_chunk},{ratio},{retries},{bias}\n")

    async def _fetch_conversation_summary_completion(self):
        return await self._generate_chat_completion(
            self._build_conversation_summarization_messages(),
            {"model": "gpt-4-1106-preview", "max_tokens": 1000, "temperature": 0},
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
                "content": self._conversation_summarization_prompt,
            },
            {
                "role": "user",
                "content": "\n\n".join(
                    [
                        "# Past Memory Context:",
                        self.context.current_memory,
                        "---",
                        "# Conversation:",
                        self._format_conversation_history(),
                    ]
                ),
            },
            {
                "role": "user",
                "content": self._conversation_summarization_prompt,
            },
        ]

    def _build_chunk_compression_prompt(self, memory_chunk, bias):
        bias_text = self.COMPRESSION_BIAS_TEXT[bias + self._bias_offset]
        prompt = self._memory_integration_prompt.replace("{BIAS_TEXT}", bias_text)
        return "{}\n\n---\n\n{}\n\n---\n\n# Full-length rewritten document:".format(
            memory_chunk, prompt
        )

    def _format_conversation_history(self):
        def format_message(msg):
            name = self.context.get_name(msg["role"])
            return f'{name}:\n\n{msg["content"]}'

        messages = [format_message(msg) for msg in self.context.current_messages]
        return "\n\n".join(messages)

    def _increment_bias(self, bias):
        return min(bias + 1, self._bias_offset)

    def _decrement_bias(self, bias):
        return max(bias - 1, -self._bias_offset)

    @property
    def _bias_offset(self):
        return math.floor(len(self.COMPRESSION_BIAS_TEXT) / 2)

    @property
    def _conversation_summarization_prompt(self):
        return (
            DEFAULT_CONVERSATION_SUMMARIZATION_PROMPT
            or self.context.conversation_summarization_prompt
        )

    @property
    def _memory_integration_prompt(self):
        return (
            DEFAULT_MEMORY_INTEGRATION_PROMPT or self.context.memory_integration_prompt
        )
