import openai
import readline

from yaml_setup import yaml
from ruamel.yaml.scalarstring import LiteralScalarString


class Context:
    def __init__(self, config_file):
        with open(config_file, 'r') as file:
            self.context = yaml.load(file)
            self.context.setdefault('messages', [])
        self.save()

    def render_chat_messages(self):
        messages = [
            {
                'role': 'system',
                'content': self._render_chat_prompt()
            },
        ]
        messages.extend(self.context['messages'])
        return messages

    def render_memorize_messages(self):
        memory = self.context['memory']
        new_info_prompt = 'Integrate the following new information:\n\n' \
            + self._render_chat_history()
        return [
            {'role': 'system', 'content': memory['prompt']},
            {'role': 'assistant', 'content': memory['current']},
            {'role': 'user', 'content': new_info_prompt},
            {'role': 'system', 'content': memory['prompt']},
        ]

    def add_message(self, role, message):
        self.context['messages'].append({
            'role': role,
            'content': LiteralScalarString(message)
        })
        self.save()

    def save(self):
        with open('context.yml', 'w') as file:
            yaml.dump(self.context, file)

    def reload(self):
        with open('context.yml', 'r') as file:
            self.context = yaml.load(file)

    # Private

    def _render_chat_prompt(self):
        return self.context['agent']['prompt'].replace(
            '{{ MEMORY }}', self.context['memory']['current']
        )

    def _render_chat_history(self):
        return '\n\n'.join([
            f'{message["role"]}:\n\n{message["content"]}'
            for message in self.context['messages']
        ])


def gpt_complete(messages):
    # print('\n##### DEBUG #####')
    # print(messages)
    return openai.ChatCompletion.create(
        model="gpt-4",
        temperature=0.0,
        messages=messages,
    )['choices'][0]['message']['content']


if __name__ == '__main__':
    context = Context('config.yml')
    while True:
        user_input = input('You: ')
        context.reload()
        if user_input == 'memorize':
            messages = context.render_memorize_messages()
            response = gpt_complete(messages)
            print('\n##### NEW MEMORY #####')
            print(response)
        else:
            context.add_message('user', user_input)
            messages = context.render_chat_messages()
            response = gpt_complete(messages)
            context.add_message('assistant', response)
            print(f'AI: {response}')
