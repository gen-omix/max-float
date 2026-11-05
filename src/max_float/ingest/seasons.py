"""Each river's lottery season and the application window, from the rules in
`config`."""

import datetime

from max_float import config


def on(rule: tuple[int, ...], year: int) -> datetime.date:
    """The date a (month, day) or (month, weekday, n) rule falls on in `year`,
    where (month, weekday, n) is the nth weekday of the month and Monday is 0."""
    if len(rule) == 2:
        return datetime.date(year, *rule)
    month, weekday, n = rule
    first = datetime.date(year, month, 1)
    return first + datetime.timedelta((weekday - first.weekday()) % 7 + 7 * (n - 1))


def season(river: str, year: int) -> tuple[datetime.date, datetime.date]:
    """The river's first and last lottery launch dates in `year`."""
    start, end = config.SEASONS[river]
    return on(start, year), on(end, year)


def window(year: int) -> tuple[datetime.date, datetime.date]:
    """When applications open and close for the lottery in `year`."""
    return on(config.OPENS, year - 1), on(config.DEADLINE, year)
