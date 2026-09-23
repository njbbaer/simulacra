from src.turn_stats import TurnStats, format_stats


def request(**overrides) -> dict:
    return {
        "stage": "response",
        "candidate": None,
        "draft": None,
        "model": "moonshotai/kimi-k3",
        "provider": "BaseTen",
        "duration_ms": 3641,
        "prompt_tokens": 5788,
        "cached_tokens": 0,
        "completion_tokens": 220,
        "reasoning_tokens": 0,
        "cost": 0.020664,
        "plan_cost": 0.0,
        **overrides,
    }


def test_without_a_turn_shows_only_the_conversation():
    assert format_stats(None, 204, 37, 4.123, 0.0) == (
        "*Conversation* · #204 · 37 messages · $4.12"
    )


def test_drafts_are_sorted_and_stages_are_grouped():
    turn = TurnStats(
        "retry",
        duration_ms=9672,
        requests=[
            request(draft=2, duration_ms=4916, completion_tokens=261, cost=0.021279),
            request(draft=1),
            request(
                stage="post_process",
                model="z-ai/glm-5.3",
                duration_ms=4743,
                prompt_tokens=6863,
                completion_tokens=1199,
                reasoning_tokens=851,
                cost=0.0223257,
            ),
        ],
    )

    assert format_stats(turn, 204, 37, 4.12, 0.0) == "\n".join(
        [
            "*Turn* · retry · 9.7s · $0.064",
            "",
            "*Response* · kimi-k3 · BaseTen · 5.8k prompt",
            "Draft 1 · 3.6s · 220 tokens · $0.021",
            "Draft 2 · 4.9s · 261 tokens · $0.021",
            "",
            "*Post-process* · glm-5.3 · BaseTen · 6.9k prompt",
            "4.7s · 1.2k tokens, 851 reasoning · $0.022",
            "",
            "*Conversation* · #204 · 37 messages · $4.12",
        ]
    )


def test_shared_cache_rate_moves_to_the_heading():
    turn = TurnStats(
        "chat",
        requests=[
            request(draft=1, cached_tokens=5788),
            request(draft=2, cached_tokens=5788),
        ],
    )

    lines = format_stats(turn, 1, 2, 0.0, 0.0).splitlines()

    assert lines[2] == "*Response* · kimi-k3 · BaseTen · 5.8k prompt, 100% cached"
    assert lines[3] == "Draft 1 · 3.6s · 220 tokens · $0.021"


def test_candidates_keep_differing_prompts_providers_and_retries_on_the_line():
    turn = TurnStats(
        "chat",
        requests=[
            request(candidate="A", draft=1, cached_tokens=4100, attempts=3),
            request(candidate="B", prompt_tokens=6000, provider="Fireworks"),
        ],
    )

    lines = format_stats(turn, 1, 2, 0.0, 0.0).splitlines()

    assert lines[2] == "*Response* · kimi-k3"
    assert lines[3] == (
        "A · Draft 1 · 3.6s · 5.8k prompt, 71% cached · 220 tokens"
        " · 3 attempts · BaseTen · $0.021"
    )
    assert lines[4] == "B · 3.6s · 6.0k prompt · 220 tokens · Fireworks · $0.021"


def test_turn_cost_sums_every_request():
    turn = TurnStats("chat", requests=[request(cost=0.1), request(cost=0.25)])

    assert turn.cost == 0.35


def test_plan_cost_is_shown_beside_money_and_replaces_a_zero_cost():
    turn = TurnStats(
        "reply",
        duration_ms=5000,
        requests=[
            request(
                stage="response",
                model="agent-sdk/claude-opus-5-5",
                provider="Agent SDK",
                cost=0.0,
                plan_cost=0.4123,
            ),
            request(stage="post_process"),
        ],
    )

    lines = format_stats(turn, 1, 2, 1.5, 8.25).splitlines()

    assert lines[0] == "*Turn* · reply · 5.0s · $0.021 · plan $0.412"
    assert lines[3].endswith("220 tokens · plan $0.412")
    assert lines[6].endswith("220 tokens · $0.021")
    assert lines[-1] == "*Conversation* · #1 · 2 messages · $1.50 · plan $8.25"


def plan_usage(five_hour: float, resets_in: float) -> dict:
    return {
        "five_hour": {"utilization": five_hour, "resets_at": 1000 + resets_in},
        "seven_day": {"utilization": 0.38, "resets_at": 1000 + 187_200},
    }


def test_plan_usage_from_the_latest_request_is_shown_last():
    turn = TurnStats(
        "chat",
        requests=[
            request(draft=1, plan_usage=plan_usage(0.04, 11_520)),
            request(draft=2, plan_usage=plan_usage(0.05, 11_520)),
        ],
    )

    lines = format_stats(turn, 1, 2, 0.0, 0.0, now=1000).splitlines()

    assert lines[-3:] == [
        "*Claude Plan*",
        "5-hour · 5% · resets in 3h 12m",
        "Weekly · 38% · resets in 2d 4h",
    ]


def test_plan_window_that_has_since_reset_drops_its_stale_utilization():
    turn = TurnStats("chat", requests=[request(plan_usage=plan_usage(0.9, -60))])

    lines = format_stats(turn, 1, 2, 0.0, 0.0, now=1000).splitlines()

    assert lines[-2] == "5-hour · reset since last request"
