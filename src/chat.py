import openai
import readline


class Chat:
    def __init__(self, context):
        self.context = context

    def chat(self, user_input=None):
        self.context.reload()
        if user_input:
            self.context.add_message('user', user_input)
        messages = self._render_chat_messages()
        response = gpt_complete(messages)
        self.context.add_message('assistant', response)
        return response

    def memorize(self):
        self.context.reload()
        messages = self._render_memorizer_messages()
        response = gpt_complete(messages)
        self.context.set_memory(response)
        return response

    def _render_chat_messages(self):
        messages = [
            {
                'role': 'system',
                'content': self.context.chat_prompt,
            },
        ]
        messages.extend(self.context.chat_messages)
        return messages

    def _render_memorizer_messages(self):
        content = 'Integrate the following new information:\n\n' \
            + '\n\n'.join([
                f'{message["role"]}:\n\n{message["content"]}'
                for message in self.context.chat_messages
            ])
        return [
            {'role': 'system', 'content': self.context.memorizer_prompt},
            {'role': 'assistant', 'content': self.context.current_memory},
            {'role': 'user', 'content': content},
            {'role': 'system', 'content': self.context.memorizer_prompt},
        ]


def gpt_complete(messages):
    return openai.ChatCompletion.create(
        model="gpt-4",
        temperature=0.0,
        messages=messages,
    )['choices'][0]['message']['content']
