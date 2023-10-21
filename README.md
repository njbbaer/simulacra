# Simulacra

[![build](https://github.com/njbbaer/simulacra/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/njbbaer/simulacra/actions/workflows/build.yml)

Simulacra is a platform for creating GPT-4 powered Telegram bots with personalities, internal dialogue, and long term memory.

## Usage

### Install dependencies with Pipenv

```sh
pipenv install
```

### Configure your bot

Modify the example configuration file `example/config.toml` with your `TELEGRAM_API_TOKEN` and `TELEGRAM_USERNAME`.

- Interact with [@BotFather](https://t.me/botfather) to create a new bot and get its API token.

See the [Configuration](#Configuration) section for more information.

### Run the application

```sh
pipenv run app examples/config.yml
```

### Interact with your bot on Telegram

Send a message to your bot and it will respond. Send `/help` to see a list of commands.

## Configuration

The application is configured by a config file and one or more context files.

### Config file

The config file is a TOML file that initializes one or more bots and configures the paths to their context files.

See `example/config.toml` for a sample config file.

### Context file

The context file is a YAML file that defines a bot's personality prompts, stores its conversation history, and memory.

See `example/context.yml` for a sample context file.

A config file contains the following keys:

- `names`: Contains two sub-keys `assistant` and `user` which identify the names of the bot and user.
- `chat_prompt`: The system prompt used to generate the bot's response. Describe the bot's personality and its instructions here. Write as much detail as you can.
- `reinforcement_chat_prompt`: An extra system message provided very last to the model. Use this to reinforce the bot's personality. Keep it short.
- `conversations` will be generated by the application and contains the bot's conversation history and memory. You may edit this section at any time to manually modify the bot's memory.

## Development mode

Enable code reloading with development mode. Create a `.env` file or add the following to your environment:

```sh
export ENVIRONMENT=development
```

Note: Development mode can only run a single bot.
