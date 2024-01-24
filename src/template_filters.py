import random

import jinja2


def _shuffle_list(list):
    shuffled_list = list.copy()
    random.shuffle(shuffled_list)
    return shuffled_list


def register_filters():
    jinja2.filters.FILTERS["shuffle"] = _shuffle_list
