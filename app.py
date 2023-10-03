import toml
import argparse
import multiprocessing
from src.telegram import TelegramBot


def run_bot(bot_config):
    TelegramBot(
        bot_config['context_filepath'],
        bot_config['telegram_token'],
        bot_config['authorized_users']
    ).run()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=str)
    return parser.parse_args().config_file


if __name__ == "__main__":
    config_file = get_args()
    configs = toml.load(open(config_file, 'r'))

    for bot_config in configs.get('simulacra', []):
        multiprocessing.Process(target=run_bot, args=(bot_config,)).start()
