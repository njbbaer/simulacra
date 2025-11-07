import math


class CostTracker:
    def __init__(
        self,
        high_message_threshold: float = 0.25,
        warn_message_threshold: float = 0.15,
        warn_total_threshold: float = 1.0,
        high_total_threshold: float = 3.0,
    ) -> None:
        self.high_message_threshold = high_message_threshold
        self.warn_message_threshold = warn_message_threshold
        self.warn_total_threshold = warn_total_threshold
        self.high_total_threshold = high_total_threshold
        self.last_warned_cost = 0

    def get_cost_warnings(
        self, last_message_cost: float | None, total_cost: float
    ) -> list[str]:
        if not last_message_cost:
            return []

        warnings = []

        if last_message_cost > self.warn_message_threshold:
            symbol = "🔴" if last_message_cost > self.high_message_threshold else "🟡"
            warnings.append(f"{symbol} Last message cost: ${last_message_cost:.2f}")

        if total_cost > self.last_warned_cost + self.warn_total_threshold:
            self.last_warned_cost = math.floor(total_cost)
            symbol = "🔴" if total_cost > self.high_total_threshold else "🟡"
            warnings.append(f"{symbol} Conversation cost: ${total_cost:.2f}")

        return warnings

    def reset(self) -> None:
        self.last_warned_cost = 0
