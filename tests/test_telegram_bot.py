import unittest
from unittest.mock import patch
import telebot
from time import sleep
import os
import yaml

from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum


class ExceptionHandler(telebot.ExceptionHandler):
    def __init__(self):
        self.exception = None

    def handle(self, exception):
        self.exception = exception


class TestTelegramBot(unittest.TestCase):
    TELEGRAM_USER_ID = '123'
    CONTEXT_FILENAME = './tests/context.yml'
    CONTEXT_CONTENT = '''
names:
  assistant: AI
  user: User
chat_prompt: |-
  You are modeling the mind of an AI under test.
reinforcement_chat_prompt: |-
  Remember, you are modeling the mind of an AI under test.
conversations:
- memory: |-
    In its last coversation, the AI was told it would be tested by the user.
  messages:
  - role: user
    content: |-
      Hello. Are you ready for the test?
  - role: user
    content: |-
      <THINK>The AI thinks it is ready for the test.</THINK>
      <MESSAGE>I am ready for the test.</MESSAGE>
      <ANALYZE>I must pass the test.</ANALYZE>
'''

    def setUp(self):
        self.CONTEXT_FILENAME = './tests/context.yml'
        with open(self.CONTEXT_FILENAME, 'w') as file:
            file.write(self.CONTEXT_CONTENT)

    def tearDown(self):
        if os.path.exists(self.CONTEXT_FILENAME):
            os.remove(self.CONTEXT_FILENAME)

    def test_message_handler(self):
        exception_handler = ExceptionHandler()
        simulacrum = Simulacrum(self.CONTEXT_FILENAME)
        telebot_instance = telebot.TeleBot('fake_token', exception_handler=exception_handler)
        TelegramBot(telebot_instance, simulacrum, self.TELEGRAM_USER_ID)

        telebot_instance.send_message = unittest.mock.MagicMock()
        simulacrum.llm.fetch_completion = unittest.mock.MagicMock(return_value='Hello User!')

        telebot_msg = self.create_text_message('Hello AI!', self.TELEGRAM_USER_ID)
        telebot_instance.process_new_messages([telebot_msg])

        sleep(0.1)

        if exception_handler.exception:
            raise exception_handler.exception

        telebot_instance.send_message.assert_called_once_with(self.TELEGRAM_USER_ID, 'Hello User!', parse_mode='Markdown')

        with open(self.CONTEXT_FILENAME, 'r') as file:
            context = yaml.safe_load(file)

        messages = context['conversations'][0]['messages']
        self.assertEqual(messages[-2]['content'], 'Hello AI!')
        self.assertEqual(messages[-1]['content'], 'Hello User!')

    @staticmethod
    def create_text_message(text, user_id):
        params = {'text': text}
        chat = telebot.types.User(user_id, False, 'test')
        return telebot.types.Message(1, None, None, chat, 'text', params, "")
