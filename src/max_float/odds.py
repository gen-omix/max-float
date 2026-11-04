"""Permit odds."""

from collections import defaultdict
from collections.abc import Iterable
from math import prod


def group_odds(odds: Iterable[float]) -> float:
    """Chance that at least one of several independent applications wins."""
    values = list(odds)
    if any(not 0.0 <= p <= 1.0 for p in values):
        raise ValueError("odds must be between 0 and 1")
    return 1.0 - prod(1.0 - p for p in values)


def season_odds(rows: Iterable[dict[str, str]]) -> dict[tuple[str, int], float | None]:
    """Overall odds per (river, season) from launch rows like applications.csv.

    Odds are the permits on lottery dates, those with at least one application,
    over the applications. None when a river has no permits on its lottery dates.
    """
    permits: dict[tuple[str, int], int] = defaultdict(int)
    applications: dict[tuple[str, int], float] = defaultdict(float)
    for row in rows:
        if float(row["applications"]) > 0:
            key = row["river"], int(row["date"][:4])
            applications[key] += float(row["applications"])
            permits[key] += int(row["permits"])
    return {
        key: permits[key] / applications[key] if permits[key] else None
        for key in applications
    }
