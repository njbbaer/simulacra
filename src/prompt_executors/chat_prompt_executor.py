from .prompt_executor import PromptExecutor


class ChatExecutor(PromptExecutor):
    async def execute(self):
        messages = self.build_chat_messages()
        return await self.llm.fetch_completion(messages)

    def build_chat_messages(self):
        return [
            {
                'role': 'system',
                'content': '\n\n'.join([
                    self.context.chat_prompt,
                    '---',
                    f"{self.context.get_name('assistant')}'s Memory Context:",
                    self.context.current_memory
                ])
            },
            *self.context.current_messages,
            {
                'role': 'system',
                'content': self.context.reinforcement_chat_prompt
            }
        ]
