from .executor import Executor


class ChatExecutor(Executor):
    async def execute(self):
        return await self._generate_chat_completion(
            self.build_chat_messages(), {"model": "gpt-4"}
        )

    def build_chat_messages(self):
        return [
            {
                "role": "system",
                "content": "\n\n".join(
                    [
                        self.context.chat_prompt,
                        "---",
                        f"{self.context.get_name('assistant')}'s Memory:",
                        self.context.current_memory,
                    ]
                ),
            },
            *self.context.current_messages,
            {"role": "system", "content": self.context.reinforcement_chat_prompt},
        ]
