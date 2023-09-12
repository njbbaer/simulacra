import openai
import yaml
import readline


class Context:
    def __init__(self, config_file):
        with open(config_file, 'r') as file:
            self.context = yaml.safe_load(file)
            self.context.setdefault('messages', [])

    def render_prompt(self):
        return self.context['agent']['prompt'].replace(
            '{{ MEMORY }}', self.context['memory']['init']
        )

    def render_messages(self):
        messages = [
            {
                'role': 'system',
                'content': self.render_prompt()
            },
        ]
        messages.extend(self.context['messages'])
        return messages

    def add_message(self, role, message):
        self.context['messages'].append({
            'role': role,
            'content': message
        })


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
        context.add_message('user', user_input)
        messages = context.render_messages()
        response = gpt_complete(messages)
        context.add_message('assistant', response)
        print(f'AI: {response}')
