# Simulacra

[![build](https://github.com/njbbaer/simulacra/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/njbbaer/simulacra/actions/workflows/build.yml)

![OpenAI](https://img.shields.io/badge/OpenAI-74aa9c?style=for-the-badge&logo=openai&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

Simulacra is a platform for building GPT-4 powered Telegram bots with personalities, internal dialogue, and long term memory.

## Usage

For Docker specific usage, see the [Docker](#docker) section.

### Install dependencies with Pipenv

```sh
pipenv install
```

### Configure your bot

Modify the example configuration file `example/config.toml` with your `TELEGRAM_API_TOKEN` and `TELEGRAM_USERNAME`.

- Interact with [@BotFather](https://t.me/botfather) to create a new bot and get its API token.

For more information, see the [Configuration](#configuration) section.

### Run the application

```sh
pipenv run app examples/config.toml
```

### Interact with your bot on Telegram

Send a message to your bot and it will respond.

Bots can also see and understand images that you send, if using a model that supports this.

Send `/help` to see a list of commands:

```text
Actions
/new - Start a new conversation
/retry - Retry the last response
/reply - Reply immediately
/undo - Undo the last exchange
/clear - Clear the current conversation
/remember <text> - Add text to memory

Information
/stats - Show conversation statistics
/help - Show this help message
```

## Configuration

The application is configured by a config file and one or more context files.

### Config file

The config TOML file initializes one or more bots and defines the paths to their context files.

See `example/config.toml` for a template config file:

```toml
[[simulacra]]
context_filepath = "example/context.yml"
telegram_token = "TELEGRAM_API_TOKEN"
authorized_users = [ "TELEGRAM_USERNAME" ] # [ "@username", ... ]
```

### Context file

The context file is a YAML file that defines a bot's personality prompts, stores its conversation history, and memory.

See `example/context.yml` for a sample context file.

A config file contains the following top-level YAML keys:

| Key | Description |
|-----|-------------|
| `names` | Contains two sub-keys `assistant` and `user` which identify the names of the bot and user. |
| `chat_prompt` |  The system prompt. Describe the bot's personality and its instructions here. Write as much detail as you can. See the [Prompt Design](#prompt-design) section. |
| `reinforcement_chat_prompt` | An optional extra system message provided very last in the context window. Use this to briefly reinforce the bot's personality and instructions. Keep it short. |
| `conversations` | This key will be generated by the application and contains the bot's conversation history and memory. You may edit this section at any time to manually modify the bot's memory. |

Changes to the context file take effect immediately. You do not need to restart the application.

## Docker

This project publishes a Docker image to [GHCR](https://github.com/njbbaer/simulacra/pkgs/container/simulacra) `ghcr.io/njbbaer/simulacra`.

Configure your container with the following:

- Mount a directory containing your config and context files to `/config`.
- Set the path to your config file in the environment as `CONFIG_FILEPATH`.
- Set your OpenAI API key in the environment as `OPENAI_API_KEY`.

Ensure the context file paths in your config are accessible within the container (i.e. `/config`).

### Docker examples

#### Docker run

```shell
docker run --name simulacra \
  --volume /var/lib/simulacra:/config \
  --env OPENAI_API_KEY=your_openai_api_key \
  --env CONFIG_FILEPATH=/config/config.toml \
  --restart unless-stopped \
  ghcr.io/njbbaer/simulacra:latest
```

#### Docker Compose

```yaml
services:
  simulacra:
    image: ghcr.io/njbbaer/simulacra:latest
    container_name: simulacra
    volumes:
      - /var/lib/simulacra:/config
    environment:
      - OPENAI_API_KEY={{ your_openai_api_key }}
      - CONFIG_FILEPATH=/config/config.toml
    restart: unless-stopped
```

## Development

### Code reloading

Enable code reloading with development mode. Create a `.env` file or add the following to your environment:

```sh
export ENVIRONMENT=development
```

Note: Development mode can only run a single bot at once.

### Pre-commit hooks

Install pre-commit hooks to run code formatting and linting before committing:

```sh
pipenv run pre-commit install
```

### Run tests

```sh
pipenv run test
```

## Prompt Design

For improved personality driven conversations, we encourage designing prompts that instruct the bot to simulate personalities and engage in internal dialogue.

```text
❌ I am ...
❌ You are ...
✅ You are modeling the mind of ...
```

To support internal dialogue, the application can filter the LLM's response before providing it to the user. If the LLM uses the suggested XML tag format, only text within `<MESSAGE></MESSAGE>` or `<SPEAK></SPEAK>` tags will be sent to the user. Actions within optional `<ACT></ACT>` tags will be displayed in italics. Other content is considerd to be the bot's internal dialogue and is not shown, but will be preserved in memory. You can see an example of this type of prompt in the `example/context.yml` file. If the LLM does not use this format, the entire response is sent to the user as-is.

This form of prompt design is inspired by [Reflective Linguistic Programming (RLP)](https://arxiv.org/abs/2305.12647) by Fischer, K. A. (2023).

We also suggest defining a short `reinforcement_chat_prompt` in the context file, which is an extra system instruction provided very last to the model to reinforce its personality and instructions. This can be used to overcome the model's tendency to drift away from the bot's declared personality during long conversations where the conversation history and memory are not sufficent to embody the relevant context.
