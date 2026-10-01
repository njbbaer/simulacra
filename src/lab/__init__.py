"""Replay logged turns and run experiment batches; see README.md."""

import os

import dotenv

from ..utilities import PROJECT_ROOT
from .batch import BatchSummary, run_batch
from .calls import complete, parse_tag
from .replay import (
    Result,
    Turn,
    assistant_turns,
    combine,
    draft,
    replay,
    take_snapshot,
    totals,
)
from .sampling import sample_turns
from .stats import Effect, Pilot, paired_effect

dotenv.load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

__all__ = [
    "BatchSummary",
    "Effect",
    "Pilot",
    "Result",
    "Turn",
    "assistant_turns",
    "combine",
    "complete",
    "draft",
    "paired_effect",
    "parse_tag",
    "replay",
    "run_batch",
    "sample_turns",
    "take_snapshot",
    "totals",
]
