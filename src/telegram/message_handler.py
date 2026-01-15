import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import backoff
from telegram.error import TimedOut

from .. import notifications
from .telegram_context import TelegramContext


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
