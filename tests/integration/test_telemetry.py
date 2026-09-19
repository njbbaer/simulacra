# ruff: noqa: ASYNC230
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.simulacrum import Simulacrum
from src.telemetry import Telemetry
from src.yaml_config import yaml


@pytest.fixture
def telemetry_simulacrum(
    post_process_simulacrum: Simulacrum,  # noqa: ARG001
) -> Simulacrum:
    return Simulacrum("test.yml", telemetry=Telemetry.for_deployment("/base", "prod"))


def read_rows() -> list[dict[str, Any]]:
    with open("/base/telemetry.jsonl") as f:
        return [json.loads(line) for line in f]


@pytest.mark.asyncio
async def test_records_every_request_and_the_turn(
    telemetry_simulacrum: Simulacrum,
    mock_edited_response,  # noqa: ARG001
) -> None:
    await telemetry_simulacrum.chat("Hello assistant", None, None)

    rows = read_rows()
    assert [(row["kind"], row["status"]) for row in rows] == [
        ("request", "ok"),
        ("request", "ok"),
        ("turn", "ok"),
    ]
    assert len({row["turn"] for row in rows}) == 1
    assert all(row["character"] == "test" for row in rows)
    assert all(row["conversation"] == 0 for row in rows)
    assert all(row["deployment"] == "prod" for row in rows)
    assert all(row["action"] == "chat" for row in rows)

    draft, edit, turn = rows
    assert (draft["stage"], draft["model"]) == ("response", "anthropic/claude")
    assert (edit["stage"], edit["model"]) == ("post_process", "test/editor")
    assert draft["candidate"] is None
    assert draft["draft"] is None
    assert draft["generation_id"] == "gen-test"
    assert draft["provider"] == "TestProvider"
    assert draft["prompt_tokens"] == 10
    assert draft["cached_tokens"] == 0
    assert draft["cost"] == 0.1
    assert draft["chars"] == len("Something")
    assert turn["cost"] == pytest.approx(0.2)
    assert turn["chars"] == len("Edited")


@pytest.mark.asyncio
async def test_records_candidates_and_drafts(
    telemetry_simulacrum: Simulacrum,
    context_data: dict[str, Any],
    mock_openrouter,
    mock_completion_response: dict[str, Any],
) -> None:
    context_data["post_process"]["drafts"] = 2
    context_data["post_process"]["candidates"] = [
        {"api_params": {"model": "test/editor-one"}},
        {"prompt": "Revise the draft harder."},
    ]
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    for _ in range(3):
        mock_openrouter.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=mock_completion_response,
        )

    await telemetry_simulacrum.retry()

    rows = [row for row in read_rows() if row["kind"] == "request"]
    assert sorted((row["stage"], row["candidate"], row["draft"]) for row in rows) == [
        ("post_process", "A", None),
        ("post_process", "B", None),
        ("response", None, 1),
        ("response", None, 2),
    ]
    assert all(row["action"] == "retry" for row in rows)


@pytest.mark.asyncio
async def test_records_a_failed_request_and_turn(
    telemetry_simulacrum: Simulacrum,
    mock_openrouter,
    mock_completion_response: dict[str, Any],
) -> None:
    mock_completion_response["choices"][0]["message"]["content"] = ""
    mock_openrouter.reset()
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=mock_completion_response,
    )

    with pytest.raises(RuntimeError, match="Response was empty"):
        await telemetry_simulacrum.chat("Hello assistant", None, None)

    rows = read_rows()
    assert [(row["kind"], row["status"]) for row in rows] == [
        ("request", "error"),
        ("turn", "error"),
    ]
    assert rows[0]["error"] == "RuntimeError: Response was empty"
    assert "cost" not in rows[0]


@pytest.mark.asyncio
async def test_records_nothing_without_telemetry(
    post_process_simulacrum: Simulacrum,
    mock_edited_response,  # noqa: ARG001
    fs,
) -> None:
    await post_process_simulacrum.chat("Hello assistant", None, None)
    assert not fs.exists("/base")


@pytest.mark.asyncio
async def test_counts_http_retries_within_the_request(
    telemetry_simulacrum: Simulacrum,
    mock_openrouter,
    mock_completion_response: dict[str, Any],
) -> None:
    mock_openrouter.reset()
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions", status_code=500, json={}
    )
    for _ in range(2):
        mock_openrouter.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=mock_completion_response,
        )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await telemetry_simulacrum.chat("Hello assistant", None, None)

    draft, edit, turn = read_rows()
    assert (draft["status"], draft["attempts"]) == ("ok", 2)
    assert edit["status"] == "ok"
    assert "attempts" not in edit
    assert "attempts" not in turn
