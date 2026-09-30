import asyncio
import json
from typing import Any

import pytest

from src.lab import run_batch
from src.response_transform import ResponseFormatError


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr("src.lab.batch.RETRY_SECONDS", 0)


@pytest.fixture
def out(tmp_path) -> str:
    return str(tmp_path / "results.jsonl")


def read(path: str) -> list[dict[str, Any]]:
    with open(path) as f:
        return [json.loads(line) for line in f]


def jobs(n: int) -> list[dict[str, Any]]:
    return [{"turn": f"t{i}"} for i in range(n)]


@pytest.mark.asyncio
async def test_appends_results_and_skips_done_jobs_on_rerun(out: str) -> None:
    calls = []

    async def fn(job):
        calls.append(job["turn"])
        return {"text": job["turn"].upper()}

    await run_batch(jobs(2), fn, out)
    summary = await run_batch(jobs(3), fn, out)

    assert calls == ["t0", "t1", "t2"]
    assert summary.ok == 1
    assert read(out)[2] == {"job": {"turn": "t2"}, "text": "T2"}


@pytest.mark.asyncio
async def test_retries_api_errors(out: str) -> None:
    attempts = 0

    async def fn(_):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("rate limited")
        return {}

    summary = await run_batch(jobs(1), fn, out)

    assert attempts == 3
    assert summary.ok == 1


@pytest.mark.asyncio
async def test_aborts_on_a_local_error_without_retrying(out: str) -> None:
    calls = 0

    async def fn(_):
        nonlocal calls
        calls += 1
        raise KeyError("points")

    summary = await run_batch(jobs(3), fn, out, concurrency=1)

    assert calls == 1
    assert summary.aborted is not None
    assert "KeyError" in summary.aborted


@pytest.mark.asyncio
async def test_aborts_on_a_plain_value_error(out: str) -> None:
    async def fn(_):
        raise ValueError("Unsupported by the Agent SDK: top_k")

    summary = await run_batch(jobs(3), fn, out, concurrency=1)

    assert summary.failed == 0
    assert summary.aborted is not None


@pytest.mark.asyncio
async def test_retries_malformed_output(out: str) -> None:
    attempts = 0

    async def fn(_):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ResponseFormatError("Missing required tags: character")
        return {}

    summary = await run_batch(jobs(1), fn, out)

    assert summary.ok == 1


@pytest.mark.asyncio
async def test_caps_calls_in_flight_across_groups(out: str) -> None:
    in_flight = peak = 0

    async def fn(_):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return {}

    group_jobs = [{"turn": f"t{i}", "sample": s} for i in range(4) for s in range(3)]
    await run_batch(group_jobs, fn, out, group=lambda j: j["turn"], concurrency=2)

    assert peak == 2


@pytest.mark.asyncio
async def test_stops_after_consecutive_failures(out: str) -> None:
    async def fn(_):
        raise RuntimeError("down")

    summary = await run_batch(jobs(5), fn, out, concurrency=1)

    assert summary.failed == 3
    assert summary.aborted == "3 failures in a row"


@pytest.mark.asyncio
async def test_stops_at_the_spend_cap_counting_earlier_runs(out: str) -> None:
    async def fn(_):
        return {"cost": 0.3}

    await run_batch(jobs(1), fn, out)
    summary = await run_batch(jobs(5), fn, out, concurrency=1, max_cost=0.5)

    assert summary.ok == 1
    assert len(read(out)) == 2


@pytest.mark.asyncio
async def test_stops_near_the_plan_limit(out: str) -> None:
    async def fn(_):
        return {"plan_usage": {"five_hour": {"utilization": 0.9}}}

    summary = await run_batch(jobs(3), fn, out, concurrency=1)

    assert summary.ok == 1
    assert summary.aborted is not None


@pytest.mark.asyncio
async def test_runs_one_job_per_group_before_the_rest(out: str) -> None:
    events = []

    async def fn(job):
        events.append(("start", job["turn"]))
        await asyncio.sleep(0)
        events.append(("end", job["turn"]))
        return {}

    group_jobs = [{"turn": f"t{i}", "char": "a"} for i in range(3)]
    await run_batch(group_jobs, fn, out, group=lambda job: job["char"])

    assert events[:2] == [("start", "t0"), ("end", "t0")]


@pytest.mark.asyncio
async def test_logs_an_abort_before_calls_in_flight_finish(out: str, capsys) -> None:
    async def fn(job):
        if job["turn"] == "t1":
            await asyncio.sleep(0)
            raise KeyError("points")
        await asyncio.sleep(0.01)
        return {}

    await run_batch(jobs(3), fn, out)

    lines = capsys.readouterr().out.splitlines()
    aborted = next(i for i, line in enumerate(lines) if "ABORTED" in line)
    finished = next(i for i, line in enumerate(lines) if "ok turn=t2" in line)
    assert aborted < finished
    assert "STOPPED: 2 ok, 0 failed" in lines[-1]
