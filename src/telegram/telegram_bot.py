import textwrap
import re
import logging
import signal
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from src.simulacrum import Simulacrum
from src.telegram.filters import StaleMessageFilter
from src.telegram.message_handler import message_handler

logger = logging.getLogger('telegram_bot')
logging.basicConfig(level=logging.ERROR)


class TelegramBot:
    def __init__(self, context_filepath, telegram_token, authorized_users):
        self.app = ApplicationBuilder().token(telegram_token).build()
        self.sim = Simulacrum(context_filepath)

        self.app.add_handler(MessageHandler(StaleMessageFilter(), self.do_nothing))
        self.app.add_handler(MessageHandler(~filters.User(username=authorized_users), self.unauthorized))
        self.app.add_handler(CommandHandler('new', self.new_conversation_command_handler))
        self.app.add_handler(CommandHandler('retry', self.retry_command_handler))
        self.app.add_handler(CommandHandler('reply', self.reply_command_handler))
        self.app.add_handler(CommandHandler('undo', self.undo_command_handler))
        self.app.add_handler(CommandHandler('stats', self.stats_command_handler))
        self.app.add_handler(CommandHandler('clear', self.clear_command_handler))
        self.app.add_handler(CommandHandler('remember', self.remember_command_handler))
        self.app.add_handler(CommandHandler('help', self.help_command_handler))
        self.app.add_handler(CommandHandler('start', self.do_nothing))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.chat_message_handler))
        self.app.add_handler(MessageHandler(filters.ALL, self.unknown_message_handler))
        self.app.add_error_handler(self.error_handler)

    def run(self):
        self.app.run_polling()

    @message_handler
    async def chat_message_handler(self, ctx):
        await self._chat(ctx, ctx.message_text)

    @message_handler
    async def new_conversation_command_handler(self, ctx):
        chat_id = ctx.chat_id
        if self.sim.has_messages():
            await ctx.send_message('`⏳ Integrating memory...`')
            await self.sim.integrate_memory()
            await ctx.send_message('`✅ Ready to chat`')
        else:
            await ctx.send_message('`❌ No messages in conversation`')

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
        await ctx.send_message('🗑️ Last message undone')

    @message_handler
    async def stats_command_handler(self, ctx):
        percentage = round(self.sim.estimate_utilization_percentage())
        await ctx.send_message(f'`{percentage}% of max conversation size`')

    @message_handler
    async def clear_command_handler(self, ctx):
        self.sim.clear_messages()
        await ctx.send_message('🗑️ Current conversation cleared')

    @message_handler
    async def remember_command_handler(self, ctx):
        memory_text = re.search(r'/remember (.*)', ctx.message_text)
        if memory_text:
            self.sim.append_memory(memory_text.group(1))
            await ctx.send_message('`✅ Added to memory`')
        else:
            await ctx.send_message('`❌ No text provided`')

    @message_handler
    async def help_command_handler(self, ctx):
        await ctx.send_message(textwrap.dedent("""\
            *Actions*
            /new - Start a new conversation
            /retry - Retry the last response
            /reply - Reply immediately
            /undo - Undo the last exchange
            /clear - Clear the current conversation
            /remember <text> - Add text to memory

            *Information*
            /stats - Show conversation statistics
            /help - Show this help message
        """))

    @message_handler
    async def unauthorized(self, ctx):
        await ctx.send_message('`❌ Unauthorized`')

    @message_handler
    async def unknown_message_handler(self, ctx):
        await ctx.send_message('`❌ Not recognized`')

    @message_handler
    async def error_handler(self, ctx):
        logger.error(ctx.context.error, exc_info=True)
        if ctx.update:
            await ctx.send_message(f'`❌ An error occurred: {ctx.context.error}`')

    async def do_nothing(self, *_):
        pass

    async def _chat(self, ctx, user_message):
        response = await self.sim.chat(user_message)
        await ctx.send_message(response)
        await self._warn_max_size(ctx)

    async def _warn_max_size(self, ctx):
        percentage = round(self.sim.estimate_utilization_percentage())
        if percentage >= 70:
            shape, adverb = (
                ('🔴', 'now') if percentage >= 90 else
                ('🟠', 'soon') if percentage >= 80 else
                ('🟡', 'when ready')
            )
            text = f'`{shape} {percentage}% of max conversation size. Run /new {adverb}.`'
            await ctx.send_message(text)
