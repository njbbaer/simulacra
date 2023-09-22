import telebot
import os
import yaml
from time import sleep
import pytest
from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum


class ExceptionHandler(telebot.ExceptionHandler):
    def __init__(self):
        self.exception = None

    def handle(self, exception):
        self.exception = exception


@pytest.fixture(scope="function")
def setup_teardown():
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

    with open(CONTEXT_FILENAME, 'w') as file:
        file.write(CONTEXT_CONTENT)

    yield CONTEXT_FILENAME  # This is where the test function will execute

    if os.path.exists(CONTEXT_FILENAME):
        os.remove(CONTEXT_FILENAME)


def create_text_message(text, user_id):
    params = {'text': text}
    chat = telebot.types.User(user_id, False, 'test')
    return telebot.types.Message(1, None, None, chat, 'text', params, "")


def test_message_handler(setup_teardown, mocker):
    TELEGRAM_USER_ID = '123'
    exception_handler = ExceptionHandler()
    simulacrum = Simulacrum(setup_teardown)
    telebot_instance = telebot.TeleBot('fake_token', exception_handler=exception_handler)
    TelegramBot(telebot_instance, simulacrum, TELEGRAM_USER_ID)

    mocker.patch.object(telebot_instance, 'send_message')
    mocker.patch.object(simulacrum.llm, 'fetch_completion', return_value='Hello User!')

    telebot_msg = create_text_message('Hello AI!', TELEGRAM_USER_ID)
    telebot_instance.process_new_messages([telebot_msg])

    sleep(0.1)

    if exception_handler.exception:
        raise exception_handler.exception

    telebot_instance.send_message.assert_called_once_with(TELEGRAM_USER_ID, 'Hello User!', parse_mode='Markdown')

    with open(setup_teardown, 'r') as file:
        context = yaml.safe_load(file)

    messages = context['conversations'][0]['messages']
    assert messages[-2]['content'] == 'Hello AI!'
    assert messages[-1]['content'] == 'Hello User!'
