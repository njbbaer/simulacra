import random
from typing import Any, List

import jinja2


def _shuffle_list(list: List[Any]) -> List[Any]:
    shuffled_list = list.copy()
    random.shuffle(shuffled_list)
    return shuffled_list


def _merge_lists(list1: List[Any], list2: List[Any]) -> List[Any]:
    return list1 + list2


def register_filters() -> None:
    jinja2.filters.FILTERS["shuffle"] = _shuffle_list
    jinja2.filters.FILTERS["merge"] = _merge_lists
