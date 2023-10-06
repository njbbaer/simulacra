class TelegramContext:
    def __init__(self, app, update, context):
        self.app = app
        self.update = update
        self.context = context

    @property
    def chat_id(self):
        return self.update.effective_chat.id

    @property
    def message_text(self):
        return self.update.message.text

    async def send_message(self, text):
        await self.app.bot.send_message(self.chat_id, text, parse_mode="Markdown")

    async def send_typing_action(self):
        await self.app.bot.send_chat_action(chat_id=self.chat_id, action="typing")
