from src.yaml_init import yaml
from ruamel.yaml.scalarstring import LiteralScalarString


class Context:
    def __init__(self, config_file):
        with open(config_file, 'r') as file:
            self.dict = yaml.load(file)
            self.dict.setdefault('messages', [])
        self.save()

    def save(self):
        with open('context.yml', 'w') as file:
            yaml.dump(self.dict, file)

    def reload(self):
        with open('context.yml', 'r') as file:
            self.dict = yaml.load(file)

    def add_message(self, role, message):
        self.dict['messages'].append({
            'role': role,
            'content': LiteralScalarString(message)
        })
        self.save()

    def set_memory(self, memory):
        self.dict['current_memory'] = memory
        self.save()

    @property
    def chat_messages(self):
        return self.dict['messages']

    @property
    def chat_prompt(self):
        return self.dict['chat_prompt'].replace(
            '{{ MEMORY }}', self.current_memory
        )

    @property
    def memorizer_prompt(self):
        return self.dict['memory_prompt']

    @property
    def current_memory(self):
        return self.dict['current_memory']
