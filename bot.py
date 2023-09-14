import os
import argparse
import telebot
from telebot import types
from dotenv import load_dotenv

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
            bot.send_chat_action(message.chat.id, action='typing')
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


if __name__ == '__main__':
    bot = configure_bot()
    bot.infinity_polling()
