import argparse
import telebot
import os

from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('context_file', type=str)
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    sim = Simulacrum(args.context_file)
    bot = telebot.TeleBot(os.environ['TELEGRAM_API_TOKEN'])
    user_id = os.environ['TELEGRAM_USER_ID']
    TelegramBot(bot, sim, user_id).start()
