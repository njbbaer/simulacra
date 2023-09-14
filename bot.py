import os
import argparse
import telebot
from dotenv import load_dotenv
import threading
import time
from contextlib import contextmanager


from src.chat import Chat

load_dotenv()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('context', type=str)
    return parser.parse_args()


def configure_authorized_message_handler(bot, chat):
    @bot.message_handler(func=lambda message: str(message.chat.id) == os.environ['USER_ID'])
    def handle(message):
        try:
            with show_typing(bot, message.chat.id):
                response = chat.chat(message.text)
            bot.reply_to(message, response)
        except Exception as e:
            bot.reply_to(message, f'An error occurred: {str(e)}')


def configure_unauthorized_message_handler(bot):
    @bot.message_handler(func=lambda message: True)
    def handle(message):
        bot.reply_to(message, 'Unauthorized')


def configure_bot():
    args = get_args()
    chat = Chat(args.context)
    bot = telebot.TeleBot(os.environ['API_TOKEN'])

    configure_authorized_message_handler(bot, chat)
    configure_unauthorized_message_handler(bot)

    return bot


@contextmanager
def show_typing(bot, chat_id):
    stop_typing = threading.Event()

    def send_typing_periodically():
        while not stop_typing.is_set():
            bot.send_chat_action(chat_id, action='typing')
            time.sleep(4)

    thread = threading.Thread(target=send_typing_periodically)
    thread.start()
    yield
    stop_typing.set()
    thread.join()


if __name__ == '__main__':
    bot = configure_bot()
    bot.infinity_polling()
