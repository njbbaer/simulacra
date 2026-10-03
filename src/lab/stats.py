import math
import random
import statistics
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

type Row = tuple[Hashable, str, float]


@dataclass(frozen=True)
class Effect:
    """The relative change from base to treatment, with a bootstrap 95% CI and the
    share of resamples in which the treatment came out below the base."""

    effect: float
    low: float
    high: float
    turns: int
    below: float

    def __str__(self) -> str:
        return (
            f"{self.effect:+.0%} (95% CI {self.low:+.0%} to {self.high:+.0%}, "
            f"{self.turns} turns, below base in {self.below:.0%} of resamples)"
        )


def paired_effect(
    rows: Iterable[Row],
    base: str,
    treatment: str,
    *,
    resamples: int = 5000,
    seed: int = 0,
) -> Effect:
    """Compare the conditions' means over turns that have both, resampling turns.

    Rows are (turn, condition, value), and samples are averaged within a turn."""
    means = {
        turn: (statistics.fmean(b), statistics.fmean(t))
        for turn, (b, t) in _paired(rows, base, treatment).items()
    }
    turns = list(means)

    def effect(sample: list[Hashable]) -> float:
        b = statistics.fmean(means[turn][0] for turn in sample)
        t = statistics.fmean(means[turn][1] for turn in sample)
        if not b:
            return math.copysign(math.inf, t) if t else 0.0
        return t / b - 1

    rng = random.Random(seed)
    boots = sorted(effect(rng.choices(turns, k=len(turns))) for _ in range(resamples))
    low, high = boots[round(0.025 * resamples)], boots[round(0.975 * resamples) - 1]
    below = sum(boot < 0 for boot in boots) / resamples
    return Effect(effect(turns), low, high, len(turns), below)


@dataclass(frozen=True)
class Pilot:
    """Variance of a paired comparison, estimated from pilot rows to size a run.

    The per-turn difference varies by `between` across turns, plus `within`
    divided by the samples of each condition per turn."""

    base_mean: float
    between: float
    within: float

    @classmethod
    def from_rows(cls, rows: Iterable[Row], base: str, treatment: str) -> Pilot:
        """Estimate from rows of (turn, condition, value) with repeat samples."""
        pairs = list(_paired(rows, base, treatment).values())
        if len(pairs) < 2:
            raise ValueError("The pilot needs at least two turns with both conditions")
        within_base = _pooled_variance(b for b, _ in pairs)
        within_treatment = _pooled_variance(t for _, t in pairs)
        diffs = [statistics.fmean(t) - statistics.fmean(b) for b, t in pairs]
        noise = statistics.fmean(
            within_base / len(b) + within_treatment / len(t) for b, t in pairs
        )
        return cls(
            base_mean=statistics.fmean(statistics.fmean(b) for b, _ in pairs),
            between=max(0.0, statistics.variance(diffs) - noise),
            within=within_base + within_treatment,
        )

    def detectable_effect(
        self, turns: int, samples: int, *, power: float = 0.8, alpha: float = 0.05
    ) -> float:
        """Return the smallest relative effect a run of this size detects."""
        spread = math.sqrt(self.variance(samples) / turns)
        return _z(power, alpha) * spread / self.base_mean

    def turns_needed(
        self, effect: float, samples: int, *, power: float = 0.8, alpha: float = 0.05
    ) -> int:
        """Return the turns needed to detect a relative effect of this size."""
        shift = effect * self.base_mean
        return math.ceil(self.variance(samples) * (_z(power, alpha) / shift) ** 2)

    def variance(self, samples: int) -> float:
        """Return the variance of one turn's difference with this many samples."""
        return self.between + self.within / samples


def _paired(
    rows: Iterable[Row], base: str, treatment: str
) -> dict[Hashable, tuple[list[float], list[float]]]:
    """Group values by turn, keeping turns that have both conditions."""
    values: dict[Hashable, dict[str, list[float]]] = {}
    for turn, condition, value in rows:
        if condition in (base, treatment):
            values.setdefault(turn, {}).setdefault(condition, []).append(value)
    return {
        turn: (v[base], v[treatment])
        for turn, v in values.items()
        if base in v and treatment in v
    }


def _pooled_variance(groups: Iterable[list[float]]) -> float:
    """Return the variance of samples around their turn's mean, pooled over turns."""
    squares = 0.0
    freedom = 0
    for group in groups:
        mean = statistics.fmean(group)
        squares += sum((x - mean) ** 2 for x in group)
        freedom += len(group) - 1
    if not freedom:
        raise ValueError("The pilot needs repeat samples of each condition")
    return squares / freedom


def _z(power: float, alpha: float) -> float:
    normal = statistics.NormalDist()
    return normal.inv_cdf(1 - alpha / 2) + normal.inv_cdf(power)
