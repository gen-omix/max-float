from calendar import MONDAY
from datetime import date

from max_float import config
from max_float.ingest import seasons


def test_every_river_has_a_season():
    assert set(config.SEASONS) == set(config.RIVERS)


def test_fixed_day():
    assert seasons.on((5, 15), 2027) == date(2027, 5, 15)


def test_nth_weekday():
    assert seasons.on((5, MONDAY, 2), 2027) == date(2027, 5, 10)
    assert seasons.on((5, MONDAY, 1), 2028) == date(2028, 5, 1)


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


def test_in_season():
    assert seasons.in_season("Salt", date(2025, 3, 1))
    assert seasons.in_season("Salt", date(2025, 5, 15))
    assert not seasons.in_season("Salt", date(2025, 5, 16))


def test_window_opens_the_year_before():
    assert seasons.window(2027) == (date(2026, 12, 1), date(2027, 1, 31))
