import random

import pytest

from src.lab import Pilot, paired_effect


def simulate(turns: int, samples: int, between: float, within: float, seed: int):
    """Rows where treatment lowers a base of 10 by 2, with known variances."""
    rng = random.Random(seed)
    rows = []
    for turn in range(turns):
        level = rng.gauss(10, 3)
        shift = rng.gauss(-2, between**0.5)
        for _ in range(samples):
            rows.append((turn, "base", rng.gauss(level, within**0.5)))
            rows.append((turn, "treat", rng.gauss(level + shift, within**0.5)))
    return rows


def test_paired_effect_averages_samples_within_a_turn() -> None:
    rows = [
        ("a", "base", 2), ("a", "base", 4), ("a", "treat", 3),
        ("b", "base", 6), ("b", "treat", 3), ("b", "treat", 3),
        ("c", "treat", 100), ("a", "other", 100),
    ]  # fmt: skip

    effect = paired_effect(rows, "base", "treat", resamples=200)

    assert effect.turns == 2
    assert effect.effect == pytest.approx(-1 / 3)
    assert effect.low <= effect.effect <= effect.high


def test_paired_effect_bounds_resamples_without_base_hits() -> None:
    rows = [("a", "base", 1), ("a", "treat", 1)]
    rows += [(turn, cond, 0) for turn in "bcdefgh" for cond in ("base", "treat")]
    rows += [("i", "base", 0), ("i", "treat", 1)]

    effect = paired_effect(rows, "base", "treat", resamples=200)

    assert effect.effect == pytest.approx(1)
    assert effect.high == float("inf")


def test_paired_effect_reports_the_share_of_resamples_below_base() -> None:
    rows = simulate(40, 2, 1.0, 4.0, seed=2)

    assert paired_effect(rows, "base", "treat", resamples=500).below == 1.0
    assert paired_effect(rows, "treat", "base", resamples=500).below == 0.0


def test_pilot_separates_between_and_within_turn_variance() -> None:
    pilot = Pilot.from_rows(simulate(400, 3, 1.0, 4.0, seed=1), "base", "treat")

    assert pilot.between == pytest.approx(1.0, rel=0.3)
    assert pilot.within == pytest.approx(8.0, rel=0.1)
    assert pilot.base_mean == pytest.approx(10, rel=0.05)


def test_sizing_round_trips_and_more_samples_help() -> None:
    pilot = Pilot(base_mean=10, between=1, within=8)

    detectable = pilot.detectable_effect(40, 2)
    assert pilot.turns_needed(detectable, 2) == 40
    assert pilot.detectable_effect(40, 4) < detectable


def test_pilot_needs_repeat_samples() -> None:
    with pytest.raises(ValueError, match="repeat samples"):
        Pilot.from_rows(simulate(10, 1, 1.0, 4.0, seed=1), "base", "treat")
