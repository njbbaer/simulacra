from src import Context, Chat

context = Context('config.yml')
chat = Chat(context)

while True:
    user_input = input('You: ')
    if user_input == 'memorize':
        response = chat.memorize()
    else:
        response = chat.chat(user_input)
        print(f'AI: {response}')
