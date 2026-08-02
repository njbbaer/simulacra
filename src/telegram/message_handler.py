import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import Any

import backoff
from telegram.error import TimedOut

from .. import notifications
from .telegram_context import TelegramContext


def requires_body(
    usage: str,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Reject a command with no text after it, else pass the text to the handler."""

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(self, ctx: TelegramContext, *args, **kwargs) -> Any:
            if not ctx.command_body:
                await ctx.send_message(f"`❌ Usage: {usage}`")
                return None
            return await func(self, ctx, ctx.command_body, *args, **kwargs)

        return wrapper

    return decorator


def message_handler(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    async def wrapper(self, update, context, *args, **kwargs) -> Any:
        ctx = TelegramContext(self.app, update, context)
        notifications.set_context(ctx)
        typing_task = asyncio.create_task(_loop_send_typing_action(ctx))
        try:
            await func(self, ctx, *args, **kwargs)
        finally:
            typing_task.cancel()

    return wrapper


async def _loop_send_typing_action(ctx: TelegramContext) -> None:
    while True:
        await _send_typing_action(ctx)
        await asyncio.sleep(4)


@backoff.on_exception(backoff.expo, TimedOut, max_tries=2)
async def _send_typing_action(ctx: TelegramContext) -> None:
    await ctx.send_typing_action()
