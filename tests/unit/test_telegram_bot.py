from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.cost_tracker import CostTracker
from src.message import Message
from src.simulacrum import Generation
from src.telegram.telegram_bot import TelegramBot

pytestmark = pytest.mark.asyncio


class FakeBotAPI:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, _chat_id, text, **_kwargs) -> None:
        self.sent.append(text)

    async def send_chat_action(self, **_kwargs) -> None:
        pass


@pytest.fixture
def conversation_data() -> dict[str, Any]:
    return {
        "cost": 0.0,
        "messages": [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "<thinking>hm</thinking>\nEarlier reply"},
            {"role": "user", "content": "Second"},
            {"role": "assistant", "content": "Latest reply"},
        ],
    }


@pytest.fixture
def bot(sim):
    bot = TelegramBot.__new__(TelegramBot)
    bot.app = SimpleNamespace(bot=FakeBotAPI())
    bot._token = "12345:SECRET"
    bot.sim = sim
    bot.cost_tracker = CostTracker()
    return bot


@pytest.fixture
def sent(bot) -> list[str]:
    return bot.app.bot.sent


def command(text: str) -> SimpleNamespace:
    message = SimpleNamespace(
        text=text, photo=None, document=None, voice=None, caption=None
    )
    return SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=1))


class TestUndo:
    async def test_reports_status_then_shows_new_last_message(self, bot, sent):
        await bot._undo(command("/undo"), None)

        assert sent == ["`🗑️ Last message undone`", "Earlier reply"]

    async def test_omits_message_when_conversation_is_emptied(self, bot, sent):
        await bot._undo(command("/undo"), None)
        await bot._undo(command("/undo"), None)

        assert sent == [
            "`🗑️ Last message undone`",
            "Earlier reply",
            "`🗑️ Last message undone`",
        ]

    async def test_body_replaces_the_undone_message(self, bot, sent):
        generation = Generation("New reply", "New reply")
        with patch.object(bot.sim, "_generate", AsyncMock(return_value=generation)):
            await bot._undo(command("/undo Actually, this instead"), None)

        assert sent == ["New reply"]
        msgs = bot.sim.context.conversation_messages
        assert [m.content for m in msgs[-2:]] == [
            "Actually, this instead",
            "New reply",
        ]


class TestUndoRetry:
    async def test_reports_status_then_shows_restored_message(self, bot, sent):
        bot.sim.retry_stack.append([Message("assistant", "Original reply")])

        await bot._undo_retry(command("/undoretry"), None)

        assert sent == ["`↩️ Retry undone`", "Original reply"]


class TestRetry:
    async def test_sends_nothing_when_superseded(self, bot, sent):
        with patch.object(bot.sim, "retry", AsyncMock(return_value="")):
            await bot._retry(command("/retry"), None)

        assert sent == []


class TestRequiresBody:
    async def test_command_without_body_reports_usage(self, bot, sent):
        await bot._set_var(command("/set"), None)

        assert "Usage" in sent[0]


class TestContinue:
    async def test_sends_nothing_when_superseded(self, bot, sent):
        with patch.object(bot.sim, "continue_conversation", AsyncMock(return_value="")):
            await bot._continue(command("/continue"), None)

        assert sent == []


class TestApplyPreset:
    async def test_unknown_preset_is_rejected(self, bot, sent):
        await bot._apply_preset(command("/preset nope"), None)

        assert sent[0].startswith("`❌")
        assert bot.sim._pending_instruction is None

    async def test_known_preset_is_queued(self, bot, sent):
        await bot._apply_preset(command("/preset formal"), None)

        assert bot.sim._pending_instruction.content == "Be formal."
        assert sent[0].startswith("`✅")

    async def test_preset_with_message_starts_a_chat(self, bot, sent):
        generation = Generation("Certainly", "Certainly")
        with patch.object(bot.sim, "_generate", AsyncMock(return_value=generation)):
            await bot._apply_preset(command("/preset formal Hello there"), None)

        assert sent == ["Certainly"]
        msgs = bot.sim.context.conversation_messages
        assert "Hello there" in msgs[-2].content
        assert "Be formal." in msgs[-2].content


class TestConversationGuards:
    async def test_new_conversation_clears_messages(self, bot, sent):
        await bot._new_conversation(command("/new"), None)

        assert bot.sim.context.conversation_messages == []
        assert sent[0].startswith("`✅")

    async def test_new_conversation_rejected_when_empty(self, bot, sent):
        with bot.sim.context.session():
            bot.sim.context.conversation_messages.clear()

        await bot._new_conversation(command("/new"), None)

        assert sent[0].startswith("`❌")

    async def test_compact_rejected_when_empty(self, bot, sent):
        with bot.sim.context.session():
            bot.sim.context.conversation_messages.clear()

        await bot._compact_conversation(command("/compact"), None)

        assert sent[0].startswith("`❌")


class TestErrorHandler:
    async def test_redacts_the_bot_token(self, bot, sent):
        error = RuntimeError(f"Request to bot{bot._token} failed")

        await bot._error_handler(command("/undo"), SimpleNamespace(error=error))

        assert bot._token not in sent[0]
        assert "[REDACTED]" in sent[0]
