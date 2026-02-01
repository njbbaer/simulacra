import logging
import textwrap
import tomllib

import aiofiles

# fmt: off
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

from ..cost_tracker import CostTracker
from ..simulacrum import Simulacrum
from ..utilities import extract_url_content
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
        request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
        )
        self.app = (
            ApplicationBuilder()
            .token(telegram_token)
            .request(request)
            .concurrent_updates(True)
            .build()
        )
        self.sim = Simulacrum(context_filepath)
        self.cost_tracker = CostTracker()

        self._register_handlers(authorized_user)

    def run(self) -> None:
        self.app.run_polling()

    @message_handler
    async def chat_message_handler(self, ctx: TelegramContext) -> None:
        image = await ctx.save_image_locally(self.sim.context.images_dir)
        pdf_content = await ctx.get_pdf_content()
        text = await ctx.get_text()
        text, url_content = await extract_url_content(text)
        documents = [d for d in [pdf_content, url_content] if d]
        for document in documents:
            tokens = len(document) // 4
            await ctx.send_message(f"`📄 Document added: {tokens:,} tokens`")
        await self._chat(ctx, text, image, documents=documents)

    def _register_handlers(self, authorized_user: str) -> None:
        self.app.add_handler(MessageHandler(StaleMessageFilter(), self._do_nothing))

        self.app.add_handler(
            MessageHandler(
                ~filters.User(username=[authorized_user]),  # type: ignore
                self._unauthorized,  # type: ignore
            )
        )

        command_map = [
            (["new", "n"], self._new_conversation),
            (["extend", "e"], self._extend_conversation),
            (["retry", "r"], self._retry),
            (["undoretry", "ur"], self._undo_retry),
            (["continue", "co"], self._continue),
            (["undo", "u"], self._undo),
            (["set"], self._set_var),
            (["preset", "p"], self._apply_preset),
            (["instruct", "i"], self._apply_freeform_instruction),
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

        self.app.add_handler(
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND)
                | filters.PHOTO
                | filters.VOICE
                | filters.ATTACHMENT,
                self.chat_message_handler,  # type: ignore
            )
        )

        self.app.add_handler(
            MessageHandler(filters.ALL, self._unknown_message)  # type: ignore
        )
        self.app.add_error_handler(self._error_handler)  # type: ignore

    @message_handler
    async def _new_conversation(self, ctx: TelegramContext) -> None:
        if self.sim.has_messages():
            await self.sim.new_conversation()
            self.cost_tracker.reset()
            await ctx.send_message("`✅ New conversation started`")
        else:
            await ctx.send_message("`❌ No messages in conversation`")

    @message_handler
    async def _extend_conversation(self, ctx: TelegramContext) -> None:
        if self.sim.has_messages():
            await self.sim.extend_conversation()
            self.cost_tracker.reset()
            await ctx.send_message("`✅ Conversation extended with memory`")
        else:
            await ctx.send_message("`❌ No messages in conversation`")

    @message_handler
    async def _retry(self, ctx: TelegramContext) -> None:
        response = await self.sim.retry()
        await ctx.send_response(response)
        await self._warn_cost(ctx)

    @message_handler
    async def _undo_retry(self, ctx: TelegramContext) -> None:
        self.sim.cancel_pending_request()
        if not self.sim.undo_retry():
            await ctx.send_message("`❌ No retry to undo`")
            return
        await ctx.send_message("`↩️ Retry undone`")

    @message_handler
    async def _continue(self, ctx: TelegramContext) -> None:
        response = await self.sim.continue_conversation()
        await ctx.send_response(response)
        await self._warn_cost(ctx)

    @message_handler
    async def _undo(self, ctx: TelegramContext) -> None:
        self.sim.cancel_pending_request()
        self.sim.undo()
        await ctx.send_message("`🗑️ Last message undone`")

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
        await ctx.send_message("`🗑️ Current conversation cleared`")

    @message_handler
    async def _set_var(self, ctx: TelegramContext) -> None:
        if not ctx.command_body:
            await ctx.send_message("`❌ Usage: /set <key> <value>`")
            return
        parts = ctx.command_body.split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send_message("`❌ Usage: /set <key> <value>`")
            return
        key, value = parts
        self.sim.set_conversation_var(key, value)
        await ctx.send_message(f"`✅ Set {key} = {value}`")

    @message_handler
    async def _apply_preset(self, ctx: TelegramContext) -> None:
        if not ctx.command_body:
            await ctx.send_message("`❌ Usage: /preset <key> [message]`")
            return
        parts = ctx.command_body.split(maxsplit=1)
        key = parts[0]
        message = parts[1] if len(parts) > 1 else None
        preset_name = self.sim.apply_instruction(key)
        if not preset_name:
            await ctx.send_message(f"`❌ Unknown preset: {key}`")
            return
        await ctx.send_message(f"`✅ Preset '{preset_name}' applied`")
        if message:
            await self._chat(ctx, message)

    @message_handler
    async def _apply_freeform_instruction(self, ctx: TelegramContext) -> None:
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
                /extend - Extend conversation with memory
                /retry - Retry the last response
                /undoretry - Undo a retry
                /undo - Undo the last exchange
                /clear - Clear the conversation
                /continue - Request another response
                /set <key> <value> - Set a variable
                /preset (...) - Apply a preset
                /instruct (...) - Freeform instruction
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
        await ctx.send_message(
            f"`_...{chunk_sample}_\n\n📖 Synced {num_words:,} words.`"
        )

    @message_handler
    async def _parrot(self, ctx: TelegramContext) -> None:
        if not ctx.command_body:
            await ctx.send_message("`❌ No text provided`")
            return
        await ctx.send_response(ctx.command_body)

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
                error = ctx.context.error
                error_msg = str(error) or type(error).__name__
                await ctx.send_message(f"`❌ An error occurred: {error_msg}`")
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
        await ctx.send_response(response)
        await self._warn_cost(ctx)

    async def _warn_cost(self, ctx: TelegramContext) -> None:
        if not self.sim.last_completion:
            return
        warnings = self.cost_tracker.get_cost_warnings(
            self.sim.last_completion.cost, self.sim.get_conversation_cost()
        )
        if warnings:
            await ctx.send_message("\n".join(warnings))
