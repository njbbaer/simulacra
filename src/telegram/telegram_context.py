import os
import re
import uuid

import aiofiles
import backoff
from openai import AsyncOpenAI
from telegram.error import BadRequest, TimedOut

from ..utilities import parse_pdf


class TelegramContext:
    def __init__(self, app, update, context) -> None:
        self.app = app
        self.update = update
        self.context = context

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
        data = await document.download_as_bytearray()
        return parse_pdf(bytes(data))

    async def get_text(self) -> str | None:
        if self._message.voice:
            return await self._transcribe_voice()
        return self._message.text or self._message.caption

    async def send_response(self, text: str) -> None:
        # Italicize parenthetical asides
        text = text.replace("(", "_(").replace(")", ")_")

        # Attempt to fix broken markdown
        if text.count("_") % 2 != 0 and text.endswith("_"):
            text = text[:-1]
        await self.send_message(text)

    @backoff.on_exception(backoff.expo, TimedOut, max_tries=5)
    async def send_message(self, text: str) -> None:
        for chunk in self._split_message(text):
            try:
                await self.app.bot.send_message(
                    self._chat_id, chunk, parse_mode="Markdown"
                )
            except BadRequest:
                await self.app.bot.send_message(self._chat_id, chunk)

    async def send_typing_action(self) -> None:
        await self.app.bot.send_chat_action(chat_id=self._chat_id, action="typing")

    @property
    def _chat_id(self) -> int:
        return self.update.effective_chat.id

    @property
    def _message(self):
        return self.update.message

    @staticmethod
    def _split_message(text: str, max_length: int = 4096) -> list[str]:
        if len(text) <= max_length:
            return [text]

        for sep in ["\n\n", "\n", " "]:
            idx = text.rfind(sep, 0, max_length)
            if idx != -1:
                break
        else:
            idx = max_length

        head = text[:idx].rstrip()
        tail = text[idx:].lstrip()
        return [head, *TelegramContext._split_message(tail, max_length)]

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
