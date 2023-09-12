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

    def render_chat_prompt(self):
        return self.context['agent']['prompt'].replace(
            '{{ MEMORY }}', self.context['memory']['init']
        )

    def render_chat_messages(self):
        messages = [
            {
                'role': 'system',
                'content': self.render_chat_prompt()
            },
        ]
        messages.extend(self.context['messages'])
        return messages

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


def gpt_complete(messages):
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
        context.add_message('user', user_input)
        messages = context.render_chat_messages()
        response = gpt_complete(messages)
        context.add_message('assistant', response)
        print(f'AI: {response}')
