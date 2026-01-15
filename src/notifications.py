import asyncio
import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .telegram.telegram_context import TelegramContext

_ctx: contextvars.ContextVar["TelegramContext | None"] = contextvars.ContextVar(
    "telegram_context", default=None
)


def set_context(ctx: "TelegramContext") -> None:
    _ctx.set(ctx)


def send(message: str) -> None:
    ctx = _ctx.get()
    if ctx:
        asyncio.create_task(ctx.send_message(message))  # noqa: RUF006
