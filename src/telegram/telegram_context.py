import os
import re
import uuid
from typing import Optional

import httpx
from openai import AsyncOpenAI

from telegram.error import BadRequest

from ..utilities import parse_pdf, rehost_file_to_catbox


class TelegramContext:
    def __init__(self, app, update, context) -> None:
        self.app = app
        self.update = update
        self.context = context

    @property
    def _chat_id(self) -> int:
        return self.update.effective_chat.id

    @property
    def _message(self):
        return self.update.message

    @property
    def _user_name(self) -> str:
        return self._message.from_user.first_name

    @property
    def command_body(self) -> Optional[str]:
        match = re.search(r"/\w+\s+(.*)", self._message.text)
        return match.group(1) if match else None

    async def get_image_url(self) -> Optional[str]:
        if not self._message.photo:
            return None

        image_file = await self._message.photo[-1].get_file()
        image_url = await rehost_file_to_catbox(image_file.file_path)
        return image_url

    async def get_pdf_string(self) -> Optional[str]:
        if not self._message.document:
            return None

        document = await self._message.document.get_file()
        async with httpx.AsyncClient() as client:
            response = await client.get(document.file_path)
            response.raise_for_status()
            return parse_pdf(response.content)

    async def get_text(self) -> Optional[str]:
        if self._message.voice:
            return await self._transcribe_voice()
        return self._message.text or self._message.caption

    async def send_message(self, text: str) -> None:
        # Attempt to fix broken markdown
        if text.count("_") % 2 != 0 and text.endswith("_"):
            text = text[:-1]

        try:
            await self.app.bot.send_message(self._chat_id, text, parse_mode="Markdown")
        except BadRequest:
            await self.app.bot.send_message(self._chat_id, text)

    async def send_typing_action(self) -> None:
        await self.app.bot.send_chat_action(chat_id=self._chat_id, action="typing")

    async def _transcribe_voice(self) -> str:
        file_id = self._message.voice.file_id
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
