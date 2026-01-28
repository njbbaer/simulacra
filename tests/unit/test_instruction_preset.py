from src.instruction_preset import InstructionPreset


class TestMatches:
    def test_matches_trigger(self):
        preset = InstructionPreset(content="x", trigger=r"hello")
        assert preset.matches("say hello world") is True

    def test_no_match(self):
        preset = InstructionPreset(content="x", trigger=r"hello")
        assert preset.matches("goodbye") is False

    def test_case_insensitive(self):
        preset = InstructionPreset(content="x", trigger=r"hello")
        assert preset.matches("HELLO") is True

    def test_no_trigger_never_matches(self):
        preset = InstructionPreset(content="x")
        assert preset.matches("anything") is False

    def test_regex_trigger(self):
        preset = InstructionPreset(content="x", trigger=r"\d{3}")
        assert preset.matches("code 123 here") is True
        assert preset.matches("no digits") is False


class TestFindMatch:
    def test_finds_first_match(self):
        presets = InstructionPreset.from_dict(
            {
                "a": {"content": "ca", "trigger": "hello"},
                "b": {"content": "cb", "trigger": "world"},
            }
        )
        result = InstructionPreset.find_match(presets, "hello world", [])
        assert result is not None
        assert result[0] == "a"

    def test_skips_already_triggered(self):
        presets = InstructionPreset.from_dict(
            {
                "a": {"content": "ca", "trigger": "hello"},
                "b": {"content": "cb", "trigger": "hello"},
            }
        )
        result = InstructionPreset.find_match(presets, "hello", ["a"])
        assert result is not None
        assert result[0] == "b"

    def test_returns_none_when_no_match(self):
        presets = InstructionPreset.from_dict(
            {
                "a": {"content": "ca", "trigger": "hello"},
            }
        )
        assert InstructionPreset.find_match(presets, "goodbye", []) is None

    def test_returns_none_when_all_triggered(self):
        presets = InstructionPreset.from_dict(
            {
                "a": {"content": "ca", "trigger": "hello"},
            }
        )
        assert InstructionPreset.find_match(presets, "hello", ["a"]) is None


class TestFromDict:
    def test_parses_all_fields(self):
        presets = InstructionPreset.from_dict(
            {
                "x": {
                    "content": "do stuff",
                    "trigger": "go",
                    "name": "Go Preset",
                    "overrides": {"key": "val"},
                }
            }
        )
        p = presets["x"]
        assert p.content == "do stuff"
        assert p.trigger == "go"
        assert p.name == "Go Preset"
        assert p.overrides == {"key": "val"}

    def test_optional_fields_default_none(self):
        presets = InstructionPreset.from_dict({"x": {"content": "c"}})
        p = presets["x"]
        assert p.trigger is None
        assert p.name is None
        assert p.overrides is None
