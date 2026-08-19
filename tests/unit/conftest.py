import os
from typing import Any

import pytest

from src.simulacrum import Simulacrum
from src.yaml_config import yaml


@pytest.fixture
def context_data() -> dict[str, Any]:
    return {
        "character_name": "test",
        "total_cost": 0.0,
        "api_params": {"model": "test/model"},
        "system_prompt": "Hello",
        "instruction_presets": {
            "formal": {
                "content": "Be formal.",
                "name": "Formal Tone",
                "trigger": r"(?i)\bformal\b",
            },
        },
    }


@pytest.fixture
def conversation_data() -> dict[str, Any]:
    return {
        "cost": 0.0,
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
    }


@pytest.fixture
def sim(fs, context_data, conversation_data):
    fs.add_real_file("src/lm_executors/chat_executor_template.j2")
    with open("context.yml", "w") as f:
        yaml.dump(context_data, f)
    with open("context.state.yml", "w") as f:
        yaml.dump({"conversation_file": "file://./conversations/test_0.yml"}, f)
    os.makedirs("conversations", exist_ok=True)
    with open("conversations/test_0.yml", "w") as f:
        yaml.dump(conversation_data, f)
    return Simulacrum("context.yml")
