from datetime import datetime

import pytz

from telegram.ext import filters


class StaleMessageFilter(filters.MessageFilter):
    SECONDS_STALE = 5

    def filter(self, message) -> bool:
        message_time = message.date
        current_time = datetime.now(pytz.utc)
        time_difference = (current_time - message_time).total_seconds()
        return time_difference > self.SECONDS_STALE
