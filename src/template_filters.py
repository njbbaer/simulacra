import random
from typing import Any

import jinja2


def _shuffle_list(items: list[Any]) -> list[Any]:
    shuffled = items.copy()
    random.shuffle(shuffled)
    return shuffled


def _merge_lists(list1: list[Any] | None, list2: list[Any] | None) -> list[Any]:
    return (list1 or []) + (list2 or [])


def register_filters() -> None:
    jinja2.filters.FILTERS["shuffle"] = _shuffle_list
    jinja2.filters.FILTERS["merge"] = _merge_lists
