import asyncio
import json
import os
import time
import traceback
from collections.abc import Awaitable, Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Any

import httpx
from claude_agent_sdk import ClaudeSDKError

from ..response_transform import ResponseFormatError

type Job = dict[str, Any]

# Errors from the API or the model's output; anything else is a local bug
RETRYABLE = (
    RuntimeError,
    ResponseFormatError,
    TimeoutError,
    httpx.HTTPError,
    ClaudeSDKError,
)
ATTEMPTS = 3
RETRY_SECONDS = 10
BREAKER = 3
PLAN_LIMITS = {"five_hour": 0.8, "seven_day": 0.9}


@dataclass
class BatchSummary:
    ok: int
    failed: int
    aborted: str | None


async def run_batch(
    jobs: Iterable[Job],
    fn: Callable[[Job], Awaitable[dict[str, Any]]],
    out: str,
    *,
    group: Callable[[Job], Hashable] = lambda _: None,
    concurrency: int = 10,
    max_cost: float | None = None,
    plan_limits: dict[str, float] | None = None,
) -> BatchSummary:
    """Run `fn` on each job, appending `{"job": job, **result}` lines to `out`.

    Jobs already in `out` are skipped. At most `concurrency` jobs run at once,
    and each group runs one job before the rest so they can read the prompt
    cache it writes. `plan_limits` overrides the PLAN_LIMITS utilization at
    which the batch stops.
    """
    records = _read(out)
    done = {_key(r["job"]) for r in records}
    pending = [job for job in jobs if _key(job) not in done]
    spent = sum(r.get("cost", 0.0) for r in records)
    limits = {**PLAN_LIMITS, **(plan_limits or {})}
    batch = _Batch(fn, out, len(pending), spent, max_cost, limits)
    _log(f"{len(pending)} jobs ({len(done)} already done)")

    groups: dict[Hashable, list[Job]] = {}
    for job in pending:
        groups.setdefault(group(job), []).append(job)

    semaphore = asyncio.Semaphore(concurrency)

    async def run(job: Job, *, warm: bool) -> None:
        async with semaphore:
            await batch.run(job, warm=warm)

    async def run_group(group_jobs: list[Job]) -> None:
        await run(group_jobs[0], warm=False)
        await asyncio.gather(*(run(job, warm=True) for job in group_jobs[1:]))

    await asyncio.gather(*(run_group(g) for g in groups.values()))
    if batch.warm_prompt:
        share = batch.warm_cached / batch.warm_prompt
        _log(
            f"cached {batch.warm_cached}/{batch.warm_prompt} ({share:.0%}) "
            "of prompt tokens in jobs after each group's first"
        )
    totals = f"{batch.ok} ok, {batch.failed} failed"
    _log(f"STOPPED: {totals}" if batch.aborted else f"ALL DONE: {totals}")
    return BatchSummary(batch.ok, batch.failed, batch.aborted)


class _Batch:
    def __init__(
        self,
        fn: Callable[[Job], Awaitable[dict[str, Any]]],
        out: str,
        total: int,
        spent: float,
        max_cost: float | None,
        plan_limits: dict[str, float],
    ) -> None:
        self._fn = fn
        self._out = out
        self._total = total
        self._spent = spent
        self._max_cost = max_cost
        self._plan_limits = plan_limits
        self._consecutive_failures = 0
        self.ok = 0
        self.failed = 0
        self.aborted: str | None = None
        self.warm_cached = 0
        self.warm_prompt = 0

    async def run(self, job: Job, *, warm: bool) -> None:
        label = " ".join(f"{k}={v}" for k, v in job.items())
        for attempt in range(1, ATTEMPTS + 1):
            if self.aborted:
                return
            if self._max_cost is not None and self._spent >= self._max_cost:
                self._abort(f"spent ${self._spent:.2f} of ${self._max_cost:.2f}")
                return
            try:
                result = await self._fn(job)
            except RETRYABLE as err:
                if attempt < ATTEMPTS:
                    _log(f"RETRY {label} attempt {attempt}: {_describe(err)}")
                    await asyncio.sleep(RETRY_SECONDS * attempt)
                    continue
                self._fail(label, err)
                return
            except Exception:
                self._abort(f"local error on {label}\n{traceback.format_exc()}")
                return
            self._record(job, label, result)
            if warm:
                self.warm_cached += result.get("cached_tokens", 0)
                self.warm_prompt += result.get("prompt_tokens", 0)
            return

    def _abort(self, reason: str) -> None:
        """Stop starting jobs, keeping the first reason; calls in flight finish."""
        if not self.aborted:
            self.aborted = reason
            _log(f"ABORTED: {reason}")

    def _fail(self, label: str, err: BaseException) -> None:
        self.failed += 1
        self._consecutive_failures += 1
        _log(f"FAILED {label}: {_describe(err)}")
        if self._consecutive_failures >= BREAKER:
            self._abort(f"{BREAKER} failures in a row")

    def _record(self, job: Job, label: str, result: dict[str, Any]) -> None:
        with open(self._out, "a") as file:
            file.write(json.dumps({"job": job, **result}) + "\n")
        self.ok += 1
        self._consecutive_failures = 0
        self._spent += result.get("cost", 0.0)
        _log(f"ok {label} {_summarize(result)} [{self.ok}/{self._total}]")
        usage = result.get("plan_usage") or {}
        if any(
            window["utilization"] >= self._plan_limits.get(name, 0.8)
            for name, window in usage.items()
        ):
            self._abort(f"plan usage near its limit: {usage}")


def _summarize(result: dict[str, Any]) -> str:
    parts = []
    if "duration_ms" in result:
        parts.append(f"{result['duration_ms'] / 1000:.1f}s")
    if "cached_tokens" in result and "prompt_tokens" in result:
        parts.append(f"cached={result['cached_tokens']}/{result['prompt_tokens']}")
    if result.get("cost"):
        parts.append(f"cost=${result['cost']:.4f}")
    if result.get("plan_cost"):
        parts.append(f"plan=${result['plan_cost']:.4f}")
    if usage := result.get("plan_usage"):
        parts.append(f"5h={usage.get('five_hour', {}).get('utilization')}")
    return " ".join(parts)


def _read(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path) as file:
        return [json.loads(line) for line in file if line.strip()]


def _key(job: Job) -> str:
    return json.dumps(job, sort_keys=True)


def _describe(err: BaseException) -> str:
    return f"{type(err).__name__}: {err}"


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)
