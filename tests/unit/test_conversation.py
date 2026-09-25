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
        conv.plan_cost = 0.5
        conv.save()

        loaded = _reload()
        assert len(loaded.messages) == 2
        assert loaded.messages[0].role == "user"
        assert loaded.messages[0].content == "Hello"
        assert loaded.messages[1].content == "Hi there"
        assert loaded.cost == pytest.approx(0.05)
        assert loaded.plan_cost == pytest.approx(0.5)

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


class TestRecordModels:
    def test_first_call_fills_header(self, conv):
        assert conv.record_models({"response": "a", "post_process": "b"}) == {}
        assert conv.models == {"response": "a", "post_process": "b"}

    def test_change_returns_marker_and_keeps_header(self, conv):
        conv.record_models({"response": "a"})
        assert conv.record_models({"response": "a"}) == {}
        assert conv.record_models({"response": "b"}) == {"response": "b"}
        assert conv.models == {"response": "a"}

    def test_compares_against_last_marker(self, conv):
        conv.record_models({"response": "a"})
        conv.add_message("assistant", "x", metadata={"models": {"response": "b"}})
        assert conv.record_models({"response": "b"}) == {}
        assert conv.record_models({"response": "a"}) == {"response": "a"}

    def test_missing_header_key_is_filled_later(self, conv):
        conv.record_models({"response": "a"})
        assert conv.record_models({"response": "a", "post_process": "b"}) == {}
        assert conv.models == {"response": "a", "post_process": "b"}

    def test_header_round_trips(self, conv):
        conv.record_models({"response": "a", "post_process": "b"})
        conv.save()
        assert _reload().models == {"response": "a", "post_process": "b"}


class TestConversationReset:
    def test_reset_clears_state(self, conv):
        conv.add_message("user", "Hello")
        conv.cost = 1.0
        conv.vars = {"x": 1}
        conv.memories = ["mem"]
        conv.models = {"response": "a"}
        conv.reset()
        assert conv.messages == []
        assert conv.models == {}
        assert conv.cost == 0.0
        assert conv.vars == {}
        assert conv.memories == []


class TestFormatAsMemory:
    def test_formats_messages(self, conv):
        conv.add_message("user", "Hi")
        conv.add_message("assistant", "Hello")
        result = conv.format_as_memory("Bot")
        assert "---\n\nHi" in result
        assert "BOT:\n\nHello" in result

    def test_strips_tags(self, conv):
        conv.add_message("assistant", "Hello <secret>hidden</secret>world")
        result = conv.format_as_memory("Bot")
        assert "hidden" not in result
        assert "Hello " in result

    def test_skips_empty_content(self, conv):
        conv.add_message("user", "<tag>only tags</tag>")
        result = conv.format_as_memory("Bot")
        assert result == ""


class TestIncrementCost:
    def test_increments(self, conv):
        conv.increment_cost(0.05)
        conv.increment_cost(0.10)
        assert conv.cost == pytest.approx(0.15)


class TestReplaced:
    def _retry(self, conv, content):
        replaced = conv.messages.pop()
        conv.add_message("assistant", content, replacing=replaced)

    def test_restores_through_a_chain_of_retries(self, conv):
        conv.add_message("assistant", "first", metadata={"trial": 1})
        self._retry(conv, "second")
        self._retry(conv, "third")
        conv.save()
        conv = _reload()

        conv.restore_replaced()
        assert conv.messages[-1].content == "second"
        conv.restore_replaced()
        assert conv.messages[-1].content == "first"
        assert conv.messages[-1].metadata == {"trial": 1}
        assert len(conv.messages) == 1

    def test_restores_across_roles(self, conv):
        conv.add_message("user", "old scene", metadata={"scene": True})
        replaced = conv.messages.pop()
        conv.add_message("user", "new scene", replacing=replaced)

        conv.restore_replaced()

        assert [m.content for m in conv.messages] == ["old scene"]

    def test_raises_when_the_last_message_replaced_nothing(self, conv):
        conv.add_message("assistant", "first")
        self._retry(conv, "second")
        conv.add_message("user", "next")

        with pytest.raises(ValueError, match="No retry to undo"):
            conv.restore_replaced()
