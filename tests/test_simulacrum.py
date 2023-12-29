import pytest

from src.simulacrum import Simulacrum


@pytest.fixture
def simulacrum_instance():
    return Simulacrum("dummy_context.yml")


@pytest.fixture(autouse=True)
def mock_context(mocker):
    return mocker.patch("src.simulacrum.Context")


@pytest.fixture
def mock_chat_executor(mocker):
    mock_chat_executor = mocker.patch("src.simulacrum.ChatExecutor")
    mock_chat_executor.return_value.execute = mocker.AsyncMock(
        return_value=mocker.MagicMock(content="Hello, World!")
    )
    return mock_chat_executor


@pytest.fixture
def mock_memory_integration_executor(mocker):
    mock_executor = mocker.patch("src.simulacrum.MemoryIntegrationExecutor")
    mock_executor.return_value.execute = mocker.AsyncMock(
        return_value=["Memory #1", "Memory #2"]
    )
    return mock_executor


def test_constructor(simulacrum_instance, mock_context):
    mock_context.assert_called_with("dummy_context.yml")
    assert simulacrum_instance.context is not None


@pytest.mark.asyncio
async def test_chat(mock_chat_executor, simulacrum_instance):
    user_input = "Hello"
    image_url = "http://example.com/photo.jpg"

    speech, _ = await simulacrum_instance.chat(user_input, image_url)

    simulacrum_context = simulacrum_instance.context
    mock_chat_executor.assert_called_once_with(simulacrum_context)
    assert speech == "Hello, World!"
    simulacrum_context.load.assert_called()
    simulacrum_context.add_message.assert_any_call("user", user_input, image_url)
    simulacrum_context.add_message.assert_called_with("assistant", "Hello, World!")
    simulacrum_context.save.assert_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("integrate_memory", [True, False])
async def test_new_conversation(
    integrate_memory, mock_memory_integration_executor, simulacrum_instance
):
    await simulacrum_instance.new_conversation(integrate_memory)

    simulacrum_context = simulacrum_instance.context
    simulacrum_context.load.assert_called()

    if integrate_memory:
        mock_memory_integration_executor.assert_called_once_with(simulacrum_context)
        assert simulacrum_context.new_conversation.called_with(
            ["Memory #1", "Memory #2"]
        )
    else:
        assert not mock_memory_integration_executor.called
        assert simulacrum_context.new_conversation.called_with([])

    simulacrum_context.save.assert_called()
    assert simulacrum_instance.warned_about_cost is False
