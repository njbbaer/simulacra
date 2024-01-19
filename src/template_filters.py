import random

import jinja2


def _shuffle_list(value):
    random.shuffle(value)
    return value


def register_filters():
    jinja2.filters.FILTERS["shuffle"] = _shuffle_list
