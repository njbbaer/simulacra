import pytest

from src.simulacrum import Simulacrum

CONTEXT_FILE = "dummy_context.yml"


@pytest.fixture
def simulacrum_instance():
    return Simulacrum(CONTEXT_FILE)


@pytest.fixture(autouse=True)
def mock_context(mocker):
    return mocker.patch("src.simulacrum.Context")


def test_constructor(simulacrum_instance, mock_context):
    mock_context.assert_called_with(CONTEXT_FILE)
    assert simulacrum_instance.context is not None


@pytest.mark.asyncio
async def test_chat(mocker, simulacrum_instance):
    user_input = "Hello"
    image_url = "http://example.com/photo.jpg"

    mock_chat_executor = mocker.patch("src.simulacrum.ChatExecutor")
    mock_completion = mocker.MagicMock(content="Hello, World!")
    mock_execute = mocker.AsyncMock(return_value=mock_completion)
    mock_chat_executor.return_value.execute = mock_execute

    speech, _ = await simulacrum_instance.chat(user_input, image_url)

    simulacrum_instance.context.load.assert_called()
    simulacrum_instance.context.add_message.assert_any_call(
        "user", user_input, image_url
    )
    mock_chat_executor.assert_called_once_with(simulacrum_instance.context)
    assert speech == "Hello, World!"
    simulacrum_instance.context.add_message.assert_called_with(
        "assistant", mock_completion.content.strip()
    )
    simulacrum_instance.context.save.assert_called()
