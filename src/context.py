import os
import re
from typing import Any, Dict, List, Optional

from .conversation import Conversation
from .types import ScaffoldConfig
from .yaml_config import yaml


class Context:
    def __init__(self, filepath: str) -> None:
        self._filepath = filepath

    def load(self) -> None:
        with open(self._filepath, "r") as file:
            self._data = yaml.load(file)
        self._load_conversation()

    def save(self) -> None:
        with open(self._filepath, "w") as file:
            yaml.dump(self._data, file)
        self._conversation.save()

    def add_message(
        self,
        role: str,
        message: str,
        image_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._conversation.add_message(role, message, image_url, metadata)

    def reset_conversation(self) -> None:
        self._conversation.reset()

    def new_conversation(self) -> None:
        self._data["conversation_id"] = self._next_conversation_id()
        self._load_conversation()

    def increment_cost(self, new_cost: float) -> None:
        self._data["total_cost"] += new_cost
        self._conversation.increment_cost(new_cost)

    def add_conversation_fact(self, fact: str) -> None:
        self._conversation.add_fact(fact)

    @property
    def conversation_messages(self) -> List[Dict[str, Any]]:
        return self._conversation.messages

    @property
    def conversation_facts(self) -> List[str]:
        return self._conversation.facts

    @property
    def conversation_cost(self) -> float:
        return self._conversation.cost

    @property
    def dir(self) -> str:
        return os.path.dirname(self._filepath)

    @property
    def conversations_dir(self) -> str:
        return f"{self.dir}/conversations"

    @property
    def vars(self) -> Dict[str, Any]:
        return self._data["vars"]

    @property
    def char_name(self) -> str:
        return self._data["char_name"]

    @property
    def api_provider(self) -> str:
        return self._data["api_provider"]

    @property
    def model(self) -> str:
        return self._data["model"]

    @property
    def conversation_id(self) -> int:
        return self._data.setdefault("conversation_id", self._next_conversation_id())

    @property
    def pricing(self) -> Optional[Dict[str, Any]]:
        return self._data.get("pricing", None)

    @property
    def provider(self) -> Optional[str]:
        return self._data.get("provider", None)

    @property
    def book_path(self) -> Optional[str]:
        path = self._data.get("book_path", None)
        if path:
            return os.path.join(self.dir, path)
        return None

    @property
    def last_book_position(self) -> Optional[int]:
        for message in reversed(self.conversation_messages):
            metadata = message.get("metadata", {})
            if "end_idx" in metadata:
                return metadata["end_idx"]
        return None

    @property
    def response_scaffold(self) -> ScaffoldConfig:
        scaffold_config_dict = self._data.get("response_scaffold", {})
        return ScaffoldConfig.from_dict(scaffold_config_dict)

    def _load_conversation(self) -> None:
        os.makedirs(self.conversations_dir, exist_ok=True)
        path = f"{self.conversations_dir}/{self.char_name}_{self.conversation_id}.yml"
        self._conversation = Conversation(path)
        self._conversation.load()

    def _next_conversation_id(self) -> int:
        max_id = max(
            (
                int(os.path.splitext(file)[0].split("_")[1])
                for file in os.listdir(self.conversations_dir)
                if re.match(rf"^{self.char_name}_\d+\.yml$", file)
            ),
            default=0,
        )
        return max_id + 1
