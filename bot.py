import os
import argparse
import telebot
from dotenv import load_dotenv
import threading
import time
from contextlib import contextmanager


from src.simulacrum import Simulacrum

load_dotenv()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('context_file', type=str)
    return parser.parse_args()


def execute_with_feedback(bot, chat_id, action, format_response=None):
    try:
        with show_typing(bot, chat_id):
            result = action()
        message = format_response(result) if format_response else result
        bot.send_message(chat_id, message, parse_mode='Markdown')
    except Exception as e:
        error_text = f'```\n❌ An error occurred: {str(e)}\n```'
        bot.send_message(chat_id, error_text, parse_mode='Markdown')


def configure_integrate_command_handler(bot, sim):
    @bot.message_handler(commands=['integrate'], func=is_authorized)
    def handle(message):
        def format_response(_): return '```\n🧠 Memory integration complete\n```'
        execute_with_feedback(bot, message.chat.id, sim.integrate_memory, format_response)


def configure_authorized_message_handler(bot, sim):
    @bot.message_handler(func=is_authorized)
    def handle(message):
        execute_with_feedback(bot, message.chat.id, lambda: sim.chat(message.text))


def configure_unauthorized_message_handler(bot):
    @bot.message_handler(func=lambda message: True)
    def handle(message):
        bot.reply_to(message, 'Unauthorized')


def is_authorized(message):
    return str(message.chat.id) == os.environ['USER_ID']


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


def configure_bot():
    args = get_args()
    sim = Simulacrum(args.context_file)
    bot = telebot.TeleBot(os.environ['API_TOKEN'])

    configure_integrate_command_handler(bot, sim)
    configure_authorized_message_handler(bot, sim)
    configure_unauthorized_message_handler(bot)

    return bot


if __name__ == '__main__':
    bot = configure_bot()
    bot.infinity_polling()
