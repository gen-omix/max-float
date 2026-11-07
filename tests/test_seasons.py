from calendar import MONDAY
from datetime import date

from max_float.ingest import seasons


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


def test_release_days_fall_in_their_lotterys_year():
    assert seasons.released("Rio Chama", 2027) == date(2027, 4, 1)
    assert seasons.released("Salt", 2027) == date(2027, 2, 21)


def test_some_years_released_on_another_day():
    assert seasons.released("Main Salmon", 2019) == date(2019, 3, 23)
    assert seasons.released("Main Salmon", 2020) == date(2020, 3, 16)
    assert seasons.released("Salt", 2020) == date(2020, 2, 24)


def test_a_lottery_permit_is_ordered_after_the_deadline_and_before_the_release():
    launch = date(2025, 4, 1)
    assert not seasons.lottery_permit("Salt", launch, "2025-01-31T18:00:00Z")
    assert seasons.lottery_permit("Salt", launch, "2025-02-10T18:00:00Z")
    assert not seasons.lottery_permit("Salt", launch, "2025-02-21T15:00:00Z")
    assert not seasons.lottery_permit("Salt", launch, "2025-04-20T15:00:00Z")


def test_order_times_are_read_on_the_lotterys_clock():
    launch = date(2025, 4, 1)
    # 06:30 UTC on February 21 is still February 20 in Arizona.
    assert seasons.lottery_permit("Salt", launch, "2025-02-21T06:30:00Z")
    assert seasons.lottery_permit("Salt", launch, "2025-02-20T23:30:00-07:00")
    assert seasons.lottery_permit("Salt", launch, "2025-02-20 12:00:00")


def test_rivers_with_no_release_or_no_order_time_have_no_lottery_permits():
    launch = date(2025, 6, 1)
    assert not seasons.lottery_permit("Rogue", launch, "2025-02-20T18:00:00Z")
    assert not seasons.lottery_permit("Selway", launch, "")
    assert not seasons.lottery_permit("Selway", launch, "0001-01-01 00:00:00.000")


def test_every_river_with_a_season_but_the_rogue_has_a_release():
    from max_float import config

    assert set(config.SEASONS) - set(config.RELEASES) == {"Rogue"}
