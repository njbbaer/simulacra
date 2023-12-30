import pytest

from src.simulacrum import Simulacrum


class TestSimulacrum:
    @pytest.fixture
    def simulacrum_instance(self):
        return Simulacrum("dummy_context.yml")

    @pytest.fixture(autouse=True)
    def mock_context(self, mocker):
        return mocker.patch("src.simulacrum.Context")

    @pytest.fixture
    def mock_chat_executor(self, mocker):
        mock_chat_executor = mocker.patch("src.simulacrum.ChatExecutor")
        mock_chat_executor.return_value.execute = mocker.AsyncMock(
            return_value=mocker.MagicMock(content="Hello")
        )
        return mock_chat_executor

    @pytest.fixture
    def mock_memory_integration_executor(self, mocker):
        mock_executor = mocker.patch("src.simulacrum.MemoryIntegrationExecutor")
        mock_executor.return_value.execute = mocker.AsyncMock(
            return_value=["Memory 1", "Memory 2"]
        )
        return mock_executor

    @staticmethod
    def assert_context_loaded_and_saved(simulacrum_context):
        simulacrum_context.load.assert_called()
        simulacrum_context.save.assert_called()

    def test_constructor(self, simulacrum_instance, mock_context):
        mock_context.assert_called_with("dummy_context.yml")
        assert simulacrum_instance.context is not None

    @pytest.mark.asyncio
    async def test_chat(self, mock_chat_executor, simulacrum_instance):
        user_input = "Hello"
        image_url = "http://example.com/photo.jpg"

        speech, _ = await simulacrum_instance.chat(user_input, image_url)

        simulacrum_context = simulacrum_instance.context
        mock_chat_executor.assert_called_once_with(simulacrum_context)
        assert speech == "Hello"
        simulacrum_context.load.assert_called()
        simulacrum_context.add_message.assert_any_call("user", user_input, image_url)
        simulacrum_context.add_message.assert_called_with("assistant", "Hello")
        simulacrum_context.save.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("integrate_memory", [True, False])
    async def test_new_conversation(
        self, integrate_memory, mock_memory_integration_executor, simulacrum_instance
    ):
        await simulacrum_instance.new_conversation(integrate_memory)

        simulacrum_context = simulacrum_instance.context

        if integrate_memory:
            mock_memory_integration_executor.assert_called_once_with(simulacrum_context)
            assert simulacrum_context.new_conversation.called_with(
                ["Memory #1", "Memory #2"]
            )
        else:
            assert not mock_memory_integration_executor.called
            assert simulacrum_context.new_conversation.called_with([])

        TestSimulacrum.assert_context_loaded_and_saved(simulacrum_context)
        assert simulacrum_instance.warned_about_cost is False

    def test_append_memory(self, simulacrum_instance):
        text = "This is a new memory."
        simulacrum_instance.append_memory(text)

        simulacrum_context = simulacrum_instance.context
        simulacrum_context.append_memory.assert_called_with("\n\n" + text)
        TestSimulacrum.assert_context_loaded_and_saved(simulacrum_context)

    def test_clear_messages(self, simulacrum_instance):
        simulacrum_instance.clear_messages()

        simulacrum_context = simulacrum_instance.context
        simulacrum_context.clear_messages.assert_called_with(None)
        TestSimulacrum.assert_context_loaded_and_saved(simulacrum_context)
        assert simulacrum_instance.warned_about_cost is False

    def test_undo_last_user_message(self, simulacrum_instance):
        messages = [
            {"role": "assistant", "content": "Hello User!"},
            {"role": "user", "content": "Hello Assistant!"},
            {"role": "assistant", "content": "How are you?"},
        ]
        simulacrum_context = simulacrum_instance.context
        simulacrum_context.current_messages = messages

        simulacrum_instance.undo_last_user_message()
        assert simulacrum_context.current_messages == messages[:2]
        TestSimulacrum.assert_context_loaded_and_saved(simulacrum_context)

    def test_has_messages(self, simulacrum_instance):
        simulacrum_context = simulacrum_instance.context
        simulacrum_context.current_messages = []

        assert simulacrum_instance.has_messages() is False
        simulacrum_context.load.assert_called()

        simulacrum_context.current_messages = [
            {"role": "assistant", "content": "Hello!"}
        ]

        assert simulacrum_instance.has_messages() is True

    def test_get_current_conversation_cost(self, simulacrum_instance):
        simulacrum_context = simulacrum_instance.context
        simulacrum_context.current_conversation = {"cost": 0.5}

        assert simulacrum_instance.get_current_conversation_cost() == 0.5
        simulacrum_context.load.assert_called()
