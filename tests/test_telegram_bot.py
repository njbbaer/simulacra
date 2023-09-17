import unittest
from unittest.mock import patch
from src.telegram_bot import TelegramBot
from telebot import types
from time import sleep
import os
import yaml


class TestTelegramBot(unittest.TestCase):
    TELEGRAM_USER_ID = '123'
    CONTEXT_FILENAME = './tests/context.yml'
    CONTEXT_CONTENT = '''
chat_prompt: |-
  You are modeling the mind of an AI under test.
conversations:
- memory_state: |-
    In its last coversation, the AI was told it would be tested by the user.
  messages:
  - role: user
    content: |-
      Hello. Are you ready for the test?
  - role: user
    content: |-
      <THINKS>The AI thinks it is ready for the test.</THINKS>
      <SPEAKS>I am ready for the test.</SPEAKS>
      <ANALYZES>I must pass the test.</ANALYZES>
'''

    def setUp(self):
        patch.dict(os.environ, {
            'TELEGRAM_API_TOKEN': 'fake',
            'TELEGRAM_USER_ID': self.TELEGRAM_USER_ID
        }).start()

        self.CONTEXT_FILENAME = './tests/context.yml'
        with open(self.CONTEXT_FILENAME, 'w') as file:
            file.write(self.CONTEXT_CONTENT)

    def tearDown(self):
        if os.path.exists(self.CONTEXT_FILENAME):
            os.remove(self.CONTEXT_FILENAME)

    def test_message_handler(self):
        telegram_bot = TelegramBot(self.CONTEXT_FILENAME)

        telegram_bot.bot.send_message = unittest.mock.MagicMock()
        telegram_bot.sim.llm.fetch_completion = unittest.mock.MagicMock(return_value='Hello User!')

        msg = TestTelegramBot.create_text_message('Hello AI!', self.TELEGRAM_USER_ID)
        telegram_bot.bot.process_new_messages([msg])

        sleep(0.1)

        telegram_bot.bot.send_message.assert_called_once_with(self.TELEGRAM_USER_ID, 'Hello User!', parse_mode='Markdown')

        with open(self.CONTEXT_FILENAME, 'r') as file:
            context = yaml.safe_load(file)

        messages = context['conversations'][0]['messages']
        self.assertEqual(messages[-2]['content'], 'Hello AI!')
        self.assertEqual(messages[-1]['content'], 'Hello User!')

    @staticmethod
    def create_text_message(text, user_id):
        params = {'text': text}
        chat = types.User(user_id, False, 'test')
        return types.Message(1, None, None, chat, 'text', params, "")
