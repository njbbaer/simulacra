import argparse
import multiprocessing
import os
from typing import Any

import dotenv
import toml

from src import TelegramBot
from src.telemetry import Telemetry

dotenv.load_dotenv()

IS_DEVELOPMENT = os.getenv("ENVIRONMENT") == "development"
CONFIG_FILEPATH = os.getenv("CONFIG_FILEPATH")


def main() -> None:
    if IS_DEVELOPMENT:
        _start_reloader()

    config_file = _get_args()
    if config_file is None:
        raise ValueError("Config file is required")
    with open(config_file) as f:
        configs = toml.load(f)
    bot_configs = configs.get("simulacra", [])
    telemetry = _telemetry(config_file, configs.get("base_dir"))

    if IS_DEVELOPMENT:
        _run_bot(bot_configs[0], telemetry)
    else:
        for bot_config in bot_configs:
            multiprocessing.Process(
                target=_run_bot, args=(bot_config, telemetry)
            ).start()


def _telemetry(config_file: str, base_dir: str | None) -> Telemetry:
    """Telemetry under `base_dir`, resolved against the config file's directory."""
    if base_dir:
        config_dir = os.path.dirname(os.path.abspath(config_file))
        base_dir = os.path.normpath(os.path.join(config_dir, base_dir))
    deployment = os.path.splitext(os.path.basename(config_file))[0]
    return Telemetry.for_deployment(base_dir, deployment)


def _run_bot(bot_config: dict[str, Any], telemetry: Telemetry) -> None:
    TelegramBot(
        bot_config["context_filepath"],
        bot_config["telegram_token"],
        bot_config["authorized_user"],
        telemetry,
    ).run()


def _get_args() -> str | None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", type=str, nargs="?", default=CONFIG_FILEPATH)
    return parser.parse_args().config_file


def _start_reloader() -> None:
    import hupper  # type: ignore

    reloader = hupper.start_reloader("app.main")
    reloader.watch_files([CONFIG_FILEPATH, ".env"])


if __name__ == "__main__":
    main()
