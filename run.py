import telebot
import multiprocessing
import yaml
import argparse

from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum


def _start_bot(context_file, user_ids, api_token):
    TelegramBot(
        telebot.TeleBot(api_token),
        Simulacrum(context_file),
        user_ids
    ).start()


def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=str)
    return parser.parse_args()


if __name__ == "__main__":
    args = _get_args()
    with open(args.config_file, 'r') as file:
        config = yaml.safe_load(file)

    for bot in config:
        multiprocessing.Process(
            target=_start_bot,
            args=(
                bot['context_file'],
                bot['user_ids'],
                bot['api_token']
            )
        ).start()
