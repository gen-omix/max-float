"""Each river's lottery season, the application window and when unclaimed permits
are released, from the rules in `config`."""

import datetime
from zoneinfo import ZoneInfo

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


def in_season(river: str, date: datetime.date) -> bool:
    """Whether a launch date is in the river's lottery season."""
    start, end = season(river, date.year)
    return start <= date <= end


def window(year: int) -> tuple[datetime.date, datetime.date]:
    """When applications open and close for the lottery in `year`."""
    return on(config.OPENS, year - 1), on(config.DEADLINE, year)


def released(river: str, year: int) -> datetime.date:
    """The day the river's unclaimed lottery permits open to anyone in `year`."""
    usual = config.RELEASES[river][0]
    return on(config.RELEASED_ON.get(year, {}).get(river, usual), year)


def lottery_permit(river: str, launch: datetime.date, ordered: str) -> bool:
    """Whether a permit for a launch came from the river's lottery: ordered after
    applications closed and before unclaimed permits were released, on the
    lottery's clock. An order time without a zone is UTC, as RIDB's are, and one
    that can't be on the clock, like RIDB's few in year 1, isn't from the lottery."""
    if river not in config.RELEASES or not ordered:
        return False
    when = datetime.datetime.fromisoformat(ordered)
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.UTC)
    try:
        day = when.astimezone(ZoneInfo(config.RELEASES[river][1])).date()
    except OverflowError:
        return False
    return window(launch.year)[1] < day < released(river, launch.year)
