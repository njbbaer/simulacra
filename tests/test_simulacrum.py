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

        speech = await simulacrum_instance.chat(user_input, image_url)

        simulacrum_context = simulacrum_instance.context
        mock_chat_executor.assert_called_once_with(simulacrum_context)
        assert speech == "Hello"
        simulacrum_context.load.assert_called()
        simulacrum_context.add_message.assert_any_call("user", user_input, image_url)
        simulacrum_context.add_message.assert_called_with("assistant", "Hello")
        simulacrum_context.save.assert_called()

    @pytest.mark.asyncio
    async def test_new_conversation(self, simulacrum_instance):
        await simulacrum_instance.new_conversation()

        simulacrum_context = simulacrum_instance.context
        assert simulacrum_context.new_conversation.called_with([])

        TestSimulacrum.assert_context_loaded_and_saved(simulacrum_context)
        assert simulacrum_instance.warned_about_cost is False

    def test_clear_messages(self, simulacrum_instance):
        simulacrum_instance.clear_messages(1)

        simulacrum_context = simulacrum_instance.context
        simulacrum_context.clear_messages.assert_called_with(1)
        TestSimulacrum.assert_context_loaded_and_saved(simulacrum_context)

    def test_reset_current_conversation(self, simulacrum_instance):
        simulacrum_instance.reset_current_conversation()

        simulacrum_context = simulacrum_instance.context
        simulacrum_context.reset_current_conversation.assert_called()
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

    def test_add_conversation_fact(self, simulacrum_instance):
        simulacrum_instance.add_conversation_fact("A fact")

        simulacrum_context = simulacrum_instance.context
        simulacrum_context.add_conversation_fact.assert_called_with("A fact")
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
