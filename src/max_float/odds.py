"""Permit odds."""

from collections.abc import Iterable
from math import prod


def group_odds(odds: Iterable[float]) -> float:
    """Chance that at least one of several independent applications wins."""
    values = list(odds)
    if any(not 0.0 <= p <= 1.0 for p in values):
        raise ValueError("odds must be between 0 and 1")
    return 1.0 - prod(1.0 - p for p in values)
