import telebot
import yaml
import pytest
from time import sleep
from src.telegram_bot import TelegramBot
from src.simulacrum import Simulacrum

TELEGRAM_USER_ID = '123'
CONTEXT_PATH = './context.yml'
CONTEXT_CONTENT = {
    'names': {'assistant': 'AI', 'user': 'User'},
    'chat_prompt': 'You are modeling the mind of an AI under test.',
    'reinforcement_chat_prompt': 'Remember, you are modeling the mind of an AI under test.',
    'conversations': [
        {
            'memory': 'In its last coversation, the AI was told it would be tested by the user.',
            'messages': []
        }
    ]
}


class ExceptionHandler(telebot.ExceptionHandler):
    def __init__(self):
        self.exception = None

    def handle(self, exception):
        self.exception = exception


@pytest.fixture(scope="function")
def setup(fs):
    fs.create_file(CONTEXT_PATH, contents=yaml.dump(CONTEXT_CONTENT))


@pytest.fixture
def exception_handler():
    return ExceptionHandler()


@pytest.fixture
def simulacrum():
    return Simulacrum(CONTEXT_PATH)


@pytest.fixture
def telebot_instance(exception_handler):
    return telebot.TeleBot('fake_token', exception_handler=exception_handler)


def create_text_message(text, user_id):
    params = {'text': text}
    chat = telebot.types.User(user_id, False, 'test')
    return telebot.types.Message(1, None, None, chat, 'text', params, "")


def assert_context_last_messages(user_msg, ai_msg):
    with open(CONTEXT_PATH, 'r') as file:
        context = yaml.safe_load(file)

    messages = context['conversations'][0]['messages']
    assert messages[-2]['role'] == 'user'
    assert messages[-2]['content'] == user_msg
    assert messages[-1]['role'] == 'assistant'
    assert messages[-1]['content'] == ai_msg


def assert_sent_message(telebot_instance, message):
    telebot_instance.send_message.assert_called_once_with(
        TELEGRAM_USER_ID, message, parse_mode='Markdown'
    )


def test_message_handler(setup, telebot_instance, simulacrum, exception_handler, mocker, fs):
    TelegramBot(telebot_instance, simulacrum, TELEGRAM_USER_ID)
    mocker.patch.object(telebot_instance, 'send_message')
    mocker.patch.object(simulacrum.llm, 'fetch_completion', return_value='Hello User!')

    telebot_msg = create_text_message('Hello AI!', TELEGRAM_USER_ID)
    telebot_instance.process_new_messages([telebot_msg])

    sleep(0.1)

    if exception_handler.exception:
        raise exception_handler.exception

    assert_sent_message(telebot_instance, 'Hello User!')
    assert_context_last_messages('Hello AI!', 'Hello User!')
