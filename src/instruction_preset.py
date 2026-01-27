import re
from dataclasses import dataclass


@dataclass
class InstructionPreset:
    content: str
    trigger: str | None = None
    name: str | None = None
    overrides: dict | None = None

    def matches(self, text: str) -> bool:
        if not self.trigger:
            return False
        return re.search(self.trigger, text, re.IGNORECASE) is not None

    @staticmethod
    def find_match(
        presets: dict[str, "InstructionPreset"],
        text: str,
        triggered: list[str],
    ) -> tuple[str, "InstructionPreset"] | None:
        for key, preset in presets.items():
            if key not in triggered and preset.matches(text):
                return key, preset
        return None

    @staticmethod
    def from_dict(data: dict[str, dict]) -> dict[str, "InstructionPreset"]:
        return {
            key: InstructionPreset(
                content=preset["content"],
                trigger=preset.get("trigger"),
                name=preset.get("name"),
                overrides=preset.get("overrides"),
            )
            for key, preset in data.items()
        }
