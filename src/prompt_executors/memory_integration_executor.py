from .prompt_executor import PromptExecutor


class MemoryIntegrationPromptExecutor(PromptExecutor):
    async def execute(self):
        messages = self.build_conversation_summarization_messages()
        conversation_summary = await self.llm.fetch_completion(messages)
        messages = self._build_integration_messages(conversation_summary)
        return await self.llm.fetch_completion(messages)

    def build_conversation_summarization_messages(self):
        return [
            {
                'role': 'system',
                'content': self.context.conversation_summarization_prompt
            },
            {
                'role': 'user',
                'content': '\n\n'.join([
                    '# Knowledge base:',
                    self.context.current_memory,
                    '---',
                    '# Most recent conversation:',
                    self._format_conversation_history()
                ])
            },
            {
                'role': 'system',
                'content': '\n\n'.join([
                    self.context.conversation_summarization_prompt,
                    '---',
                    '# Most recent conversation summary:'
                ])
            }
        ]

    def _build_integration_messages(self, conversation_summary):
        return [
            {
                'role': 'system',
                'content': self.context.memory_integration_prompt
            },
            {
                'role': 'user',
                'content': '\n\n'.join([
                    '# Knowledge base:',
                    self.context.current_memory,
                    conversation_summary
                ])
            },
            {
                'role': 'system',
                'content': '\n\n'.join([
                    self.context.memory_integration_prompt,
                    '---',
                    '# Rewritten knowledge base:'
                ])
            }
        ]

    def _format_conversation_history(self):
        def format_message(msg):
            name = self.context.get_name(msg['role'])
            return f'{name}:\n\n{msg["content"]}'

        messages = [format_message(msg) for msg in self.context.current_messages]
        return '\n\n'.join(messages)
