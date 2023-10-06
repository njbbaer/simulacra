import argparse
import multiprocessing
import os

import hupper
import toml

from src import TelegramBot

IS_DEVELOPMENT = os.environ.get("ENVIRONMENT") == "development"


def run_bot(bot_config):
    TelegramBot(
        bot_config["context_filepath"],
        bot_config["telegram_token"],
        bot_config["authorized_users"],
    ).run()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", type=str)
    return parser.parse_args().config_file


def main():
    config_file = get_args()
    configs = toml.load(open(config_file, "r"))
    bot_configs = configs.get("simulacra", [])

    if IS_DEVELOPMENT:
        run_bot(bot_configs[0])
    else:
        for bot_config in bot_configs:
            multiprocessing.Process(target=run_bot, args=(bot_config,)).start()


if __name__ == "__main__":
    if IS_DEVELOPMENT:
        hupper.start_reloader("app.main")
    main()
