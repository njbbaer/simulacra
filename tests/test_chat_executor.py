import pytest

from src.executors.chat_executor import ChatExecutor


@pytest.fixture
def mock_context(mocker):
    mock_instance = mocker.patch("src.context.Context").return_value
    mock_instance.vars = {}
    mock_instance.current_memory = None
    mock_instance.chat_prompt = "You are Alice, speaking to Bob."
    mock_instance.reinforcement_chat_prompt = "Remember, you are Alice."
    mock_instance.current_messages = [
        {"role": "assistant", "content": "Hello, Bob."},
        {"role": "user", "content": "Hi, Alice."},
    ]
    return mock_instance


@pytest.fixture
def mock_generate_chat_completion(mocker):
    completion_mock = mocker.Mock()
    completion_mock.cost = 0.25
    async_mock = mocker.AsyncMock(return_value=completion_mock)
    mocker.patch("src.completion.ChatCompletion.generate", new=async_mock)
    return async_mock


@pytest.mark.asyncio
async def test_execute(mock_context, mock_generate_chat_completion):
    await ChatExecutor(mock_context).execute()
    mock_generate_chat_completion.assert_called_once_with(
        [
            {"role": "system", "content": "You are Alice, speaking to Bob."},
            {"role": "assistant", "content": "Hello, Bob."},
            {"role": "user", "content": "Hi, Alice."},
            {"role": "system", "content": "Remember, you are Alice."},
        ],
        {"model": "gpt-4-vision-preview", "max_tokens": 1000},
    )
