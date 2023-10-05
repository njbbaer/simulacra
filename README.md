# Simulacra

[![build](https://github.com/njbbaer/simulacra/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/njbbaer/simulacra/actions/workflows/build.yml)

Simulacra is a platform for creating OpenAI based Telegram bots with personalities, internal dialogue, and long term memory.

## Usage

### Install dependencies with Pipenv

```sh
pipenv install
```

### Run tests
  
```sh
pipenv run pytest
```

### Configure your bot

Set your `TELEGRAM_API_TOKEN` and `TELEGRAM_USER_ID` in `example/config.yml`.

- Interact with [@BotFather](https://t.me/botfather) to create a new bot and get its API token.
- Send a message to [@userinfobot](https://t.me/userinfobot) to get your Telegram user ID.

### Run the application

```sh
pipenv run python app.py examples/config.yml
```

## Development mode

Enable code reloading with development mode.

Create a `.env` file or add the following to your environment:

```sh
export ENVIRONMENT=development
```

Note: development mode will only run the first bot in your config file.
