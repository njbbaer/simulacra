import pytest

from src.conversation_files import ConversationFiles


@pytest.fixture
def conv_files(fs):
    fs.create_dir("/test/conversations")
    fs.create_file("/test/conversations/alice_1.yml")
    fs.create_file("/test/conversations/alice_2_adventure.yml")
    fs.create_file("/test/conversations/alice_3_adventure.yml")
    fs.create_file("/test/conversations/alice_4_quest.yml")
    return ConversationFiles("/test/conversations", "Alice")


class TestFind:
    def test_find_by_id(self, conv_files):
        conv = conv_files.find("2")
        assert conv.id == 2
        assert conv.name == "adventure"

    def test_find_by_name_returns_highest_id(self, conv_files):
        conv = conv_files.find("adventure")
        assert conv.id == 3
        assert conv.name == "adventure"

    def test_find_by_id_not_found(self, conv_files):
        with pytest.raises(ValueError, match="No conversation with ID '99'"):
            conv_files.find("99")

    def test_find_by_name_not_found(self, conv_files):
        with pytest.raises(ValueError, match="No conversation named 'unknown'"):
            conv_files.find("unknown")

    def test_find_by_name_case_insensitive(self, conv_files):
        conv = conv_files.find("ADVENTURE")
        assert conv.id == 3


class TestSanitizeName:
    @pytest.fixture
    def conv_files(self):
        return ConversationFiles("/unused", "Alice")

    def test_lowercases_and_replaces_spaces(self, conv_files):
        assert conv_files.sanitize_name("My Quest") == "my_quest"

    def test_removes_special_characters(self, conv_files):
        assert conv_files.sanitize_name("test@#$123") == "test123"

    def test_raises_on_empty_result(self, conv_files):
        with pytest.raises(ValueError, match="alphanumeric"):
            conv_files.sanitize_name("@#$%")


class TestList:
    def test_returns_all_conversations(self, conv_files):
        convs = conv_files.list()
        assert len(convs) == 4
        ids = {c.id for c in convs}
        assert ids == {1, 2, 3, 4}

    def test_next_id_returns_max_plus_one(self, conv_files):
        assert conv_files.next_id() == 5


class TestRename:
    def test_renames_file_and_returns_new_name(self, conv_files):
        new_filename, sanitized = conv_files.rename("alice_1.yml", "new name")
        assert new_filename == "alice_1_new_name.yml"
        assert sanitized == "new_name"

    def test_raises_on_invalid_filename(self, conv_files):
        with pytest.raises(ValueError, match="Invalid filename"):
            conv_files.rename("invalid.yml", "test")
