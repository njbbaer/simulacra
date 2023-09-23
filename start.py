import yaml
import argparse
from telegram.ext import ApplicationBuilder

from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum


def _start_bot(context_file, authorized_users, api_token):
    TelegramBot(
        ApplicationBuilder().token(api_token).build(),
        Simulacrum(context_file),
        authorized_users
    ).run()


def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=str)
    return parser.parse_args()


if __name__ == "__main__":
    args = _get_args()
    with open(args.config_file, 'r') as file:
        config = yaml.safe_load(file)

    for bot in config:
        _start_bot(bot['context_file'], bot['authorized_users'], bot['api_token'])
