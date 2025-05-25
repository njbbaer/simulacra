import argparse
import multiprocessing
import os

import dotenv
import toml

from src import TelegramBot

dotenv.load_dotenv()

IS_DEVELOPMENT = os.environ.get("ENVIRONMENT") == "development"
CONFIG_FILE = os.environ.get("CONFIG_FILE")


def _run_bot(bot_config):
    TelegramBot(
        bot_config["context_filepath"],
        bot_config["telegram_token"],
        bot_config["authorized_users"],
    ).run()


def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", type=str, nargs="?", default=CONFIG_FILE)
    return parser.parse_args().config_file


def main():
    config_file = _get_args()
    configs = toml.load(open(config_file, "r"))
    bot_configs = configs.get("simulacra", [])

    if IS_DEVELOPMENT:
        _run_bot(bot_configs[0])
    else:
        for bot_config in bot_configs:
            multiprocessing.Process(target=_run_bot, args=(bot_config,)).start()


if __name__ == "__main__":
    if IS_DEVELOPMENT:
        import hupper

        hupper.start_reloader("app.main")
    main()
