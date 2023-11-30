from .executor import Executor


class ChatExecutor(Executor):
    async def execute(self):
        return await self._generate_chat_completion(
            self.build_chat_messages(),
            {
                "model": self.context.chat_model,
                "max_tokens": 1000,
            },
        )

    def build_chat_messages(self):
        system_content = [self.context.chat_prompt]
        if self.context.current_memory:
            system_content.extend(
                [
                    "---",
                    f"{self.context.get_name('assistant')}'s Memory:",
                    self.context.current_memory,
                ]
            )
        messages = [{"role": "system", "content": "\n\n".join(system_content)}]

        messages.extend(self.context.current_messages)

        if self.context.reinforcement_chat_prompt:
            messages.append(
                {"role": "system", "content": self.context.reinforcement_chat_prompt}
            )

        return messages
