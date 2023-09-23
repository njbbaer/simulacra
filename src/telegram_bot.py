import textwrap
import re
import asyncio
import logging
from functools import wraps
from telegram.ext import CommandHandler, MessageHandler, filters

logger = logging.getLogger('telegram_bot')
logging.basicConfig(level=logging.ERROR)


def send_typing_action(func):
    @wraps(func)
    async def command_func(self, update, context, *args, **kwargs):
        async def loop_send_typing_action():
            while True:
                await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='typing')
                await asyncio.sleep(4)

        typing_task = asyncio.create_task(loop_send_typing_action())
        try:
            return await func(self, update, context, *args, **kwargs)
        finally:
            typing_task.cancel()

    return command_func


class TelegramBot:
    def __init__(self, app, sim, authorized_users):
        self.app = app
        self.sim = sim

        self.app.add_handler(MessageHandler(~filters.User(username=authorized_users), self.unauthorized))
        self.app.add_handler(CommandHandler('new', self.new_conversation_command_handler))
        self.app.add_handler(CommandHandler('retry', self.retry_command_handler))
        self.app.add_handler(CommandHandler('reply', self.reply_command_handler))
        self.app.add_handler(CommandHandler('tokens', self.tokens_command_handler))
        self.app.add_handler(CommandHandler('clear', self.clear_command_handler))
        self.app.add_handler(CommandHandler('remember', self.remember_command_handler))
        self.app.add_handler(CommandHandler('help', self.help_command_handler))
        self.app.add_handler(CommandHandler('start', lambda x: None))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        self.app.add_handler(MessageHandler(filters.ALL, self.unknown_message_handler))

        self.app.add_error_handler(self.error_handler)

    def run(self):
        self.app.run_polling()

    @send_typing_action
    async def message_handler(self, update, context):
        await self._chat(update.effective_chat.id, update.message.text)

    @send_typing_action
    async def new_conversation_command_handler(self, update, context):
        chat_id = update.effective_chat.id
        self.sim.context.load()
        if self.sim.context.current_messages:
            await self._send_message(chat_id, '`⏳ Integrating memory...`')
            await self.sim.integrate_memory()
            await self._send_message(chat_id, '`✅ Ready to chat`')
        else:
            await self._send_message(chat_id, '`❌ No messages in conversation`')

    @send_typing_action
    async def retry_command_handler(self, update, context):
        self.sim.clear_messages(1)
        await self._chat(update.effective_chat.id, message_text=None)

    @send_typing_action
    def reply_command_handler(self, update, context):
        self._chat(update.effective_chat.id, message_text=None)

    async def tokens_command_handler(self, update, context):
        text = f'`{self.sim.llm.tokens} tokens in last request`'
        await self._send_message(update.effective_chat.id, text)

    async def clear_command_handler(self, update, context):
        self.sim.clear_messages()
        await self._send_message(update.effective_chat.id, '🗑️ Current conversation cleared')

    async def remember_command_handler(self, update, context):
        memory_text = re.search(r'/remember (.*)', update.message.text)
        if memory_text:
            self.sim.append_memory(memory_text.group(1))
            await self._send_message(update.effective_chat.id, '`✅ Added to memory`')
        else:
            await self._send_message(update.effective_chat.id, '`❌ No text provided`')

    async def help_command_handler(self, update, context):
        text = textwrap.dedent("""\
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
        await self._send_message(update.effective_chat.id, text)

    async def unauthorized(self, update, context):
        await self._send_message(update.effective_chat.id, '`❌ Unauthorized`')

    async def unknown_message_handler(self, update, context):
        await self._send_message(update.effective_chat.id, '`❌ Not recognized`')

    async def error_handler(self, update, context):
        logger.error(context.error, exc_info=True)
        error_text = f'`❌ An error occurred: {context.error}`'
        if update:
            await self._send_message(update.effective_chat.id, error_text)

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
