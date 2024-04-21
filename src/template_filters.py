import random

import jinja2


def _shuffle_list(list):
    shuffled_list = list.copy()
    random.shuffle(shuffled_list)
    return shuffled_list


def _merge_lists(list1, list2):
    return list1 + list2


def register_filters():
    jinja2.filters.FILTERS["shuffle"] = _shuffle_list
    jinja2.filters.FILTERS["merge"] = _merge_lists
