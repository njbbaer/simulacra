from .prompt_executor import PromptExecutor


class ChatPromptExecutor(PromptExecutor):
    async def execute(self):
        messages = self._build_chat_messages()
        return await self.llm.fetch_completion(messages)

    def _build_chat_messages(self):
        messages = [{'role': 'system', 'content': self._format_chat_prompt()}]
        messages.extend(self.context.current_messages)
        messages.append({'role': 'system', 'content': self.context.reinforcement_chat_prompt})
        return messages

    def _format_chat_prompt(self):
        name = self.context.get_name('assistant')
        memory = f"{name}'s Memory:\n\n{self.context.current_memory}"
        return f"{self.context.chat_prompt}\n\n---\n\n{memory}"

    def _build_chat_messages(self):
        return [
            {
                'role': 'system',
                'content': '\n\n'.join([
                    self.context.chat_prompt,
                    '---',
                    f"{self.context.get_name('assistant')}'s Knowledge Base:",
                    self.context.current_memory
                ])
            },
            *self.context.current_messages,
            {
                'role': 'system',
                'content': self.context.reinforcement_chat_prompt
            }
        ]