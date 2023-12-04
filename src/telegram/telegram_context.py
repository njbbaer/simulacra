from telegram.error import BadRequest


class TelegramContext:
    def __init__(self, app, update, context):
        self.app = app
        self.update = update
        self.context = context

    @property
    def chat_id(self):
        return self.update.effective_chat.id

    @property
    def message(self):
        return self.update.message

    async def get_photo_url(self):
        if not self.message.photo:
            return None

        photo_file = await self.message.photo[-1].get_file()
        file = await self.app.bot.get_file(photo_file.file_id)
        return file.file_path

    async def send_message(self, text):
        # Attempt to fix broken markdown
        if text.count("*") % 2 != 0:
            text = text.rpartition("*")[0]

        try:
            await self.app.bot.send_message(self.chat_id, text, parse_mode="Markdown")
        except BadRequest:
            await self.app.bot.send_message(self.chat_id, text)

    async def send_typing_action(self):
        await self.app.bot.send_chat_action(chat_id=self.chat_id, action="typing")
