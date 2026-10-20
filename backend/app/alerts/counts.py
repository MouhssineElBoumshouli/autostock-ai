"""How surprising a week's sales count is, with a count model: Poisson for parts that sell evenly,
negative binomial for parts that sell unevenly (variance = mean + spread x mean²)."""

from math import exp, lgamma, log

import numpy as np


def spread(predicted: np.ndarray, actual: np.ndarray) -> float:
    """The part's extra spread beyond Poisson, from its own past weeks (forecast vs real counts),
    by the method of moments. 0 means Poisson is enough."""
    if len(predicted) == 0 or float((predicted**2).sum()) == 0:
        return 0.0
    return max(float((((actual - predicted) ** 2) - predicted).sum() / (predicted**2).sum()), 0.0)


def chance_at_most(count: int, mean: float, extra_spread: float) -> float:
    """Chance of selling `count` or fewer when `mean` was expected."""
    if count < 0:
        return 0.0
    return min(sum(exp(_log_chance(k, mean, extra_spread)) for k in range(count + 1)), 1.0)


def chance_at_least(count: int, mean: float, extra_spread: float) -> float:
    """Chance of selling `count` or more when `mean` was expected."""
    return max(1.0 - chance_at_most(count - 1, mean, extra_spread), 0.0)


def _log_chance(k: int, mean: float, extra_spread: float) -> float:
    if extra_spread < 1e-9:  # Poisson
        return k * log(mean) - mean - lgamma(k + 1)
    size = 1 / extra_spread
    return lgamma(k + size) - lgamma(size) - lgamma(k + 1) + size * log(size / (size + mean)) + k * log(mean / (size + mean))
