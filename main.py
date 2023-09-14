import argparse

from src.telegram_bot import configure_bot

if __name__ == "__main__":
    bot = configure_bot()
    bot.infinity_polling()
