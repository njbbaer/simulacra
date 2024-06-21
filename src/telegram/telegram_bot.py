import logging
import re
import textwrap

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from ..simulacrum import Simulacrum
from ..telegram.filters import StaleMessageFilter
from ..telegram.message_handler import message_handler

logger = logging.getLogger("telegram_bot")
logging.basicConfig(level=logging.ERROR)


class TelegramBot:
    def __init__(self, context_filepath, telegram_token, authorized_users):
        self.app = ApplicationBuilder().token(telegram_token).build()
        self.sim = Simulacrum(context_filepath)

        # Ignore stale messages
        self.app.add_handler(MessageHandler(StaleMessageFilter(), self.do_nothing))

        # Disallow unauthorized users
        self.app.add_handler(
            MessageHandler(~filters.User(username=authorized_users), self.unauthorized)
        )

        # Handle commands
        self.app.add_handler(
            CommandHandler("new", self.new_conversation_command_handler)
        )
        self.app.add_handler(CommandHandler("retry", self.retry_command_handler))
        self.app.add_handler(CommandHandler("reply", self.reply_command_handler))
        self.app.add_handler(CommandHandler("undo", self.undo_command_handler))
        self.app.add_handler(CommandHandler("fact", self.add_fact_command_handler))
        self.app.add_handler(CommandHandler("stats", self.stats_command_handler))
        self.app.add_handler(CommandHandler("clear", self.clear_command_handler))
        self.app.add_handler(CommandHandler("help", self.help_command_handler))
        self.app.add_handler(CommandHandler("start", self.do_nothing))

        # Handle messages
        self.app.add_handler(
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.VOICE,
                self.chat_message_handler,
            )
        )

        # Handle unknown messages and errors
        self.app.add_handler(MessageHandler(filters.ALL, self.unknown_message_handler))
        self.app.add_error_handler(self.error_handler)

    def run(self):
        self.app.run_polling()

    @message_handler
    async def chat_message_handler(self, ctx):
        image_url = await ctx.get_image_url()
        text = await ctx.get_text()
        await self._chat(ctx, text, image_url)

    @message_handler
    async def new_conversation_command_handler(self, ctx):
        if self.sim.has_messages():
            await self.sim.new_conversation()
            await ctx.send_message("`✅ New conversation started`")
        else:
            await ctx.send_message("`❌ No messages in conversation`")

    @message_handler
    async def retry_command_handler(self, ctx):
        self.sim.trim_messages(1)
        await self._chat(ctx, user_message=None)

    @message_handler
    async def reply_command_handler(self, ctx):
        await self._chat(ctx, user_message=None)

    @message_handler
    async def undo_command_handler(self, ctx):
        self.sim.undo_last_user_message()
        await ctx.send_message("🗑️ Last message undone")

    @message_handler
    async def stats_command_handler(self, ctx):
        lines = []
        lines.append("*Conversation*")
        lines.append(f"`Cost: ${self.sim.get_conversation_cost():.2f}`")
        lines.append("\n*Last Message*")
        last_completion = self.sim.last_completion
        if last_completion:
            lines.append(f"`Cost: ${last_completion.cost:.2f}`")
            lines.append(f"`Prompt tokens: {last_completion.prompt_tokens}`")
            lines.append(f"`Completion tokens: {last_completion.completion_tokens}`")
        else:
            lines.append("`Not available`")
        await ctx.send_message("\n".join(lines))

    @message_handler
    async def clear_command_handler(self, ctx):
        self.sim.reset_conversation()
        await ctx.send_message("🗑️ Current conversation cleared")

    @message_handler
    async def add_fact_command_handler(self, ctx):
        fact_text = re.search(r"/fact (.*)", ctx.message.text)
        if fact_text:
            self.sim.add_conversation_fact(fact_text.group(1))
            await ctx.send_message("`✅ Fact added to conversation`")
        else:
            await ctx.send_message("`❌ No text provided`")

    @message_handler
    async def help_command_handler(self, ctx):
        await ctx.send_message(
            textwrap.dedent(
                """
                *Actions*
                /new - Start a new conversation
                /retry - Retry the last response
                /reply - Reply immediately
                /undo - Undo the last exchange
                /clear - Clear the conversation
                /fact - Add a fact to the conversation

                *Information*
                /stats - Show conversation statistics
                /help - Show this help message
                """
            )
        )

    @message_handler
    async def unauthorized(self, ctx):
        await ctx.send_message("`❌ Unauthorized`")

    @message_handler
    async def unknown_message_handler(self, ctx):
        await ctx.send_message("`❌ Not recognized`")

    @message_handler
    async def error_handler(self, ctx):
        logger.error(ctx.context.error, exc_info=True)
        if ctx.update:
            await ctx.send_message(f"`❌ An error occurred: {ctx.context.error}`")

    async def do_nothing(self, *_):
        pass

    async def _chat(self, ctx, user_message, image_url=None):
        response = await self.sim.chat(user_message, ctx.user_name, image_url)
        response = response.translate(str.maketrans("*_", "_*"))
        await ctx.send_message(response)
        await self._warn_cost(ctx)

    async def _warn_cost(self, ctx, threshold_high=0.15, threshold_elevated=0.10):
        cost = self.sim.last_completion.cost
        if not cost:
            return

        if cost > threshold_high:
            await ctx.send_message("🔴 Cost is high. Start a new conversation soon.")
        elif cost > threshold_elevated and not self.sim.cost_warning_sent:
            self.sim.cost_warning_sent = True
            await ctx.send_message(
                "🟡 Cost is elevated. Start a new conversation when ready."
            )
