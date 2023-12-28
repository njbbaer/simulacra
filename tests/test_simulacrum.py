from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.simulacrum import Simulacrum

CONTEXT_FILE = "dummy_context.yml"


@pytest.fixture
def simulacrum_instance():
    return Simulacrum(CONTEXT_FILE)


@pytest.fixture
def context_instance(mock_context):
    return mock_context.return_value


@pytest.fixture(autouse=True)
def mock_context():
    with patch("src.simulacrum.Context") as mock:
        yield mock


def test_constructor(simulacrum_instance, mock_context):
    mock_context.assert_called_with(CONTEXT_FILE)
    assert simulacrum_instance.context is not None


@pytest.mark.asyncio
@patch("src.simulacrum.ChatExecutor")
async def test_chat(mock_chat_executor, simulacrum_instance, context_instance):
    user_input = "Hello"
    photo_url = "http://example.com/photo.jpg"
    mock_execute = AsyncMock()
    mock_completion = MagicMock(content="Hello, World!")
    mock_execute.return_value = mock_completion
    mock_chat_executor.return_value.execute = mock_execute

    speech, _ = await simulacrum_instance.chat(user_input, photo_url)

    context_instance.load.assert_called()
    context_instance.add_message.assert_any_call("user", user_input, photo_url)
    mock_chat_executor.assert_called_once_with(context_instance)
    assert speech == "Hello, World!"
    context_instance.add_message.assert_called_with(
        "assistant", mock_completion.content.strip()
    )
    context_instance.save.assert_called()
