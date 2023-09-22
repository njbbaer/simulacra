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
pipenv run python start.py examples/config.yml
```
