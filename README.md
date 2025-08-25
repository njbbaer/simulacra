# Simulacra

[![build](https://github.com/njbbaer/simulacra/actions/workflows/build.yml/badge.svg?branch=master)](https://github.com/njbbaer/simulacra/actions/workflows/build.yml)
[![codecov](https://codecov.io/gh/njbbaer/simulacra/graph/badge.svg?token=F6D6YPZLZC)](https://codecov.io/gh/njbbaer/simulacra)

Simulacra is a platform for building LLM powered Telegram bots with a template-based context system.

This project was created for personal experimentation, but is available for anyone to use. Express your interest by starring this project on GitHub. Community contributions are welcome!

## Usage

For Docker specific usage, see the [Docker](#docker) section.

### Install dependencies with uv

```sh
uv install
```

If you wish to include development dependencies, add `--dev`.

### Configure your bot

Modify the example configuration file `example/config.toml` with your `TELEGRAM_API_TOKEN` and `TELEGRAM_USERNAME`.

- Interact with [@BotFather](https://t.me/botfather) to create a new bot and get its API token.

For more information, see the [Configuration](#configuration) section.

### Run the application

```sh
uv run app examples/config.toml
```

### Interact with your bot on Telegram

Send a message to your bot and it will respond.
Bots can also see and understand images, if the model supports this.

Send `/help` to see a list of commands:

```text
Actions
/new - Start a new conversation
/retry - Retry the last response
/undo - Undo the last exchange
/clear - Clear the conversation
/continue - Request another response
/cancel - Cancel the current request
/fact (...) - Add a fact to the conversation
/instruct (...) - Apply an instruction
/syncbook (...) - Sync current book position

Information
/stats - Show conversation statistics
/help - Show this help message
```

## Configuration

The application is configured by a TOML config file, which initializes one or more Telegram bots and defines the path to their YAML context files.

### Config file

The config TOML file initializes one or more Telegram bots and defines the path to their context files.

See `example/config.toml` for a template config file:

```toml
[[simulacra]]
context_filepath = "example/context.yml"
telegram_token = "telegram-bot-token"
authorized_user = "@telegram-username"

[[simulacra]]  # Second bot configuration
context_filepath = "example/second_bot_context.yml"
telegram_token = "second-telegram-bot-token"
authorized_user = "@telegram-username"
```

### Context file

The context file is a YAML file that defines bot configuration and state.

A context file contains the following keys:

| Key | Description |
|-----|-------------|
| `char_name` | The bot's character name |
| `conversation_id` | Current conversation ID (auto-generated) |
| `api_params` | API configuration object |
| `├─ model` | The model to use for the API |
| `└─ <key>` | Additional API parameters (e.g. temperature, max_tokens) |
| `vars` | Template variables object |
| `├─ chat_prompt` | The bot's system prompt |
| `└─ <key>` | Additional template variables |

Conversations are stored separately in a `conversations/` directory. Changes to the context file take effect immediately.

## Docker

This project publishes a Docker image to [GHCR](https://github.com/njbbaer/simulacra/pkgs/container/simulacra) `ghcr.io/njbbaer/simulacra`.

Configure your container with the following:

- Mount a directory containing your config and context files to `/config`.
- Set the path to your config file in the environment as `CONFIG_FILEPATH`.
- Set your OpenRouter API key in the environment as `OPENROUTER_API_KEY`.

Ensure the context file paths in your config are accessible within the container (i.e. `/config`).

### Docker examples

#### Docker run

```shell
docker run --name simulacra \
  --volume /var/lib/simulacra:/config \
  --env OPENROUTER_API_KEY=your_openai_api_key \
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
      - OPENROUTER_API_KEY={{ your_openai_api_key }}
      - CONFIG_FILEPATH=/config/config.toml
    restart: unless-stopped
```

## Development

### Code reloading

Enable code reloading with development mode. Create a `.env` file or add the following to your environment:

```sh
export ENVIRONMENT=development
```

Note: Development mode can only run a single bot.

### Pre-commit hooks

Install pre-commit hooks to run code formatting and linting before committing:

```sh
uv run pre-commit install
```

### Run tests

```sh
uv run pytest
```

### Release a new version

New versions are released automatically by GitHub Actions when a new tag is pushed.

This script automatically pushes a new tag using the version in `pyproject.toml`.

```sh
make release
```
