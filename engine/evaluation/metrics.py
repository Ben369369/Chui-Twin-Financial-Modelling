"""Scoring rules. Lower CRPS is better; CRPS reduces to absolute error for a point forecast."""

from __future__ import annotations

import math

import numpy as np


def crps_samples(samples: np.ndarray, y: float) -> float:
    """CRPS = E|X - y| - 0.5 E|X - X'|, computed exactly from sorted samples."""
    x = np.sort(np.asarray(samples, dtype=float))
    n = len(x)
    term1 = float(np.mean(np.abs(x - y)))
    i = np.arange(1, n + 1)
    term2 = float(np.sum((2 * i - n - 1) * x)) / (n * n)  # = 0.5 E|X - X'|
    return term1 - term2


def crps_gaussian(mu: float, sd: float, y: float) -> float:
    if sd <= 0:
        return abs(y - mu)
    z = (y - mu) / sd
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return sd * (z * (2 * cdf - 1) + 2 * pdf - 1 / math.sqrt(math.pi))


def gaussian_interval(mu: float, sd: float, lo: float = 0.1, hi: float = 0.9) -> tuple[float, float]:
    z = 1.2815515655446004  # Phi^-1(0.9)
    assert (lo, hi) == (0.1, 0.9), "only the 80% interval is implemented"
    return mu - z * sd, mu + z * sd
