import threading
import time
from contextlib import contextmanager
import traceback
import re


class TelegramBot:
    def __init__(self, telebot, simulacrum, user_ids):
        self.telebot = telebot
        self.simulacrum = simulacrum
        self.user_ids = user_ids
        self._configure_handlers()

    def start(self):
        self.telebot.infinity_polling()

    def _configure_handlers(self):
        self.telebot.message_handler(func=self.is_unauthorized)(self.unauthorized_message_handler)
        self.telebot.message_handler(commands=['new'])(self.new_conversation_command_handler)
        self.telebot.message_handler(commands=['retry'])(self.retry_command_handler)
        self.telebot.message_handler(commands=['tokens'])(self.tokens_command_handler)
        self.telebot.message_handler(commands=['clear'])(self.clear_command_handler)
        self.telebot.message_handler(commands=['remember'])(self.remember_command_handler)
        self.telebot.message_handler(commands=['help'])(self.help_command_handler)
        self.telebot.message_handler(commands=['reply'])(self.reply_command_handler)
        self.telebot.message_handler(commands=['start'])(lambda x: None)
        self.telebot.message_handler(func=self.is_command)(self.invalid_command_handler)
        self.telebot.message_handler()(self.message_handler)

    #
    # Handlers
    #

    def unauthorized_message_handler(self, message):
        self._send_message(message.chat.id, '🚫 Unauthorized', is_block=True)

    def new_conversation_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            if self.simulacrum.context.current_messages:
                self._send_message(message.chat.id, '⏳ Integrating memory...', is_block=True)
                self.simulacrum.integrate_memory()
                self._send_message(message.chat.id, '✅ Ready to chat', is_block=True)
            else:
                self._send_message(message.chat.id, '❌ No messages in conversation', is_block=True)
            return

    def retry_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            self.simulacrum.clear_messages(1)
            self._chat(message.chat.id, message_text=None)

    def tokens_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            percentage = round(self.simulacrum.llm.token_utilization_percentage)
            text = f'{self.simulacrum.llm.tokens} tokens in last request ({percentage}% of max)'
            self._send_message(message.chat.id, text, is_block=True)

    def clear_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            self.simulacrum.clear_messages()
            self._send_message(message.chat.id, '🗑️ Current conversation cleared', is_block=True)

    def remember_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            memory_text = re.search(r'/remember (.*)', message.text)
            if memory_text:
                self.simulacrum.append_memory(memory_text.group(1))
                self._send_message(message.chat.id, '✅ Added to memory', is_block=True)
            else:
                self._send_message(message.chat.id, '❌ No text provided', is_block=True)

    def reply_command_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            self._chat(message.chat.id, message_text=None)

    def help_command_handler(self, message):
        text = \
            "*/new* — Start a new conversation\n" \
            "*/retry* — Retry the last response\n" \
            "*/reply* — Reply to the last message\n" \
            "*/clear* — Clear the current conversation\n" \
            "*/remember <text>* — Add text to memory\n" \
            "*/tokens* — Show token utilization\n" \
            "*/help* — Show this help message"
        self._send_message(message.chat.id, text)

    def message_handler(self, message):
        with self._process_with_feedback(message.chat.id):
            self._chat(message.chat.id, message.text)

    def invalid_command_handler(self, message):
        self._send_message(message.chat.id, '❌ Command not recognized', is_block=True)

    #
    # Other
    #

    def is_unauthorized(self, message):
        return message.chat.id not in self.user_ids

    def is_command(self, message):
        return message.text.startswith('/')

    def _send_message(self, chat_id, text, is_block=False):
        formatted_text = f'```\n{text}\n```' if is_block else text
        self.telebot.send_message(chat_id, formatted_text, parse_mode='Markdown')

    def _warn_token_utilization(self, chat_id):
        percentage = round(self.simulacrum.llm.token_utilization_percentage)
        if percentage >= 80:
            shape, adverb = ['🔴', 'now'] if percentage >= 90 else ['🟠', 'soon']
            text = f'{shape} {percentage}% of max tokens used. Run /new {adverb}.'
            self._send_message(chat_id, text, is_block=True)

    def _chat(self, chat_id, message_text):
        response = self.simulacrum.chat(message_text)
        self._send_message(chat_id, response)
        self._warn_token_utilization(chat_id)

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
                self.telebot.send_chat_action(chat_id, action='typing')
                time.sleep(4)

        typing_thread = threading.Thread(target=send_typing_periodically)
        typing_thread.start()
        yield
        stop_typing_event.set()
        typing_thread.join()
