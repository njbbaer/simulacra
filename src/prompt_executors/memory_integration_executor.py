import asyncio
from .prompt_executor import PromptExecutor
from dataclasses import dataclass
from typing import Union


@dataclass
class Range:
    min: Union[int, float]
    max: Union[int, float]

    def contains(self, value):
        return self.min <= value <= self.max


class MemoryIntegrationExecutor(PromptExecutor):
    CHUNK_SIZE = Range(2000, 4000)
    SUMMARY_SIZE = Range(1000, 2000)
    COMPRESSION_RATIO = Range(0.80, 0.97)
    MAX_ATTEMPTS = 10

    async def execute(self):
        tasks = []
        for chunk in self.context.current_memory_chunks:
            tasks.append(self._summarize_chunk(chunk))
        tasks.append(self._fetch_conversation_summary_completion())
        new_chunks = await asyncio.gather(*tasks)
        self._merge_chunks(new_chunks)
        return new_chunks

    async def _summarize_chunk(self, chunk, retries=0):
        if len(chunk) < self.CHUNK_SIZE.min:
            return chunk

        if retries >= self.MAX_ATTEMPTS:
            raise Exception(f'Failed to summarize chunk after {retries} attempts. Try again!')

        new_chunk = await self._fetch_chunk_summary_completion(chunk)
        ratio = len(new_chunk) / len(chunk)

        with open('data.csv', 'a') as f:
            f.write(f'{len(chunk)},{ratio},{retries}\n')

        if not self.COMPRESSION_RATIO.contains(ratio):
            return await self._summarize_chunk(chunk, retries + 1)

        return new_chunk

    def _fetch_conversation_summary_completion(self):
        return self.llm.fetch_completion(
            self._build_conversation_summarization_messages(),
            model='gpt-3.5-turbo-16k', max_tokens=1000, temperature=0.2
        )

    def _fetch_chunk_summary_completion(self, chunk):
        return self.llm.fetch_completion(
            self._build_chunk_summarization_messages(chunk),
            model='gpt-3.5-turbo', max_tokens=1000, temperature=1
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
                'role': 'system',
                'content': self.context.conversation_summarization_prompt
            },
            {
                'role': 'user',
                'content': '\n\n'.join([
                    '# Memory context:',
                    self.context.current_memory,
                    '---',
                    '# Conversation:',
                    self._format_conversation_history()
                ])
            },
            {
                'role': 'user',
                'content': self.context.conversation_summarization_prompt,
            }
        ]

    def _build_chunk_summarization_messages(self, memory_chunk):
        return [
            {
                'role': 'system',
                'content': self.context.memory_integration_prompt
            },
            {
                'role': 'user',
                'content': memory_chunk
            },
            {
                'role': 'user',
                'content': self.context.memory_integration_prompt
            },
        ]

    def _format_conversation_history(self):
        def format_message(msg):
            name = self.context.get_name(msg['role'])
            return f'{name}:\n\n{msg["content"]}'

        messages = [format_message(msg) for msg in self.context.current_messages]
        return '\n\n'.join(messages)
