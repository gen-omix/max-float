from datetime import date

from max_float.ingest import ridb, seasons
from max_float.ingest.seasons import Rule


def test_every_river_has_a_season():
    assert set(seasons.SEASONS) == set(ridb.RIVERS)


def test_fixed_day():
    assert Rule(5, day=15).on(2027) == date(2027, 5, 15)


def test_nth_weekday():
    assert Rule(5, weekday=seasons.MONDAY, n=2).on(2027) == date(2027, 5, 10)
    assert Rule(5, weekday=seasons.MONDAY, n=1).on(2028) == date(2028, 5, 1)


def test_lag():
    assert Rule(12, day=1, lag=-1).on(2027) == date(2026, 12, 1)


def test_dinosaur_2025():
    assert seasons.season("Green - Gates of Lodore", 2025) == (
        date(2025, 5, 12),
        date(2025, 9, 12),
    )
    assert seasons.season("Yampa", 2025) == (date(2025, 5, 12), date(2025, 7, 12))


def test_snake_starts_the_friday_before_memorial_day():
    memorial_days = {2021: 31, 2025: 26, 2027: 31}
    for year, day in memorial_days.items():
        start, _ = seasons.season("Snake - Hells Canyon", year)
        assert start == date(year, 5, day - 3)


def test_rio_chama_2027():
    assert seasons.season("Rio Chama", 2027) == (date(2027, 4, 16), date(2027, 9, 15))


def test_window():
    assert seasons.window(2027) == (date(2026, 12, 1), date(2027, 1, 31))


def test_upcoming():
    assert seasons.upcoming(date(2026, 11, 4)) == 2027
    assert seasons.upcoming(date(2027, 1, 31)) == 2027
    assert seasons.upcoming(date(2027, 2, 1)) == 2028
