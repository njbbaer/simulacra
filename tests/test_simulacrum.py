import pytest

from src.simulacrum import Simulacrum
from src.yaml_config import yaml


@pytest.fixture
def custom_fs(fs):
    fs.add_real_file("src/lm_executors/chat_executor_template.j2")
    return fs


@pytest.fixture
def simulacrum_context(custom_fs):
    context_path = "context.yml"
    context_data = {
        "char_name": "my-character",
        "model": "anthropic/claude-3.7-sonnet",
        "total_cost": 0,
        "vars": {
            "chat_prompt": "Say something!",
        },
    }
    with open(context_path, "w") as f:
        yaml.dump(context_data, f)
    return context_path


@pytest.fixture
def simulacrum(simulacrum_context):
    return Simulacrum(simulacrum_context)


@pytest.fixture
def mock_openrouter(httpx_mock):
    gen_id = "gen-4567291038-XpT8aKfqs2wRvZyLmEgC"
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json={
            "id": gen_id,
            "choices": [
                {
                    "message": {
                        "content": "Something",
                    },
                }
            ],
        },
    )
    httpx_mock.add_response(
        url=f"https://openrouter.ai/api/v1/generation?id={gen_id}",
        json={"data": {"total_cost": 0.01}},
    )
    return httpx_mock


@pytest.mark.asyncio
async def test_simulacrum_chat(simulacrum, mock_openrouter):
    await simulacrum.chat("Hello", None, None)
    assert mock_openrouter.get_requests(
        url="https://openrouter.ai/api/v1/chat/completions"
    )
    assert mock_openrouter.get_requests(
        url="https://openrouter.ai/api/v1/generation?id=gen-4567291038-XpT8aKfqs2wRvZyLmEgC"
    )
