import os
import re
import uuid

import aiofiles
import backoff
import httpx
from openai import AsyncOpenAI
from telegram.error import BadRequest

from ..utilities import parse_pdf


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
    def command_body(self) -> str | None:
        match = re.search(r"/\w+\s+(.*)", self._message.text)
        return match.group(1) if match else None

    async def save_image_locally(self, base_path: str) -> str | None:
        if not self._message.photo:
            return None

        image_file = await self._message.photo[-1].get_file()
        os.makedirs(base_path, exist_ok=True)
        filename = f"{uuid.uuid4()}.jpg"
        image_filepath = f"{base_path}/{filename}"
        await image_file.download_to_drive(image_filepath)
        return filename

    async def get_pdf_content(self) -> str | None:
        if not self._message.document:
            return None

        document = await self._message.document.get_file()
        async with httpx.AsyncClient() as client:
            response = await client.get(document.file_path)
            response.raise_for_status()
            return parse_pdf(response.content)

    async def get_text(self) -> str | None:
        if self._message.voice:
            return await self._transcribe_voice()
        return self._message.text or self._message.caption

    @backoff.on_exception(backoff.expo, httpx.HTTPError, max_tries=3)
    async def send_message(self, text: str) -> None:
        # Italicize parenthetical asides
        text = text.replace("(", "_(").replace(")", ")_")

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
            async with aiofiles.open(voice_filepath, "rb") as file:
                content = await file.read()
            transcript = await AsyncOpenAI().audio.transcriptions.create(
                model="whisper-1",
                file=(os.path.basename(voice_filepath), content),
            )
            return transcript.text
        finally:
            os.remove(voice_filepath)
