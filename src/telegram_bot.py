import os
import telebot
from dotenv import load_dotenv
import threading
import time
from contextlib import contextmanager
import traceback

from src.simulacrum import Simulacrum

load_dotenv()


class TelegramBot:
    def __init__(self, context_file):
        self.sim = Simulacrum(context_file)
        self.bot = telebot.TeleBot(os.environ['API_TOKEN'])
        self._configure_handlers()

    def start(self):
        self.bot.infinity_polling()

    def _configure_handlers(self):
        # Must be first to catch unauthorized messages
        @self.bot.message_handler(func=self.is_unauthorized)
        def unauthorized_message_handler(message):
            self._send_message(message.chat.id, '🚫 Unauthorized', is_block=True)

        @self.bot.message_handler(commands=['integrate'])
        def integrate_command_handler(message):
            with self._process_with_feedback(message.chat.id):
                self.sim.integrate_memory()
                text = '✅ Memory integration complete'
                self._send_message(message.chat.id, text, is_block=True)

        @self.bot.message_handler(commands=['retry'])
        def retry_command_handler(message):
            with self._process_with_feedback(message.chat.id):
                self.sim.clear_messages(1)
                response = self.sim.chat()
                self._send_message(message.chat.id, response)
                self._check_token_utilization(message.chat.id)

        @self.bot.message_handler(commands=['tokens'])
        def tokens_command_handler(message):
            with self._process_with_feedback(message.chat.id):
                percentage = round(self.sim.llm.token_utilization_percentage)
                text = f'{self.sim.llm.tokens} tokens in last request ({percentage}% of limit)'
                self._send_message(message.chat.id, text, is_block=True)

        @self.bot.message_handler(commands=['clear'])
        def tokens_command_handler(message):
            with self._process_with_feedback(message.chat.id):
                self.sim.clear_messages()
                text = '🗑️ The conversation has been cleared'
                self._send_message(message.chat.id, text, is_block=True)

        @self.bot.message_handler()
        def message_handler(message):
            with self._process_with_feedback(message.chat.id):
                response = self.sim.chat(message.text)
                self._send_message(message.chat.id, response)
                self._check_token_utilization(message.chat.id)

    def _send_message(self, chat_id, text, is_block=False):
        formatted_text = f'```\n{text}\n```' if is_block else text
        self.bot.send_message(chat_id, formatted_text, parse_mode='Markdown')

    def is_unauthorized(self, message):
        return str(message.chat.id) != os.environ['USER_ID']

    def _check_token_utilization(self, chat_id):
        percentage = round(self.sim.llm.token_utilization_percentage)
        if percentage >= 80:
            text = f'🔶 {percentage}% of max tokens used'
            self._send_message(chat_id, text, is_block=True)

    @contextmanager
    def _process_with_feedback(self, chat_id):
        try:
            with self._show_typing(chat_id):
                yield
        except Exception as e:
            error_text = f'❌ An error occurred: {e}'
            self._send_message(chat_id, error_text, is_block=True)
            traceback.print_exc()

    @contextmanager
    def _show_typing(self, chat_id):
        stop_typing_event = threading.Event()

        def send_typing_periodically():
            time.sleep(1)
            while not stop_typing_event.is_set():
                self.bot.send_chat_action(chat_id, action='typing')
                time.sleep(4)

        typing_thread = threading.Thread(target=send_typing_periodically)
        typing_thread.start()
        yield
        stop_typing_event.set()
        typing_thread.join()
