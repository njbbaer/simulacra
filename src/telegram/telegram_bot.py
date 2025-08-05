import logging
import math
import textwrap
from typing import List, Optional

# fmt: off
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from ..simulacrum import Simulacrum
from ..telegram.filters import StaleMessageFilter
from ..telegram.message_handler import message_handler
from ..telegram.telegram_context import TelegramContext

# fmt: on


logger = logging.getLogger("telegram_bot")
logging.basicConfig(level=logging.ERROR)


class TelegramBot:
    def __init__(
        self, context_filepath: str, telegram_token: str, authorized_users: List[str]
    ) -> None:
        self.app = (
            ApplicationBuilder().token(telegram_token).concurrent_updates(True).build()
        )
        self.sim = Simulacrum(context_filepath)
        self.last_warned_cost = 0

        # Ignore stale messages
        self.app.add_handler(MessageHandler(StaleMessageFilter(), self._do_nothing))

        # Disallow unauthorized users
        self.app.add_handler(
            MessageHandler(~filters.User(username=authorized_users), self.unauthorized)  # type: ignore
        )

        # Handle commands
        command_handlers = [
            (["new", "n"], self.new_conversation_command_handler),
            (["retry", "r"], self.retry_command_handler),
            (["continue", "co"], self.continue_command_handler),
            (["undo", "u"], self.undo_command_handler),
            (["fact", "f"], self.add_fact_command_handler),
            (["instruct", "i"], self.apply_instruction_command_handler),
            (["stats", "s"], self.stats_command_handler),
            (["clear"], self.clear_command_handler),
            (["cancel", "x"], self.cancel_command_handler),
            (["syncbook", "sb"], self.sync_book_command_handler),
            (["help", "h"], self.help_command_handler),
            (["start"], self._do_nothing),
        ]
        for commands, handler in command_handlers:
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
        self.app.add_handler(MessageHandler(filters.ALL, self.unknown_message_handler))  # type: ignore
        self.app.add_error_handler(self.error_handler)  # type: ignore

    def run(self) -> None:
        self.app.run_polling()

    @message_handler
    async def chat_message_handler(self, ctx: TelegramContext) -> None:
        image_url = await ctx.get_image_url()
        pdf_string = await ctx.get_pdf_string()
        text = await ctx.get_text()
        documents = [pdf_string] if pdf_string else []
        await self._chat(ctx, text, image_url, documents=documents)

    @message_handler
    async def new_conversation_command_handler(self, ctx: TelegramContext) -> None:
        if self.sim.has_messages():
            await self.sim.new_conversation()
            self.last_warned_cost = 0
            await ctx.send_message("`✅ New conversation started`")
        else:
            await ctx.send_message("`❌ No messages in conversation`")

    @message_handler
    async def retry_command_handler(self, ctx: TelegramContext) -> None:
        if self.sim.last_message_role == "assistant":
            self.sim.undo_last_messages_by_role("assistant")
        await self._chat(ctx, user_message=None)

    @message_handler
    async def continue_command_handler(self, ctx: TelegramContext) -> None:
        await self._chat(ctx, user_message=None)

    @message_handler
    async def undo_command_handler(self, ctx: TelegramContext) -> None:
        self.sim.undo_last_messages_by_role("user")
        await ctx.send_message("🗑️ Last message undone")

    @message_handler
    async def stats_command_handler(self, ctx: TelegramContext) -> None:
        conversation_cost = (
            f"*Conversation*\n`Cost: ${self.sim.get_conversation_cost():.2f}`"
        )

        last_message_stats = "*Last Message*\n"
        if self.sim.last_completion:
            lc = self.sim.last_completion
            last_message_stats += "\n".join(
                [
                    f"`Cost: ${lc.cost:.2f}`",
                    f"`Cache discount: {lc.cache_discount_string}`",
                    f"`Prompt tokens: {lc.prompt_tokens}`",
                    f"`Completion tokens: {lc.completion_tokens}`",
                ]
            )
        else:
            last_message_stats += "`Not available`"

        await ctx.send_message(f"{conversation_cost}\n\n{last_message_stats}")

    @message_handler
    async def clear_command_handler(self, ctx: TelegramContext) -> None:
        self.sim.reset_conversation()
        self.last_warned_cost = 0
        await ctx.send_message("🗑️ Current conversation cleared")

    @message_handler
    async def add_fact_command_handler(self, ctx: TelegramContext) -> None:
        if ctx.command_body:
            self.sim.add_conversation_fact(ctx.command_body)
            await ctx.send_message("`✅ Fact added to conversation`")
        else:
            await ctx.send_message("`❌ No text provided`")

    @message_handler
    async def apply_instruction_command_handler(self, ctx: TelegramContext) -> None:
        if ctx.command_body:
            self.sim.apply_instruction(ctx.command_body)
            await ctx.send_message("`✅ Instruction applied to next response`")
        else:
            await ctx.send_message("`❌ No text provided`")

    @message_handler
    async def help_command_handler(self, ctx: TelegramContext) -> None:
        await ctx.send_message(
            textwrap.dedent(
                """
                *Actions*
                /new - Start a new conversation
                /retry - Retry the last response
                /undo - Undo the last exchange
                /clear - Clear the conversation
                /continue - Request another response
                /cancel - Cancel the current request
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
    async def unauthorized(self, ctx: TelegramContext) -> None:
        await ctx.send_message("`❌ Unauthorized`")

    @message_handler
    async def unknown_message_handler(self, ctx: TelegramContext) -> None:
        await ctx.send_message("`❌ Not recognized`")

    @message_handler
    async def error_handler(self, ctx: TelegramContext) -> None:
        logger.error(ctx.context.error, exc_info=True)
        if ctx.update:
            await ctx.send_message(f"`❌ An error occurred: {ctx.context.error}`")

    @message_handler
    async def sync_book_command_handler(self, ctx: TelegramContext) -> None:
        query = ctx.command_body or ""
        book_chunk = self.sim.sync_book(query)
        num_words = len(book_chunk.split())
        chunk_sample = " ".join(book_chunk.split()[-10:])
        await ctx.send_message(f"_...{chunk_sample}_\n\n📖 Synced {num_words:,} words.")

    async def _do_nothing(self, *_) -> None:
        pass

    @message_handler
    async def cancel_command_handler(self, ctx: TelegramContext) -> None:
        from ..api_client import last_api_call_task

        if last_api_call_task:
            last_api_call_task.cancel()
            last_api_call_task = None
            await ctx.send_message("`✅ API call cancelled`")
        else:
            await ctx.send_message("`❌ No API call to cancel`")

    async def _chat(
        self,
        ctx: TelegramContext,
        user_message: Optional[str],
        image_url: Optional[str] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        response = await self.sim.chat(user_message, image_url, documents)
        response = response.replace("(", "_(").replace(")", ")_")
        await ctx.send_message(response)
        await self._warn_cost(ctx)

    async def _warn_cost(self, ctx: TelegramContext) -> None:
        if not self.sim.last_completion:
            return
        cost = self.sim.last_completion.cost
        total_cost = self.sim.get_conversation_cost()
        warnings = []

        if cost and cost > 0.15:
            symbol = "🔴" if cost > 0.25 else "🟡"
            warnings.append(f"{symbol} Last message cost: ${cost:.2f}")

        if total_cost > self.last_warned_cost + 1.0:
            self.last_warned_cost = math.floor(total_cost)
            symbol = "🔴" if total_cost > 3.0 else "🟡"
            warnings.append(f"{symbol} Conversation cost: ${total_cost:.2f}")

        if warnings:
            await ctx.send_message("\n".join(warnings))
