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
    TelegramBot(
        telebot.TeleBot(os.environ['TELEGRAM_API_TOKEN']),
        Simulacrum(args.context_file),
        os.environ['TELEGRAM_USER_ID']
    ).start()
