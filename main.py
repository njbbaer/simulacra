import argparse

from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('context_file', type=str)
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    sim = Simulacrum(args.context_file)
    TelegramBot(sim).start()
