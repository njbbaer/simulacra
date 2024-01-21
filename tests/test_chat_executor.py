from textwrap import dedent

import pytest

from src.executors.chat_executor import ChatExecutor


@pytest.fixture
def current_messages():
    return [
        {"role": "assistant", "content": "Hello, Bob."},
        {
            "role": "user",
            "image_url": "http://example.com/photo.jpg",
            "content": "Hi, Alice. Here is a picture.",
        },
    ]


@pytest.fixture
def vars():
    return {
        "list_of_things": ["thing1", "thing2"],
        "chat_prompt": "file:chat_prompt.j2",
        "reinforcement_chat_prompt": "Remember, you are Alice.",
    }


@pytest.fixture
def chat_prompt_file_content():
    return dedent(
        """
        You are Alice, speaking to Bob.
        {% for thing in list_of_things %}
          - {{ thing }}
        {% endfor %}
        """
    ).strip()


@pytest.fixture
def mock_context(mocker, current_messages, vars):
    mock_instance = mocker.patch("src.context.Context").return_value
    mock_instance.vars = vars
    mock_instance.current_messages = current_messages
    mock_instance.current_conversation_facts = []
    return mock_instance


@pytest.fixture
def mock_read_chat_prompt(mocker, chat_prompt_file_content):
    original_open = open

    def mock_open(file, mode="r", *args, **kwargs):
        if file.endswith("chat_prompt.j2"):
            return mocker.mock_open(read_data=chat_prompt_file_content).return_value
        else:
            return original_open(file, mode, *args, **kwargs)

    mocker.patch("builtins.open", mock_open)


@pytest.fixture
def mock_generate_chat_completion(mocker):
    completion_mock = mocker.Mock()
    completion_mock.cost = 0.25
    async_mock = mocker.AsyncMock(return_value=completion_mock)
    mocker.patch("src.completion.ChatCompletion.generate", new=async_mock)
    return async_mock


@pytest.mark.asyncio
async def test_execute(
    mock_context, mock_generate_chat_completion, mock_read_chat_prompt
):
    await ChatExecutor(mock_context).execute()
    mock_generate_chat_completion.assert_called_once_with(
        [
            {
                "role": "system",
                "content": dedent(
                    """
                    You are Alice, speaking to Bob.
                      - thing1
                      - thing2
                    """
                ).strip(),
            },
            {"role": "assistant", "content": "Hello, Bob."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "http://example.com/photo.jpg",
                            "detail": "low",
                        },
                    },
                    {
                        "type": "text",
                        "text": "Hi, Alice. Here is a picture.",
                    },
                ],
            },
            {"role": "system", "content": "Remember, you are Alice."},
        ],
        {"model": "gpt-4-vision-preview", "max_tokens": 1000},
    )
