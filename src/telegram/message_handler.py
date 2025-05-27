import asyncio
from typing import Any, Awaitable, Callable

from .telegram_context import TelegramContext


async def _loop_send_typing_action(ctx: TelegramContext) -> None:
    while True:
        await ctx.send_typing_action()
        await asyncio.sleep(4)


def message_handler(
    func: Callable[..., Awaitable[Any]]
) -> Callable[..., Awaitable[Any]]:
    async def wrapper(self, update, context, *args, **kwargs) -> Any:
        ctx = TelegramContext(self.app, update, context)
        typing_task = asyncio.create_task(_loop_send_typing_action(ctx))
        try:
            await func(self, ctx, *args, **kwargs)
        finally:
            typing_task.cancel()

    return wrapper
