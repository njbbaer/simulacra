import os
import re
import uuid

import aiofiles
from openai import AsyncOpenAI
from telegram.error import BadRequest, TimedOut

from ..utilities import parse_pdf, retry_on

TEXT_MIME_TYPES = {"application/json", "application/x-yaml", "application/yaml"}
TEXT_EXTENSIONS = {".txt", ".md", ".yml", ".yaml", ".json"}


class TelegramContext:
    def __init__(self, app, update, context) -> None:
        self.app = app
        self.update = update
        self.context = context

    @property
    def command_body(self) -> str | None:
        match = re.search(r"/\w+\s+(.*)", self._message.text, re.DOTALL)
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

    async def get_document_content(self) -> str | None:
        """Return the text of an attached PDF or text file."""
        document = self._message.document
        if not document:
            return None
        mime_type = document.mime_type or ""
        extension = os.path.splitext(document.file_name or "")[1].lower()
        is_pdf = mime_type == "application/pdf" or extension == ".pdf"
        is_text = mime_type.startswith("text/") or mime_type in TEXT_MIME_TYPES
        if not is_pdf and not is_text and extension not in TEXT_EXTENSIONS:
            raise ValueError(f"Unsupported attachment: {mime_type or extension}")
        data = bytes(await (await document.get_file()).download_as_bytearray())
        return parse_pdf(data) if is_pdf else data.decode("utf-8")

    async def get_text(self) -> str | None:
        if self._message.voice:
            return await self._transcribe_voice()
        return self._message.text or self._message.caption

    async def send_response(self, text: str) -> None:
        await self.send_message(text, italicize_asides=True)

    async def send_message(self, text: str, italicize_asides: bool = False) -> None:
        for chunk in self._split_message(text):
            formatted = _italicize_asides(chunk) if italicize_asides else chunk
            await self._send_chunk(chunk, formatted)

    async def send_typing_action(self) -> None:
        await self.app.bot.send_chat_action(chat_id=self._chat_id, action="typing")

    @retry_on(TimedOut, 5)
    async def _send_chunk(self, chunk: str, formatted: str) -> None:
        """Send the formatted chunk as Markdown, or the plain one if it fails."""
        try:
            await self.app.bot.send_message(
                self._chat_id, formatted, parse_mode="Markdown"
            )
        except BadRequest:
            await self.app.bot.send_message(self._chat_id, chunk)

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


def _italicize_asides(text: str) -> str:
    text = text.replace("(", "_(").replace(")", ")_")
    if text.count("_") % 2 != 0 and text.endswith("_"):
        text = text[:-1]
    return text
