import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Any

from . import trials
from .context import Context
from .lm_executors import ChatExecutor
from .message import Message
from .request_recorder import RequestRecorder
from .response_transform import extract_tag, strip_tags, transform_response
from .telemetry import Telemetry, TimedRecord
from .turn_stats import TurnStats

if TYPE_CHECKING:
    from .chat_completion import ChatCompletion

RESPONSE = trials.Stage("response")
POST_PROCESS = trials.Stage("post_process", scope="post_process")

CACHE_TTL_SECONDS = 15 * 60
CACHE_WRITE_SECONDS = 2.0


@dataclass
class StageResult:
    """One candidate's output, with the context and completion behind it."""

    content: str
    context: Context
    completion: ChatCompletion
    notes: str | None = None

    def as_candidate(self) -> dict[str, Any]:
        return {
            "content": self.content,
            **({"notes": self.notes} if self.notes else {}),
        }


@dataclass
class Drafts:
    """The response stage's output for one candidate, one result per draft."""

    results: list[StageResult]

    @property
    def contents(self) -> list[str]:
        return [result.content for result in self.results]

    def as_candidate(self) -> dict[str, Any]:
        if len(self.results) == 1:
            return self.results[0].as_candidate()
        return {"drafts": self.contents}


@dataclass
class Generation:
    content: str
    display: str
    drafts: list[str] = field(default_factory=list)
    editor_notes: str | None = None
    trial_record: dict[str, Any] | None = None
    models: dict[str, str] = field(default_factory=dict)

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            **({"draft": self.drafts[0]} if len(self.drafts) == 1 else {}),
            **({"drafts": self.drafts} if len(self.drafts) > 1 else {}),
            **({"editor_notes": self.editor_notes} if self.editor_notes else {}),
            **({"trial": self.trial_record["id"]} if self.trial_record else {}),
        }


