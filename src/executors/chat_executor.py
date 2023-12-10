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
        messages.extend(self._build_image_prompt_messages())
        messages.extend(self.context.current_messages)
        if self.context.reinforcement_chat_prompt:
            messages.append(
                {"role": "system", "content": self.context.reinforcement_chat_prompt}
            )

        return messages

    def _build_image_prompt_messages(self):
        messages = []
        for image_prompt in self.context.image_prompts:
            messages.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_prompt["url"],
                                "detail": "low",
                            },
                        },
                        {
                            "type": "text",
                            "text": image_prompt["text"],
                        },
                    ],
                }
            )
        return messages
