import pytest

from src.conversation import Conversation
from src.history import (
    History,
    Scope,
    edited_draft,
    layer_values,
    render_turn,
    word_diff,
)
from src.message import Message

CHARACTERS = "/characters"


def _write_log(name: str, number: int) -> Conversation:
    return Conversation(f"{CHARACTERS}/{name}/conversations/{name}_{number}.yml")


@pytest.fixture
def history(fs):
    fs.create_dir(f"{CHARACTERS}/margaret/conversations")
    fs.create_dir(f"{CHARACTERS}/pearl/conversations")
    for number in (2, 10):
        conv = _write_log("margaret", number)
        conv.add_message("user", "(scene)", metadata={"scene": True})
        conv.add_message("user", "Where's the clipboard?")
        conv.add_message(
            "assistant",
            "<character>\nHe wants the clipboard.\n</character>\n\n"
            "<playwright>\nShe points at the clipboard.\n</playwright>\n\n"
            "On the desk.",
            metadata={"feedback": "too curt"},
        )
        conv.save()
    retried = _write_log("pearl", 1)
    retried.add_message("user", "Hello")
    retried.add_message("assistant", "Hi.", metadata={"feedback": "too stiff"})
    retried.add_message(
        "assistant",
        "Hello, Nemo.",
        metadata={"draft": "Hello, Nemo. Lovely day.", "editor_notes": "Cut it."},
        replacing=retried.messages.pop(),
    )
    retried.save()
    unedited = _write_log("pearl", 2)
    unedited.add_message("assistant", "Hi.", metadata={"draft": "Hi."})
    unedited.save()
    return History(CHARACTERS)


def _hits(results):
    return [(f"{log.id}:{index}", lines) for log, index, lines in results if lines]


class TestScope:
    def test_parses_each_level(self):
        assert Scope.parse("margaret") == Scope("margaret")
        assert Scope.parse("margaret_238") == Scope("margaret", 238)
        assert Scope.parse("margaret_238:12") == Scope("margaret", 238, 12)

    def test_parses_a_named_conversation(self):
        assert Scope.parse("margaret_238_dinner:4") == Scope("margaret", 238, 4)

    def test_rejects_other_text(self):
        with pytest.raises(ValueError, match="Not a character"):
            Scope.parse("Clipboard")


class TestSearch:
    def test_text_matches_what_was_shown_but_not_thoughts(self, history):
        hits = _hits(history.search("clipboard", [Scope("margaret")]))
        assert hits == [
            ("margaret_2:1", ["Where's the clipboard?"]),
            ("margaret_10:1", ["Where's the clipboard?"]),
        ]

    def test_character_and_playwright_layers_split_the_tagged_blocks(self, history):
        scope = [Scope("margaret", 10)]
        hits = _hits(history.search("clipboard", scope, layer="playwright"))
        assert hits == [("margaret_10:2", ["She points at the clipboard."])]
        hits = _hits(history.search("clipboard", scope, layer="character"))
        assert hits == [("margaret_10:2", ["He wants the clipboard."])]

    def test_edits_layer_matches_what_the_editor_cut(self, history):
        hits = _hits(history.search(r"\[-Lovely", [Scope("pearl")], layer="edits"))
        assert hits == [("pearl_1:1", ["Hello, Nemo. [-Lovely day.-]"])]

    def test_edits_layer_searches_unchanged_drafts_for_the_edit_rate(self, history):
        results = history.search(r"\[-", [Scope("pearl")], layer="edits")
        assert [(log.id, lines) for log, _, lines in results] == [
            ("pearl_1", ["Hello, Nemo. [-Lovely day.-]"]),
            ("pearl_2", []),
        ]

    def test_feedback_layer_includes_replaced_attempts(self, history):
        hits = _hits(history.search(None, layer="feedback"))
        assert hits == [
            ("margaret_2:2", ["too curt"]),
            ("margaret_10:2", ["too curt"]),
            ("pearl_1:1", ["too stiff"]),
        ]

    def test_kind_separates_scenes_from_user_messages(self, history):
        hits = _hits(history.search(None, [Scope("margaret", 2)], kind="scene"))
        assert hits == [("margaret_2:0", ["(scene)"])]

    def test_since_skips_earlier_conversations(self, history):
        hits = _hits(history.search("desk", [Scope("margaret")], since=3))
        assert [hit_id for hit_id, _ in hits] == ["margaret_10:2"]

    def test_yields_searched_messages_without_matches_for_counting(self, history):
        scope = [Scope("margaret", 2)]
        results = history.search("desk", scope, kind="assistant")
        assert [(i, lines) for _, i, lines in results] == [(2, ["On the desk."])]
        results = history.search("nowhere", scope)
        assert [lines for _, _, lines in results] == [[], [], []]


class TestShow:
    def test_latest_conversation_is_by_number(self, history):
        assert history.log(Scope("margaret")).id == "margaret_10"

    def test_turn_shows_the_edit_and_the_attempt_it_replaced(self, history):
        log = history.log(Scope("pearl", 1))
        assert render_turn(log, 1) == (
            "── pearl_1:0  user\nHello\n\n"
            "══ pearl_1:1  assistant  retried 1x  feedback\nHello, Nemo.\n\n"
            "── edits\nHello, Nemo. [-Lovely day.-]\n\n"
            "── editor\nCut it.\n\n"
            "── replaced 1 of 1\nfeedback: too stiff\nHi.\n"
        )


def test_word_diff_skips_unchanged_paragraphs():
    old = "Same.\n\nShe cuts this, keeping that."
    new = "Same.\n\nShe cuts, keeping that."
    assert word_diff(old, new) == "She [-cuts this,-] {+cuts,+} keeping that."


def test_edited_draft_is_the_closest_one():
    drafts = ["Something else entirely.", "Hello, Nemo. Lovely day."]
    message = Message("assistant", "Hello, Nemo.", metadata={"drafts": drafts})
    assert edited_draft(message) == (2, "Hello, Nemo. Lovely day.")


def test_layers_read_older_tag_names():
    content = (
        "<think_character>\nA\n</think_character>\n\n<thinking>\nB\n</thinking>\n\n"
        "<think_playwright>\nC\n</think_playwright>\n\n<note>\nD\n</note>\n\n"
        "<character_response>\nE\n</character_response>"
    )
    message = Message("assistant", content)
    assert layer_values(message, "character") == ["A"]
    assert layer_values(message, "playwright") == ["C", "D"]
    assert layer_values(message, "text") == ["E"]
