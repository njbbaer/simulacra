import telebot
import multiprocessing
import yaml

from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum


def start_bot(context_file, user_id, api_token):
    TelegramBot(
        telebot.TeleBot(api_token),
        Simulacrum(context_file),
        user_id
    ).start()


if __name__ == "__main__":
    with open('config.yml', 'r') as file:
        config = yaml.safe_load(file)

    for bot in config:
        multiprocessing.Process(
            target=start_bot,
            args=(
                bot['context_file'],
                bot['user_id'],
                bot['api_token']
            )
        ).start()
