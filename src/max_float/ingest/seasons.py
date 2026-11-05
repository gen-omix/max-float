"""Each river's lottery season and the application window, as calendar rules.

A rule is a fixed day or the nth weekday of a month. The seasons are the first
and last launch dates with lottery applications in RIDB reservations, 2019–2025,
except the Rio Chama's end, which is from the Recreation.gov calendar for 2027.
The window is when those applications were submitted, in Pacific time.
"""

import datetime
from typing import NamedTuple


class Rule(NamedTuple):
    """A date in each lottery year: a fixed `day`, or the `n`th `weekday` (Monday
    is 0) of `month`, `lag` years from the lottery year."""

    month: int
    day: int = 0
    weekday: int = 0
    n: int = 0
    lag: int = 0

    def on(self, year: int) -> datetime.date:
        """The date for the lottery in `year`."""
        year += self.lag
        if not self.n:
            return datetime.date(year, self.month, self.day)
        first = datetime.date(year, self.month, 1)
        days = (self.weekday - first.weekday()) % 7 + 7 * (self.n - 1)
        return first + datetime.timedelta(days)


MONDAY, FRIDAY, SATURDAY = 0, 4, 5

OPENS = Rule(12, day=1, lag=-1)
DEADLINE = Rule(1, day=31)

SEASONS = {
    "Middle Fork Salmon": (Rule(5, day=28), Rule(9, day=3)),
    "Main Salmon": (Rule(6, day=20), Rule(9, day=7)),
    "Selway": (Rule(5, day=15), Rule(7, day=31)),
    "Snake - Hells Canyon": (Rule(5, weekday=FRIDAY, n=4), Rule(9, day=10)),
    "Rogue": (Rule(5, day=15), Rule(10, day=15)),
    "Green - Gates of Lodore": (
        Rule(5, weekday=MONDAY, n=2),
        Rule(9, weekday=FRIDAY, n=2),
    ),
    "Yampa": (Rule(5, weekday=MONDAY, n=2), Rule(7, weekday=SATURDAY, n=2)),
    "San Juan": (Rule(4, day=15), Rule(7, day=15)),
    "Green - Desolation/Gray": (Rule(5, day=1), Rule(9, day=30)),
    "Rio Chama": (Rule(4, weekday=FRIDAY, n=3), Rule(9, day=15)),
    "Salt": (Rule(3, day=1), Rule(5, day=15)),
}


def season(river: str, year: int) -> tuple[datetime.date, datetime.date]:
    """The river's first and last lottery launch dates in `year`."""
    start, end = SEASONS[river]
    return start.on(year), end.on(year)


def window(year: int) -> tuple[datetime.date, datetime.date]:
    """When applications open and close for the lottery in `year`."""
    return OPENS.on(year), DEADLINE.on(year)


def upcoming(today: datetime.date) -> int:
    """The first lottery year whose application deadline is not past."""
    return today.year if today <= DEADLINE.on(today.year) else today.year + 1
