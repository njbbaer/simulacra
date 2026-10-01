# ruff: noqa: ASYNC230, ASYNC240
import json
import os
from typing import Any

import pytest

from src.lab import (
    Turn,
    combine,
    complete,
    draft,
    parse_tag,
    replay,
    sample_turns,
    take_snapshot,
    totals,
)
from src.lab.replay import _load
from src.request_recorder import RequestRecorder
from src.response_transform import ResponseFormatError
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
    context_data["user_name"] = "Peter"
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


def test_transcript_names_each_speaker(character) -> None:  # noqa: ARG001
    assert Turn(LOG, 3).transcript() == (
        "PETER:\nHi\n\nTEST:\nHello\n\nPETER:\nHow are you?"
    )


def write_log(name: str, drafted: list[int]) -> None:
    messages = [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"m{i}",
            **({"metadata": {"draft": "d"}} if i in drafted else {}),
        }
        for i in range(8)
    ]
    with open(f"characters/test/conversations/{name}", "w") as f:
        yaml.dump({"messages": messages}, f)


def test_samples_drafted_turns_and_reloads_them(character) -> None:  # noqa: ARG001
    write_log("test_1.yml", [1, 3, 5, 7])
    write_log("test_2_named.yml", [5])
    write_log("test_2_named.sync-conflict-20260930-000000-ABC.yml", [7])

    def sample(seed: int) -> list[Turn]:
        return sample_turns(
            "characters",
            {"test": 3},
            seed,
            "turns.json",
            since={"test": 1},
            exclude=["test_1:5"],
        )

    turns = sample(7)

    assert {t.id for t in turns} == {"test_1:3", "test_1:7", "test_2_named:5"}
    assert sample(7) == turns
    with pytest.raises(ValueError, match="was drawn with"):
        sample(8)


def test_snapshot_applies_and_records_edits(character) -> None:  # noqa: ARG001
    turn = Turn(LOG, 1)
    edit = ("characters/test/test.yml", "Remember:", "Recall:")

    pinned = take_snapshot([turn], "/experiment/snapshot", [edit])

    with open(f"{pinned}/characters/test/test.yml") as f:
        assert "Recall: {{" in f.read()
    assert take_snapshot([turn], pinned, [edit]) == pinned
    with pytest.raises(ValueError, match="other edits"):
        take_snapshot([turn], pinned)


def test_snapshot_rejects_an_edit_without_one_match(character) -> None:  # noqa: ARG001
    with pytest.raises(ValueError, match="0 copies"):
        take_snapshot(
            [Turn(LOG, 1)],
            "/experiment/snapshot",
            [("characters/test/test.yml", "Absent", "x")],
        )


@pytest.mark.asyncio
async def test_complete_reports_stats_alongside_drafts(
    character,  # noqa: ARG001
    mock_openrouter,
    mock_completion_response: dict[str, Any],
) -> None:
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=mock_completion_response,
    )
    messages = [
        {"role": "system", "content": "Judge it."},
        {"role": "user", "content": "Hello"},
    ]

    fresh = await draft(Turn(LOG, 1))
    verdict = await complete(messages, "test/judge", "medium", stage="judge")

    body = json.loads(mock_openrouter.get_requests()[1].content)
    assert body["reasoning"] == {"effort": "medium"}
    assert verdict.content == "Something"
    assert verdict.prompts["judge"] is not None
    assert totals(fresh, verdict)["cost"] == pytest.approx(0.2)


def test_parse_tag_raises_a_retryable_error() -> None:
    assert parse_tag("<flags>[1]</flags>", "flags", as_json=True) == [1]
    with pytest.raises(ResponseFormatError):
        parse_tag("<flags>[1,</flags>", "flags", as_json=True)
