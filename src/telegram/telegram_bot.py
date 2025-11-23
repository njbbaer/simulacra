import logging
import textwrap
import tomllib

import aiofiles

# fmt: off
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from ..cost_tracker import CostTracker
from ..simulacrum import Simulacrum
from .filters import StaleMessageFilter
from .message_handler import message_handler
from .telegram_context import TelegramContext

# fmt: on


logger = logging.getLogger("telegram_bot")
logging.basicConfig(level=logging.ERROR)


class TelegramBot:
    def __init__(
        self, context_filepath: str, telegram_token: str, authorized_user: str
    ) -> None:
        self.app = (
            ApplicationBuilder().token(telegram_token).concurrent_updates(True).build()
        )
        self.sim = Simulacrum(context_filepath)
        self.cost_tracker = CostTracker()

        self._register_handlers(authorized_user)

    def _register_handlers(self, authorized_user: str) -> None:
        # Ignore stale messages
        self.app.add_handler(MessageHandler(StaleMessageFilter(), self._do_nothing))

        # Disallow unauthorized users
        self.app.add_handler(
            MessageHandler(
                ~filters.User(username=[authorized_user]),  # type: ignore
                self._unauthorized,  # type: ignore
            )
        )

        # Handle commands
        command_map = [
            (["new", "n"], self._new_conversation),
            (["retry", "r"], self._retry),
            (["undoretry", "ur"], self._undo_retry),
            (["continue", "co"], self._continue),
            (["undo", "u"], self._undo),
            (["fact", "f"], self._add_fact),
            (["instruct", "i"], self._apply_instruction),
            (["stats", "s"], self._stats),
            (["clear"], self._clear),
            (["syncbook", "sb"], self._sync_book),
            (["version", "v"], self._version),
            (["help", "h"], self._help),
            (["parrot"], self._parrot),
            (["start"], self._do_nothing),
        ]
        for commands, handler in command_map:
            for cmd in commands:
                self.app.add_handler(CommandHandler(cmd, handler))  # type: ignore

        # Handle messages
        self.app.add_handler(
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND)
                | filters.PHOTO
                | filters.VOICE
                | filters.ATTACHMENT,
                self.chat_message_handler,  # type: ignore
            )
        )

        # Handle unknown messages and errors
        self.app.add_handler(
            MessageHandler(filters.ALL, self._unknown_message)  # type: ignore
        )
        self.app.add_error_handler(self._error_handler)  # type: ignore

    def run(self) -> None:
        self.app.run_polling()

    @message_handler
    async def chat_message_handler(self, ctx: TelegramContext) -> None:
        image = await ctx.save_image_locally(self.sim.context.images_dir)
        pdf_string = await ctx.get_pdf_string()
        text = await ctx.get_text()
        documents = [pdf_string] if pdf_string else []
        await self._chat(ctx, text, image, documents=documents)

    @message_handler
    async def _new_conversation(self, ctx: TelegramContext) -> None:
        if self.sim.has_messages():
            await self.sim.new_conversation()
            self.cost_tracker.reset()
            await ctx.send_message("`✅ New conversation started`")
        else:
            await ctx.send_message("`❌ No messages in conversation`")

    @message_handler
    async def _retry(self, ctx: TelegramContext) -> None:
        response = await self.sim.retry()
        await ctx.send_message(response)
        await self._warn_cost(ctx)

    @message_handler
    async def _undo_retry(self, ctx: TelegramContext) -> None:
        self._cancel_current_request()
        if not self.sim.undo_retry():
            await ctx.send_message("`❌ No retry to undo`")
            return
        await ctx.send_message("↩️ Retry undone")

    @message_handler
    async def _continue(self, ctx: TelegramContext) -> None:
        response = await self.sim.continue_conversation()
        await ctx.send_message(response)
        await self._warn_cost(ctx)

    @message_handler
    async def _undo(self, ctx: TelegramContext) -> None:
        self._cancel_current_request()
        self.sim.undo()
        await ctx.send_message("🗑️ Last message undone")

    @message_handler
    async def _stats(self, ctx: TelegramContext) -> None:
        conversation_cost = (
            f"*Conversation*\n`Cost: ${self.sim.get_conversation_cost():.2f}`"
        )

        last_message_stats = "*Last Message*\n"
        if self.sim.last_completion:
            lc = self.sim.last_completion
            last_message_stats += "\n".join(
                [
                    f"`Cost: ${lc.cost:.4f}`",
                    f"`Cache discount: {lc.cache_discount_string}`",
                    f"`Prompt tokens: {lc.prompt_tokens}`",
                    f"`Completion tokens: {lc.completion_tokens}`",
                ]
            )
        else:
            last_message_stats += "`Not available`"

        await ctx.send_message(f"{conversation_cost}\n\n{last_message_stats}")

    @message_handler
    async def _clear(self, ctx: TelegramContext) -> None:
        self.sim.reset_conversation()
        self.cost_tracker.reset()
        await ctx.send_message("🗑️ Current conversation cleared")

    @message_handler
    async def _add_fact(self, ctx: TelegramContext) -> None:
        if not ctx.command_body:
            await ctx.send_message("`❌ No text provided`")
            return
        self.sim.add_conversation_fact(ctx.command_body)
        await ctx.send_message("`✅ Fact added to conversation`")

    @message_handler
    async def _apply_instruction(self, ctx: TelegramContext) -> None:
        if not ctx.command_body:
            await ctx.send_message("`❌ No text provided`")
            return
        self.sim.apply_instruction(ctx.command_body)
        await ctx.send_message("`✅ Instruction applied to next response`")

    @message_handler
    async def _help(self, ctx: TelegramContext) -> None:
        await ctx.send_message(
            textwrap.dedent(
                """
                *Actions*
                /new - Start a new conversation
                /retry - Retry the last response
                /undoretry - Undo a retry
                /undo - Undo the last exchange
                /clear - Clear the conversation
                /continue - Request another response
                /fact (...) - Add a fact to the conversation
                /instruct (...) - Apply an instruction
                /syncbook (...) - Sync current book position
                *Information*
                /stats - Show conversation statistics
                /help - Show this help message
                """
            )
        )

    @message_handler
    async def _sync_book(self, ctx: TelegramContext) -> None:
        query = ctx.command_body or ""
        book_chunk = self.sim.sync_book(query)
        num_words = len(book_chunk.split())
        chunk_sample = " ".join(book_chunk.split()[-10:])
        await ctx.send_message(f"_...{chunk_sample}_\n\n📖 Synced {num_words:,} words.")

    @message_handler
    async def _parrot(self, ctx: TelegramContext) -> None:
        if not ctx.command_body:
            await ctx.send_message("`❌ No text provided`")
            return
        await ctx.send_message(ctx.command_body)

    @message_handler
    async def _version(self, ctx: TelegramContext) -> None:
        async with aiofiles.open("pyproject.toml", "rb") as f:
            content = await f.read()
            pyproject = tomllib.loads(content.decode())
        await ctx.send_message(f"`📦 Version: {pyproject['project']['version']}`")

    @message_handler
    async def _unauthorized(self, ctx: TelegramContext) -> None:
        await ctx.send_message("`❌ Unauthorized`")

    @message_handler
    async def _unknown_message(self, ctx: TelegramContext) -> None:
        await ctx.send_message("`❌ Not recognized`")

    @message_handler
    async def _error_handler(self, ctx: TelegramContext) -> None:
        logger.error(ctx.context.error, exc_info=True)
        if ctx.update:
            try:
                await ctx.send_message(f"`❌ An error occurred: {ctx.context.error}`")
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    async def _do_nothing(self, *_) -> None:
        pass

    async def _chat(
        self,
        ctx: TelegramContext,
        user_message: str | None,
        image: str | None = None,
        documents: list[str] | None = None,
    ) -> None:
        response = await self.sim.chat(user_message, image, documents)
        await ctx.send_message(response)
        await self._warn_cost(ctx)

    async def _warn_cost(self, ctx: TelegramContext) -> None:
        if not self.sim.last_completion:
            return
        warnings = self.cost_tracker.get_cost_warnings(
            self.sim.last_completion.cost, self.sim.get_conversation_cost()
        )
        if warnings:
            await ctx.send_message("\n".join(warnings))

    def _cancel_current_request(self) -> None:
        from ..api_client import current_api_task

        if current_api_task:
            current_api_task.cancel()
