from src.context import Context
from src.chat import Chat


class ChatInterface:
    def __init__(self, context_file):
        self.context = Context(context_file)
        self.chat = Chat(self.context)
        self.command_handlers = {
            '/integrate': self.integrate_memory,
            '/clear': self.clear_messages,
        }

    def run(self):
        while True:
            user_input = input('You: ')
            if user_input in self.command_handlers:
                self.command_handlers[user_input]()
            else:
                response = self.chat.chat(user_input)
                print(f'AI: {response}')

    def integrate_memory(self):
        print('System: Integrating memory...', end='', flush=True)
        self.chat.integrate_memory()
        print('done')

    def clear_messages(self):
        self.chat.clear_messages()
        print('System: Memory cleared')
