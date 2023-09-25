import asyncio

from src.telegram.telegram_context import TelegramContext


async def _loop_send_typing_action(ctx):
    try:
        while True:
            await ctx.send_typing_action()
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


def message_handler(func):
    async def wrapper(self, update, context, *args, **kwargs):
        ctx = TelegramContext(self.app, update, context)
        typing_task = asyncio.create_task(_loop_send_typing_action(ctx))
        try:
            await func(self, ctx, *args, **kwargs)
        finally:
            typing_task.cancel()
            await typing_task  # Wait for the task to cancel and cleanup

    return wrapper
