import os
import re
import uuid

import httpx
from openai import AsyncOpenAI

from telegram.error import BadRequest

from ..utilities import parse_pdf


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

    @property
    def user_name(self):
        return self.update.message.from_user.first_name

    @property
    def command_body(self):
        return re.search(r"/\w+\s+(.*)", self.message.text)

    async def get_image_url(self):
        if not self.message.photo:
            return None

        photo_file = await self.message.photo[-1].get_file()
        return photo_file.file_path

    async def get_pdf_string(self):
        if not self.message.document:
            return None

        document = await self.message.document.get_file()
        async with httpx.AsyncClient() as client:
            response = await client.get(document.file_path)
            response.raise_for_status()
            return parse_pdf(response.content)

    async def get_text(self):
        if self.message.voice:
            return await self._transcribe_voice()
        return self.message.text or self.message.caption

    async def send_message(self, text):
        # Attempt to fix broken markdown
        if text.count("_") % 2 != 0 and text.endswith("_"):
            text = text[:-1]

        try:
            await self.app.bot.send_message(self.chat_id, text, parse_mode="Markdown")
        except BadRequest:
            await self.app.bot.send_message(self.chat_id, text)

    async def send_typing_action(self):
        await self.app.bot.send_chat_action(chat_id=self.chat_id, action="typing")

    async def _transcribe_voice(self):
        file_id = self.message.voice.file_id
        voice_file = await self.context.bot.get_file(file_id)
        os.makedirs("tmp", exist_ok=True)
        voice_filepath = f"tmp/{uuid.uuid4()}.ogg"
        try:
            await voice_file.download_to_drive(voice_filepath)
            with open(voice_filepath, "rb") as file:
                transcript = await AsyncOpenAI().audio.transcriptions.create(
                    model="whisper-1", file=file
                )
            return transcript.text
        finally:
            os.remove(voice_filepath)