class Generator:
    """Runs the stages of one turn, tracking its cost and pending request."""

    def __init__(self, trial_log: trials.TrialLog, telemetry: Telemetry) -> None:
        self._trial_log = trial_log
        self._telemetry = telemetry
        self._turn = telemetry
        self.last_turn: TurnStats | None = None
        self._task: asyncio.Task | None = None
        self._cache_written: dict[tuple[str, int], float] = {}

    @property
    def busy(self) -> bool:
        return self._task is not None

    def cancel(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def generate(
        self,
        context: Context,
        *,
        action: str,
        skip_required_tags: bool = False,
        skip_injected_prompt: bool = False,
        skip_post_process: bool = False,
    ) -> Generation:
        RequestRecorder().reset()
        self.last_turn = turn = TurnStats(action)
        self._turn = self._telemetry.scoped(
            turn=secrets.token_hex(6),
            character=context.context_name,
            conversation=None if context.is_ephemeral else context.conversation_id,
            action=action,
        )
        record = self._turn.start(kind="turn")
        try:
            generation = await self._generate(
                context,
                skip_required_tags=skip_required_tags,
                skip_injected_prompt=skip_injected_prompt,
                skip_post_process=skip_post_process,
            )
        except BaseException as err:
            turn.duration_ms = record.fail(err)["duration_ms"]
            raise
        row = record.ok(
            cost=turn.cost,
            plan_cost=turn.plan_cost,
            chars=len(generation.display),
        )
        turn.duration_ms = row["duration_ms"]
        return generation

    async def _generate(
        self,
        context: Context,
        *,
        skip_required_tags: bool,
        skip_injected_prompt: bool,
        skip_post_process: bool,
    ) -> Generation:
        editing = not skip_post_process

        response = await self._run_stage(
            RESPONSE,
            context,
            partial(
                self._draft,
                editing=editing,
                skip_injected_prompt=skip_injected_prompt,
                skip_required_tags=skip_required_tags,
            ),
        )
        stages: dict[trials.Stage, trials.TrialRun[Any]] = {RESPONSE: response}

        result = response.result.results[0]
        models = {RESPONSE.name: result.context.model}
        drafts: list[str] = []
        if editing and result.context.post_process_prompt:
            drafts = response.result.contents
            edited = await self._run_stage(
                POST_PROCESS,
                result.context,
                partial(self._edit, drafts=drafts),
            )
            stages[POST_PROCESS] = edited
            result = edited.result
            models[POST_PROCESS.name] = result.context.post_process_model

        display = strip_tags(result.content)
        if not display:
            raise ValueError("No displayable content")
        return Generation(
            result.content,
            display,
            drafts,
            result.notes,
            self._trial_record(stages),
            models,
        )

    async def _run_stage[T](
        self,
        stage: trials.Stage,
        context: Context,
        execute: Callable[[Context, str | None], Awaitable[T]],
    ) -> trials.TrialRun[T]:
        self._task = asyncio.create_task(trials.run(context, stage, execute))
        try:
            return await self._task
        finally:
            self._task = None

    async def _complete(
        self,
        executor: ChatExecutor,
        record: TimedRecord,
        params: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        """Execute the request, charging it to the turn and finishing its record."""
        try:
            completion = await executor.execute(params, on_retry=record.retried)
        except BaseException as err:
            record.fail(err)
            raise
        row = record.ok(
            generation_id=completion.id,
            provider=completion.provider,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            cached_tokens=completion.cached_tokens,
            reasoning_tokens=completion.reasoning_tokens,
            cost=completion.cost,
            plan_cost=completion.plan_cost,
            plan_usage=completion.plan_usage,
            chars=len(completion.content),
        )
        assert self.last_turn is not None
        self.last_turn.requests.append(row)
        return completion

    def _start_request(
        self, stage: trials.Stage, model: str, alias: str | None, label: str | None
    ) -> TimedRecord:
        return self._turn.start(
            kind="request",
            stage=stage.name,
            model=model,
            candidate=alias,
            draft=int(label) if label else None,
        )

    async def _draft(
        self,
        context: Context,
        alias: str | None,
        *,
        editing: bool,
        skip_injected_prompt: bool,
        skip_required_tags: bool,
    ) -> Drafts:
        """Generate every draft the editor will see, or one if it will not run."""
        count = context.post_process_drafts if editing else 1
        labels = [None] if count == 1 else [str(i) for i in range(1, count + 1)]
        delay = 0.0 if self._cache_warm(context) else CACHE_WRITE_SECONDS

        async def respond(label: str | None, delay: float = 0.0) -> StageResult:
            await asyncio.sleep(delay)
            return await self._respond(
                context,
                alias,
                label,
                skip_injected_prompt=skip_injected_prompt,
                skip_required_tags=skip_required_tags,
            )

        results = await asyncio.gather(
            respond(labels[0]), *(respond(label, delay) for label in labels[1:])
        )
        return Drafts(list(results))

    def _cache_warm(self, context: Context) -> bool:
        """Return whether the prompt had a response request within the TTL."""
        written = self._cache_written.get(self._cache_key(context))
        return written is not None and time.monotonic() - written < CACHE_TTL_SECONDS

    @staticmethod
    def _cache_key(context: Context) -> tuple[str, int]:
        return (context.session_id, hash(context.resolved_data.get("system_prompt")))

    async def _respond(
        self,
        context: Context,
        alias: str | None,
        label: str | None,
        *,
        skip_injected_prompt: bool,
        skip_required_tags: bool,
    ) -> StageResult:
        executor = ChatExecutor(
            context,
            request_key=RESPONSE.request_key(alias, label),
            skip_injected_prompt=skip_injected_prompt,
        )
        record = self._start_request(RESPONSE, context.model, alias, label)
        completion = await self._complete(executor, record)
        self._cache_written[self._cache_key(context)] = time.monotonic()
        content = transform_response(
            completion.content,
            context.response_patterns,
            None if skip_required_tags else context.required_response_tags,
        )
        return StageResult(content, context, completion)

    async def _edit(
        self, context: Context, alias: str | None, *, drafts: list[str]
    ) -> StageResult:
        """Re-generate the drafts under the post-processing prompt."""
        if len(drafts) == 1:
            tagged = f"<draft>\n{drafts[0]}\n</draft>"
        else:
            tagged = "\n\n".join(
                f"<draft_{i}>\n{draft}\n</draft_{i}>"
                for i, draft in enumerate(drafts, start=1)
            )
        instruction = f"<instruct>\n{context.post_process_prompt}\n</instruct>"
        executor = ChatExecutor(
            context,
            request_key=POST_PROCESS.request_key(alias),
            skip_injected_prompt=True,
            extra_messages=[
                Message("assistant", tagged),
                Message("user", instruction),
            ],
            include_images=context.post_process_supports_images,
        )
        record = self._start_request(
            POST_PROCESS, context.post_process_model, alias, None
        )
        completion = await self._complete(executor, record, context.post_process_params)
        notes, content = extract_tag(completion.content, "assessment")
        content = transform_response(
            content,
            context.response_patterns,
            context.required_response_tags,
        )
        return StageResult(content, context, completion, notes)

    def _trial_record(
        self, stages: dict[trials.Stage, trials.TrialRun[Any]]
    ) -> dict[str, Any] | None:
        """Record every stage's candidates, or None if no stage ran a trial."""
        if not any(trial.selected for trial in stages.values()):
            return None
        record: dict[str, Any] = {"id": self._trial_log.next_id()}
        for stage, trial in stages.items():
            if trial.selected:
                record[stage.name] = {
                    "selected": trial.selected,
                    "candidates": {
                        alias: result.as_candidate()
                        for alias, result in trial.outputs.items()
                    },
                }
            else:
                record[stage.name] = trial.result.as_candidate()
        return record
