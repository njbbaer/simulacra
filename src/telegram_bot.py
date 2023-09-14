import os
import argparse
import telebot
from dotenv import load_dotenv
import threading
import time
from contextlib import contextmanager


from src.simulacrum import Simulacrum

load_dotenv()


def configure_bot():
    args = get_args()
    sim = Simulacrum(args.context_file)
    bot = telebot.TeleBot(os.environ['API_TOKEN'])

    configure_handlers(bot, sim)
    return bot


def configure_handlers(bot, sim):
    # Must be first to catch unauthorized messages
    @bot.message_handler(func=is_unauthorized)
    def unauthorized_message_handler(message):
        send_message(bot, message.chat.id, '🚫 Unauthorized', is_block=True)

    @bot.message_handler(commands=['integrate'])
    def integrate_command_handler(message):
        with process_with_feedback(bot, message.chat.id):
            sim.integrate_memory()
            send_message(bot, message.chat.id, '🧠 Memory integration complete', is_block=True)

    @bot.message_handler(commands=['retry'])
    def retry_command_handler(message):
        with process_with_feedback(bot, message.chat.id):
            response = sim.retry()
            send_message(bot, message.chat.id, response)

    @bot.message_handler()
    def message_handler(message):
        with process_with_feedback(bot, message.chat.id):
            response = sim.chat(message.text)
            send_message(bot, message.chat.id, response)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('context_file', type=str)
    return parser.parse_args()


def send_message(bot, chat_id, message, is_block=False):
    message = f'```\n{message}\n```' if is_block else message
    bot.send_message(chat_id, message, parse_mode='Markdown')


def is_unauthorized(message):
    return str(message.chat.id) != os.environ['USER_ID']


@contextmanager
def process_with_feedback(bot, chat_id):
    try:
        with show_typing(bot, chat_id):
            yield
    except Exception as e:
        error_text = f'❌ An error occurred: {str(e)}'
        send_message(bot, chat_id, error_text, is_block=True)


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
