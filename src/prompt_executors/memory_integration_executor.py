import asyncio
from .prompt_executor import PromptExecutor


class MemoryIntegrationPromptExecutor(PromptExecutor):
    async def execute(self):
        segments = self._segment_memory(4)
        tasks = []

        for segment in segments:
            tasks.append(self.llm.fetch_completion(
                self._build_segment_summarization_messages(segment),
                model='gpt-3.5-turbo', max_tokens=1000, temperature=0.2
            ))

        tasks.append(self.llm.fetch_completion(
            self._build_conversation_summarization_messages(),
            model='gpt-3.5-turbo-16k', max_tokens=1000, temperature=0.2
        ))

        new_segments = await asyncio.gather(*tasks)
        return '\n\n'.join(new_segments)

    def _build_conversation_summarization_messages(self):
        return [
            {
                'role': 'system',
                'content': self.context.conversation_summarization_prompt
            },
            {
                'role': 'user',
                'content': '\n\n'.join([
                    '# Memory Context:',
                    self.context.current_memory,
                    '---',
                    '# Latest Conversation:',
                    self._format_conversation_history()
                ])
            },
            {
                'role': 'system',
                'content': '\n\n'.join([
                    self.context.conversation_summarization_prompt,
                    '---',
                    '# Latest Conversation Summary:'
                ])
            }
        ]

    def _build_segment_summarization_messages(self, memory_segment):
        return [
            {
                'role': 'system',
                'content': self.context.memory_integration_prompt
            },
            {
                'role': 'user',
                'content': '\n\n'.join([
                    '# Memory Segment:',
                    memory_segment
                ])
            },
            {
                'role': 'system',
                'content': '\n\n'.join([
                    self.context.memory_integration_prompt,
                    '---',
                    '# New Memory Segment:',
                ])
            }
        ]

    def _format_conversation_history(self):
        def format_message(msg):
            name = self.context.get_name(msg['role'])
            return f'{name}:\n\n{msg["content"]}'

        messages = [format_message(msg) for msg in self.context.current_messages]
        return '\n\n'.join(messages)

    def _segment_memory(self, n):
        paragraphs = self.context.current_memory.split('\n\n')
        segment_lengths = [0] * n
        segments = [[] for _ in range(n)]

        for paragraph in paragraphs:
            min_idx = segment_lengths.index(min(segment_lengths))
            segment_lengths[min_idx] += len(paragraph)
            segments[min_idx].append(paragraph)

        return ['\n\n'.join(segment) for segment in segments]
