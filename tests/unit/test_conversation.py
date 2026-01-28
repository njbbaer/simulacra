import pytest

from src.conversation import Conversation


@pytest.fixture()
def conv(fs):
    fs.create_dir("/data")
    return Conversation("/data/conv.yaml")


def _reload():
    return Conversation("/data/conv.yaml")


class TestConversationRoundTrip:
    def test_save_and_load(self, conv):
        conv.add_message("user", "Hello")
        conv.add_message("assistant", "Hi there")
        conv.cost = 0.05
        conv.save()

        loaded = _reload()
        assert len(loaded.messages) == 2
        assert loaded.messages[0].role == "user"
        assert loaded.messages[0].content == "Hello"
        assert loaded.messages[1].content == "Hi there"
        assert loaded.cost == pytest.approx(0.05)

    def test_save_with_vars(self, conv):
        conv.set_var("mood", "happy")
        conv.save()

        loaded = _reload()
        assert loaded.vars == {"mood": "happy"}

    def test_save_with_memories(self, conv):
        conv.memories = ["I like cats"]
        conv.save()

        loaded = _reload()
        assert loaded.memories == ["I like cats"]


class TestConversationReset:
    def test_reset_clears_state(self, conv):
        conv.add_message("user", "Hello")
        conv.cost = 1.0
        conv.vars = {"x": 1}
        conv.memories = ["mem"]
        conv.reset()
        assert conv.messages == []
        assert conv.cost == 0.0
        assert conv.vars == {}
        assert conv.memories == []


class TestFormatAsMemory:
    def test_formats_messages(self, conv):
        conv.add_message("user", "Hi")
        conv.add_message("assistant", "Hello")
        result = conv.format_as_memory("Bot", "User")
        assert "USER:\n\nHi" in result
        assert "BOT:\n\nHello" in result

    def test_strips_tags(self, conv):
        conv.add_message("assistant", "Hello <secret>hidden</secret>world")
        result = conv.format_as_memory("Bot", "User")
        assert "hidden" not in result
        assert "Hello " in result

    def test_skips_empty_content(self, conv):
        conv.add_message("user", "<tag>only tags</tag>")
        result = conv.format_as_memory("Bot", "User")
        assert result == ""


class TestIncrementCost:
    def test_increments(self, conv):
        conv.increment_cost(0.05)
        conv.increment_cost(0.10)
        assert conv.cost == pytest.approx(0.15)
