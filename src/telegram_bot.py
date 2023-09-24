import textwrap
import re
import asyncio
import logging
from functools import wraps
from telegram.ext import CommandHandler, MessageHandler, filters

logger = logging.getLogger('telegram_bot')
logging.basicConfig(level=logging.ERROR)


def message_handler(func):
    @wraps(func)
    async def wrapper(self, update, context, *args, **kwargs):
        async def loop_send_typing_action():
            while True:
                await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='typing')
                await asyncio.sleep(4)

        typing_task = asyncio.create_task(loop_send_typing_action())
        try:
            async for text in func(self, update, context, *args, **kwargs):
                if text:
                    await self._send_message(update.effective_chat.id, text)
        finally:
            typing_task.cancel()

    return wrapper


class TelegramBot:
    def __init__(self, app, sim, authorized_users):
        self.app = app
        self.sim = sim

        self.app.add_handler(MessageHandler(~filters.User(username=authorized_users), self.unauthorized))
        self.app.add_handler(CommandHandler('new', self.new_conversation_command_handler))
        self.app.add_handler(CommandHandler('retry', self.retry_command_handler))
        self.app.add_handler(CommandHandler('reply', self.reply_command_handler))
        self.app.add_handler(CommandHandler('usage', self.usage_command_handler))
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
    async def chat_message_handler(self, update, context):
        yield await self._chat(update.effective_chat.id, update.message.text)

    @message_handler
    async def new_conversation_command_handler(self, update, context):
        chat_id = update.effective_chat.id
        self.sim.context.load()
        if self.sim.context.current_messages:
            yield '`⏳ Integrating memory...`'
            await self.sim.integrate_memory()
            yield '`✅ Ready to chat`'
        else:
            yield '`❌ No messages in conversation`'

    @message_handler
    async def retry_command_handler(self, update, context):
        self.sim.clear_messages(1)
        yield await self._chat(update.effective_chat.id, message_text=None)

    @message_handler
    async def reply_command_handler(self, update, context):
        yield await self._chat(update.effective_chat.id, message_text=None)

    @message_handler
    async def tokens_command_handler(self, update, context):
        return f'`{self.sim.llm.tokens} tokens in last request`'

    @message_handler
    async def clear_command_handler(self, update, context):
        self.sim.clear_messages()
        yield '🗑️ Current conversation cleared'

    @message_handler
    async def remember_command_handler(self, update, context):
        memory_text = re.search(r'/remember (.*)', update.message.text)
        if memory_text:
            self.sim.append_memory(memory_text.group(1))
            yield '`✅ Added to memory`'
        else:
            yield '`❌ No text provided`'

    @message_handler
    async def help_command_handler(self, update, context):
        yield textwrap.dedent("""\
            *Actions*
            /new - Start a new conversation
            /retry - Retry the last response
            /reply - Reply immediately
            /clear - Clear the current conversation
            /remember <text> - Add text to memory

            *Information*
            /tokens - Show token utilization
            /help - Show this help message
        """)

    @message_handler
    async def unauthorized(self, update, context):
        yield '`❌ Unauthorized`'

    @message_handler
    async def unknown_message_handler(self, update, context):
        yield '`❌ Not recognized`'

    @message_handler
    async def error_handler(self, update, context):
        logger.error(context.error, exc_info=True)
        if update:
            yield f'`❌ An error occurred: {context.error}`'

    async def do_nothing(self, *_):
        pass

    async def _send_message(self, chat_id, text):
        await self.app.bot.send_message(chat_id, text, parse_mode='Markdown')

    async def _chat(self, chat_id, message_text):
        response = await self.sim.chat(message_text)
        await self._send_message(chat_id, response)
        await self._warn_token_utilization(chat_id)

    async def _warn_token_utilization(self, chat_id):
        percentage = round(self.sim.llm.token_utilization_percentage)
        if percentage >= 80:
            shape, adverb = (
                ('🔴', 'now') if percentage >= 90 else
                ('🟠', 'soon') if percentage >= 80 else
                ('🟡', 'when ready')
            )
            text = f'`{shape} {percentage}% of limit used. Run /new {adverb}.`'
            await self._send_message(chat_id, text)
