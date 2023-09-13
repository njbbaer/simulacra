from src import Context, Chat

context = Context('config.yml')
chat = Chat(context)

while True:
    user_input = input('You: ')
    if user_input == '/integrate':
        response = chat.integrate_memory()
    else:
        response = chat.chat(user_input)
        print(f'AI: {response}')
