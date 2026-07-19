"""Deterministic aggregation statistics for self-play result pooling."""

from __future__ import annotations

from math import fsum
from random import Random
from statistics import mean
from typing import Iterable

__all__ = ["bootstrap_ci"]


def bootstrap_ci(
    values: Iterable[float],
    *,
    seed: int | str | bytes | bytearray | None,
    iterations: int,
    alpha: float,
) -> tuple[float, float, float]:
    """Return a bootstrap mean estimate and percentile confidence interval.

    The implementation is intentionally deterministic for a fixed seed and uses
    only the standard library. The interval is computed from bootstrap means via
    the usual alpha/2 and 1-alpha/2 percentiles.
    """

    samples = [float(value) for value in values]
    if not samples:
        raise ValueError("bootstrap_ci requires at least one value")
    if iterations <= 0:
        raise ValueError("bootstrap_ci requires iterations > 0")
    if not 0 < alpha < 1:
        raise ValueError("bootstrap_ci requires 0 < alpha < 1")

    point = mean(samples)
    if len(samples) == 1 or all(value == samples[0] for value in samples):
        return point, point, point

    rng = Random(seed)
    bootstrap_means = [
        fsum(samples[rng.randrange(len(samples))] for _ in range(len(samples)))
        / len(samples)
        for _ in range(iterations)
    ]
    bootstrap_means.sort()
    lower = _percentile(bootstrap_means, alpha / 2)
    upper = _percentile(bootstrap_means, 1 - alpha / 2)
    return point, lower, upper


def _percentile(values: list[float], q: float) -> float:
    """Return the q-quantile using linear interpolation between neighbors."""

    if q <= 0:
        return values[0]
    if q >= 1:
        return values[-1]

    position = q * (len(values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - lower_index
    lower = values[lower_index]
    upper = values[upper_index]
    return lower + (upper - lower) * fraction
