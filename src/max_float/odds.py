"""Permit odds.

Odds for a launch come from every past season of its river:

1. Applications vary by weekday. A Poisson model with a level for each week of
   each season and a factor for each weekday separates the two.
2. Each past launch is matched to the same day of the season, its applications
   divided by its weekday's factor, and its applications and permits scaled so
   its season's mean per launch matches the most recent season's.
3. A day of the season is a lottery launch if it was one in at least
   `config.LAUNCH_SHARE` of the river's past seasons. Its odds are the day's mean
   permits over the day's mean applications times its own weekday's factor.
4. The odds' interval resamples the day's past seasons. The scale is the most
   recent season's overall odds: its permits over its applications.
"""

import csv
import datetime
import random
import sys
from collections import defaultdict
from collections.abc import Iterable
from math import prod
from statistics import fmean, quantiles

from max_float import config
from max_float.ingest import reservations, seasons

COLUMNS = [
    "date",
    "weekday",
    "river",
    "ridb_id",
    "applications",
    "permits",
    "odds",
    "odds_low",
    "odds_high",
]


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


def day(river: str, date: datetime.date) -> int:
    """Days from the river's first lottery launch that year."""
    return (date - seasons.season(river, date.year)[0]).days


def history(
    rows: Iterable[dict[str, str]], river: str
) -> dict[datetime.date, tuple[float, float]]:
    """Applications and permits for the river's past lottery launches: those in
    its season with at least one application."""
    found = {}
    for row in rows:
        date = datetime.date.fromisoformat(row["date"])
        if row["river"] != river or not float(row["applications"]):
            continue
        start, end = seasons.season(river, date.year)
        if start <= date <= end:
            found[date] = float(row["applications"]), float(row["permits"])
    return found


def weekday_effect(
    river: str, applications: dict[datetime.date, float], tolerance: float = 1e-10
) -> dict[int, float]:
    """Each weekday's factor on applications (Monday is 0), averaging 1 over the
    launches, with a level for each week of each season."""
    week = {date: (date.year, day(river, date) // 7) for date in applications}
    effect = {date.weekday(): 1.0 for date in applications}
    while True:
        level: dict[tuple[int, int], float] = defaultdict(float)
        weight: dict[tuple[int, int], float] = defaultdict(float)
        for date, count in applications.items():
            level[week[date]] += count
            weight[week[date]] += effect[date.weekday()]
        totals: dict[int, float] = defaultdict(float)
        expected: dict[int, float] = defaultdict(float)
        for date, count in applications.items():
            totals[date.weekday()] += count
            expected[date.weekday()] += level[week[date]] / weight[week[date]]
        new = {weekday: totals[weekday] / expected[weekday] for weekday in effect}
        mean = fmean(new[date.weekday()] for date in applications)
        new = {weekday: factor / mean for weekday, factor in new.items()}
        done = max(abs(new[weekday] - effect[weekday]) for weekday in effect)
        effect = new
        if done < tolerance:
            return effect


def interval(launches: list[tuple[float, float]]) -> tuple[float, float]:
    """`config.INTERVAL` percent bootstrap interval of permits over applications,
    from `config.DRAWS` resamples of the (applications, permits) launches."""
    rng = random.Random(0)
    odds = []
    for _ in range(config.DRAWS):
        sample = rng.choices(launches, k=len(launches))
        odds.append(min(1.0, sum(p for _, p in sample) / sum(a for a, _ in sample)))
    cuts = quantiles(odds, n=100)
    tail = (100 - config.INTERVAL) // 2
    return cuts[tail - 1], cuts[-tail]


def launch_odds(
    river: str, past: dict[datetime.date, tuple[float, float]], year: int
) -> list[dict[str, object]]:
    """Expected applications, permits and odds for each of the river's lottery
    launches in `year`, at the most recent season's level, with the odds' interval
    and `scale_{latest year}`, that season's overall odds. All but applications
    are None when the river's most recent season has no permits."""
    effect = weekday_effect(river, {date: a for date, (a, _) in past.items()})
    neutral = {date: (a / effect[date.weekday()], p) for date, (a, p) in past.items()}
    by_year: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for date, launch in neutral.items():
        by_year[date.year].append(launch)
    means = {
        y: (fmean(a for a, _ in launches), fmean(p for _, p in launches))
        for y, launches in by_year.items()
    }
    latest = max(means)
    latest_a, latest_p = means[latest]
    recent = [launch for date, launch in past.items() if date.year == latest]
    total_p = sum(p for _, p in recent)
    scale = total_p / sum(a for a, _ in recent) if total_p else None
    by_day: dict[int, list[tuple[float, float | None]]] = defaultdict(list)
    for date, (a, p) in neutral.items():
        mean_a, mean_p = means[date.year]
        scaled = p * latest_p / mean_p if mean_p else None
        by_day[day(river, date)].append((a * latest_a / mean_a, scaled))
    start, end = seasons.season(river, year)
    out = []
    for offset in range((end - start).days + 1):
        date = start + datetime.timedelta(offset)
        launches = by_day[offset]
        rare = len(launches) < config.LAUNCH_SHARE * len(means)
        if rare or date.weekday() not in effect:
            continue
        factor = effect[date.weekday()]
        applications = factor * fmean(a for a, _ in launches)
        drawn = [(factor * a, p) for a, p in launches if p is not None]
        permits = odds = low = high = None
        if latest_p and drawn:
            permits = fmean(p for _, p in drawn)
            odds = min(1.0, permits / applications)
            low, high = interval(drawn)
        out.append(
            {
                "date": date,
                "weekday": date.strftime("%A"),
                "river": river,
                "applications": round(applications, 1),
                "permits": None if permits is None else round(permits, 2),
                "odds": None if odds is None else round(odds, 4),
                "odds_low": None if low is None else round(low, 4),
                "odds_high": None if high is None else round(high, 4),
                f"scale_{latest}": None if scale is None else round(scale, 4),
            }
        )
    return out


def main(year: int = config.YEAR) -> None:
    """Write odds for every river's lottery launches in `year`."""
    with config.CLEANED_CSV.open(newline="") as file:
        rows = list(csv.DictReader(file))
    out = [
        launch | {"ridb_id": ridb_id}
        for river, ridb_id in config.RIVERS.items()
        for launch in launch_odds(river, history(rows, river), year)
    ]
    scales = sorted(
        {key for launch in out for key in launch if key.startswith("scale_")}
    )
    reservations.write(out, config.ODDS_CSV, COLUMNS + scales)


if __name__ == "__main__":
    main(*(int(arg) for arg in sys.argv[1:]))
