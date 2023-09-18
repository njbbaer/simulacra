from dotenv import load_dotenv
import threading
import time
from contextlib import contextmanager
import traceback

load_dotenv()


class TelegramBot:
    def __init__(self, bot, sim, user_id):
        self.bot = bot
        self.sim = sim
        self.user_id = user_id
        self._configure_handlers()

    def start(self):
        self.bot.infinity_polling()

    def _configure_handlers(self):
        self.bot.message_handler(func=self.is_unauthorized)(self.unauthorized_message_handler)
        self.bot.message_handler(commands=['integrate'])(self.integrate_command_handler)
        self.bot.message_handler(commands=['retry'])(self.retry_command_handler)
        self.bot.message_handler(commands=['tokens'])(self.tokens_command_handler)
        self.bot.message_handler(commands=['clear'])(self.clear_command_handler)
        self.bot.message_handler()(self.message_handler)

    def unauthorized_message_handler(self, message):
        self._send_message(message.chat.id, '🚫 Unauthorized', is_block=True)

    def integrate_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            self.sim.integrate_memory()
            self._send_message(message.chat.id, '✅ Memory integration complete', is_block=True)

    def retry_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            self.sim.clear_messages(1)
            response = self.sim.chat()
            self._send_message(message.chat.id, response)

    def tokens_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            percentage = round(self.sim.llm.token_utilization_percentage)
            text = f'{self.sim.llm.tokens} tokens in last request ({percentage}% of limit)'
            self._send_message(message.chat.id, text, is_block=True)

    def clear_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            self.sim.clear_messages()
            self._send_message(message.chat.id, '🗑️ The conversation has been cleared', is_block=True)

    def message_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            response = self.sim.chat(message.text)
            self._send_message(message.chat.id, response)

    def is_unauthorized(self, message):
        return str(message.chat.id) != self.user_id

    def _send_message(self, chat_id, text, is_block=False):
        formatted_text = f'```\n{text}\n```' if is_block else text
        self.bot.send_message(chat_id, formatted_text, parse_mode='Markdown')

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
