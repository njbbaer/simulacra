import logging
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

        self.app.add_handler(MessageHandler(StaleMessageFilter(), self.do_nothing))
        self.app.add_handler(
            MessageHandler(~filters.User(username=authorized_users), self.unauthorized)
        )
        self.app.add_handler(
            CommandHandler("new", self.new_conversation_command_handler)
        )
        self.app.add_handler(CommandHandler("retry", self.retry_command_handler))
        self.app.add_handler(CommandHandler("reply", self.reply_command_handler))
        self.app.add_handler(CommandHandler("undo", self.undo_command_handler))
        self.app.add_handler(CommandHandler("stats", self.stats_command_handler))
        self.app.add_handler(CommandHandler("clear", self.clear_command_handler))
        self.app.add_handler(CommandHandler("help", self.help_command_handler))
        self.app.add_handler(CommandHandler("start", self.do_nothing))
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND | filters.PHOTO,
                self.chat_message_handler,
            )
        )
        self.app.add_handler(MessageHandler(filters.ALL, self.unknown_message_handler))
        self.app.add_error_handler(self.error_handler)

    def run(self):
        self.app.run_polling()

    @message_handler
    async def chat_message_handler(self, ctx):
        image_url = await ctx.get_image_url()
        text = ctx.message.text or ctx.message.caption
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
        self.sim.clear_messages(1)
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
        lines.append(f"`Cost: ${self.sim.get_current_conversation_cost():.2f}`")

        lines.append("\n*Last Message*")
        if self.sim.last_cost:
            lines.append(f"`Cost: ${self.sim.last_cost:.2f}`")
            lines.append(f"`Prompt tokens: {self.sim.last_prompt_tokens}`")
            lines.append(f"`Completion tokens: {self.sim.last_completion_tokens}`")
        else:
            lines.append("`Not available`")

        await ctx.send_message("\n".join(lines))

    @message_handler
    async def clear_command_handler(self, ctx):
        self.sim.reset_current_conversation()
        await ctx.send_message("🗑️ Current conversation cleared")

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
                /clear - Clear the current conversation

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
        response = await self.sim.chat(user_message, image_url)
        response = response.translate(str.maketrans("*_", "_*"))
        await ctx.send_message(response)
        await self._warn_high_cost(ctx)

    async def _warn_high_cost(self, ctx):
        if not self.sim.last_cost:
            return

        if self.sim.last_cost > 0.15:
            await ctx.send_message("`🔴 Cost is high. Start a new conversation soon.`")
        elif self.sim.last_cost > 0.10 and not self.sim.warned_about_cost:
            self.sim.warned_about_cost = True
            await ctx.send_message(
                "`🟡 Cost is elevated. Start a new conversation when ready.`"
            )
