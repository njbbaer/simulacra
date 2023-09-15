import argparse

from src.telegram_bot import TelegramBot
from src.models import initialize_db


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('context_file', type=str)
    return parser.parse_args()


if __name__ == "__main__":
    initialize_db()
    args = get_args()
    TelegramBot(args.context_file).start()
