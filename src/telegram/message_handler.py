import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import backoff
from telegram.error import NetworkError

from .telegram_context import TelegramContext


async def _loop_send_typing_action(ctx: TelegramContext) -> None:
    while True:
        await _send_typing_action(ctx)
        await asyncio.sleep(4)


@backoff.on_exception(backoff.expo, NetworkError, max_tries=2)
async def _send_typing_action(ctx: TelegramContext) -> None:
    await ctx.send_typing_action()


def message_handler(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    async def wrapper(self, update, context, *args, **kwargs) -> Any:
        ctx = TelegramContext(self.app, update, context)
        typing_task = asyncio.create_task(_loop_send_typing_action(ctx))
        try:
            await func(self, ctx, *args, **kwargs)
        finally:
            typing_task.cancel()

    return wrapper
