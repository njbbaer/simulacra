from .prompt_executor import PromptExecutor


class WakeupMessageExecutor(PromptExecutor):
    async def execute(self):
        messages = self.build_messages()
        return await self.llm.fetch_completion(messages)

    def build_messages(self):
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
                'content': self.context.wakeup_message_prompt
            }
        ]
