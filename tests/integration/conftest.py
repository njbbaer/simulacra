import copy
import os
from collections.abc import Callable
from typing import Any

import pytest

from src.lm_executors import ChatExecutor
from src.simulacrum import Simulacrum
from src.yaml_config import yaml


@pytest.fixture
def custom_fs(fs):
    fs.add_real_file(ChatExecutor.TEMPLATE_PATH)
    return fs


@pytest.fixture
def context_data() -> dict[str, Any]:
    return {
        "character_name": "test",
        "total_cost": 0.1,
        "api_params": {"model": "anthropic/claude", "temperature": 0.7},
        "system_prompt": "Say something!",
        "scene_prompt": "Describe the scene.",
        "continue_prompt": "Continue",
    }


@pytest.fixture
def state_data() -> dict[str, Any]:
    return {"conversation_file": "file://./conversations/test_0.yml"}


@pytest.fixture
def conversation_data() -> dict[str, Any]:
    return {
        "cost": 0.1,
        "facts": [],
        "messages": [
            {
                "role": "assistant",
                "content": "Hello user",
            },
        ],
    }


@pytest.fixture
def simulacrum_context(
    custom_fs,  # noqa: ARG001
    context_data: dict[str, Any],
    state_data: dict[str, Any],
    conversation_data: dict[str, Any],
) -> None:
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    with open("test.state.yml", "w") as f:
        yaml.dump(state_data, f)
    os.makedirs("conversations", exist_ok=True)
    with open("conversations/test_0.yml", "w") as f:
        yaml.dump(conversation_data, f)


@pytest.fixture
def simulacrum(simulacrum_context) -> Simulacrum:  # noqa: ARG001
    return Simulacrum("test.yml")


@pytest.fixture
def mock_completion_response() -> dict[str, Any]:
    return {
        "id": "gen-test",
        "provider": "TestProvider",
        "choices": [
            {
                "message": {
                    "content": "Something",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost": 0.1,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }


@pytest.fixture
def mock_openrouter(
    httpx_mock,
    mock_completion_response: dict[str, Any],
):
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=mock_completion_response,
    )
    return httpx_mock


@pytest.fixture
def post_process_simulacrum(
    simulacrum: Simulacrum,
    context_data: dict[str, Any],
) -> Simulacrum:
    context_data["post_process"] = {
        "prompt": "Revise the draft.",
        "api_params": {"model": "test/editor"},
    }
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    return simulacrum


@pytest.fixture
def mock_edited_response(
    mock_openrouter,
    mock_completion_response: dict[str, Any],
):
    edited = copy.deepcopy(mock_completion_response)
    edited["choices"][0]["message"]["content"] = "Edited"
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=edited,
    )
    return mock_openrouter


@pytest.fixture
def trial_simulacrum(
    simulacrum: Simulacrum,
    context_data: dict[str, Any],
) -> Simulacrum:
    context_data["post_process"] = {
        "prompt": "Revise the draft.",
        "api_params": {"model": "test/editor"},
        "candidates": [
            {"api_params": {"model": "test/editor-one"}},
            {"prompt": "Revise the draft harder."},
        ],
    }
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    return simulacrum


@pytest.fixture
def mock_candidate_responses(
    mock_openrouter,
    mock_completion_response: dict[str, Any],
):
    for text in ["First edit", "Second edit"]:
        edited = copy.deepcopy(mock_completion_response)
        edited["choices"][0]["message"]["content"] = text
        mock_openrouter.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=edited,
        )
    return mock_openrouter


@pytest.fixture
def read_trial_log() -> Callable[[], dict[str, Any]]:
    def read() -> dict[str, Any]:
        with open("trials/test_0.yml") as f:
            return yaml.load(f)

    return read
