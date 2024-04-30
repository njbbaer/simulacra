import pytest

from src.lm_executors.chat_executor import ChatExecutor


@pytest.fixture
def conversation_messages():
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
        "chat_prompt": "You are Alice, speaking to Bob.",
        "reinforcement_chat_prompt": "Remember, you are Alice.",
    }


@pytest.fixture
def mock_context(mocker, conversation_messages, vars):
    mock_instance = mocker.patch("src.context.Context").return_value
    mock_instance.vars = vars
    mock_instance.conversation_messages = conversation_messages
    mock_instance.conversation_facts = []
    mock_instance.model = "gpt-4-vision-preview"
    return mock_instance


@pytest.fixture
def mock_generate_chat_completion(mocker):
    completion_mock = mocker.Mock()
    completion_mock.cost = 0.25
    async_mock = mocker.AsyncMock(return_value=completion_mock)
    mocker.patch("src.chat_completion.ChatCompletion.generate", new=async_mock)
    return async_mock


@pytest.fixture
def mock_resolve_vars(mocker):
    return mocker.patch(
        "src.lm_executors.chat_executor.resolve_vars", side_effect=lambda vars, _: vars
    )


@pytest.mark.asyncio
async def test_execute(mock_context, mock_generate_chat_completion, mock_resolve_vars):
    await ChatExecutor(mock_context).execute()
    mock_resolve_vars.assert_called_once()
    mock_generate_chat_completion.assert_called_once()

    actual_args = mock_generate_chat_completion.call_args[0]

    assert actual_args[1] == [
        {"role": "system", "content": "You are Alice, speaking to Bob."},
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
        {"role": "assistant", "content": "Remember, you are Alice."},
    ]

    assert actual_args[2] == {
        "max_tokens": 1000,
        "model": "gpt-4-vision-preview",
    }
