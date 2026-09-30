# ruff: noqa: ASYNC230, ASYNC240
import json
import os
from typing import Any

import pytest

from src.lab import Turn, combine, draft, replay, take_snapshot
from src.lab.replay import _load
from src.request_recorder import RequestRecorder
from src.yaml_config import yaml

LOG = "characters/test/conversations/test_0.yml"


@pytest.fixture(autouse=True)
def clear_log_cache():
    _load.cache_clear()


@pytest.fixture
def character(
    custom_fs,  # noqa: ARG001
    context_data: dict[str, Any],
    state_data: dict[str, Any],
) -> None:
    context_data["system_prompt"] = "Remember: {{ memories | join(', ') }}"
    context_data["post_process"] = {
        "prompt": "Revise the draft.",
        "api_params": {"model": "test/editor"},
    }
    os.makedirs("characters/test/conversations")
    os.makedirs("shared")
    with open("characters/test/test.yml", "w") as f:
        yaml.dump(context_data, f)
    with open("characters/test/test.state.yml", "w") as f:
        yaml.dump(state_data, f)
    with open(LOG, "w") as f:
        yaml.dump(
            {
                "memories": ["the lighthouse"],
                "messages": [
                    {"role": "user", "content": "Hi"},
                    {
                        "role": "assistant",
                        "content": "Hello",
                        "metadata": {"draft": "Hello there"},
                    },
                    {"role": "user", "content": "How are you?"},
                    {"role": "assistant", "content": "Fine"},
                ],
            },
            f,
        )


def texts(request) -> list[tuple[str, str]]:
    body = json.loads(request.content)
    return [(m["role"], m["content"][0]["text"]) for m in body["messages"]]


@pytest.mark.asyncio
async def test_replays_turn_from_the_messages_before_it(
    character,  # noqa: ARG001
    mock_edited_response,
) -> None:
    result = await replay(Turn(LOG, 1))

    draft_request, edit_request = mock_edited_response.get_requests()
    assert texts(draft_request) == [
        ("system", "Remember: the lighthouse"),
        ("user", "Hi"),
    ]
    assert json.loads(edit_request.content)["model"] == "test/editor"
    assert result.display == "Edited"
    assert result.drafts == ["Something"]
    assert result.to_dict()["cost"] == pytest.approx(0.2)
    assert not os.path.exists(RequestRecorder.FILEPATH)


@pytest.mark.asyncio
async def test_edits_given_drafts_without_drafting(
    character,  # noqa: ARG001
    mock_openrouter,
) -> None:
    turn = Turn(LOG, 1)
    result = await replay(
        turn,
        {"post_process": {"api_params": {"model": "test/other"}}},
        drafts=turn.drafts,
    )

    (request,) = mock_openrouter.get_requests()
    assert json.loads(request.content)["model"] == "test/other"
    assert texts(request)[-2:] == [
        ("assistant", "<draft>\nHello there\n</draft>"),
        ("user", "<instruct>\nRevise the draft.\n</instruct>"),
    ]
    assert result.display == "Something"


@pytest.mark.asyncio
async def test_leaves_the_log_unchanged(
    character,  # noqa: ARG001
    mock_edited_response,  # noqa: ARG001
) -> None:
    with open(LOG) as f:
        before = f.read()

    await replay(Turn(LOG, 3))

    with open(LOG) as f:
        assert f.read() == before


def test_rejects_a_user_message(character) -> None:  # noqa: ARG001
    with pytest.raises(ValueError, match="test_0:2 is not an assistant message"):
        Turn(LOG, 2)


@pytest.mark.asyncio
async def test_rejects_drafts_without_an_editor(
    character,  # noqa: ARG001
) -> None:
    with pytest.raises(ValueError, match="post-processing prompt"):
        await replay(Turn(LOG, 1), {"post_process": {"prompt": None}}, drafts=["Hello"])


@pytest.mark.asyncio
async def test_drafts_without_the_editor(
    character,  # noqa: ARG001
    mock_openrouter,
) -> None:
    result = await draft(Turn(LOG, 1))

    assert len(mock_openrouter.get_requests()) == 1
    assert result.content == "Something"
    assert result.prompts["editor"] is None


@pytest.mark.asyncio
async def test_combine_keeps_the_last_output_and_all_stats(
    character,  # noqa: ARG001
    mock_edited_response,  # noqa: ARG001
) -> None:
    turn = Turn(LOG, 1)
    fresh = await draft(turn)
    edited = await replay(turn, drafts=[fresh.content])

    combined = combine(fresh, edited).to_dict()

    assert combined["display"] == "Edited"
    assert combined["cost"] == pytest.approx(0.2)
    assert combined["prompts"]["editor"] == edited.prompts["editor"]


@pytest.mark.asyncio
async def test_snapshot_pins_character_files(
    character,  # noqa: ARG001
    context_data: dict[str, Any],
    mock_openrouter,
    mock_completion_response: dict[str, Any],
) -> None:
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=mock_completion_response,
    )
    turn = Turn(LOG, 1)
    pinned = take_snapshot([turn], "/experiment/snapshot")
    context_data["system_prompt"] = "Edited while the batch ran"
    with open("characters/test/test.yml", "w") as f:
        yaml.dump(context_data, f)

    snapshot_result = await draft(turn, snapshot=pinned)
    live_result = await draft(turn)

    first, second = mock_openrouter.get_requests()
    assert texts(first)[0] == ("system", "Remember: the lighthouse")
    assert texts(second)[0] == ("system", "Edited while the batch ran")
    assert snapshot_result.prompts["system"] != live_result.prompts["system"]
    assert take_snapshot([turn], pinned) == pinned
