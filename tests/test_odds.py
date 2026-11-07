import datetime

import pytest

from max_float import config
from max_float.ingest import seasons
from max_float.odds import (
    group_odds,
    history,
    launch_odds,
    season_odds,
    weekday_effect,
)


def test_one_application():
    assert group_odds([0.05]) == pytest.approx(0.05)


def test_no_applications():
    assert group_odds([]) == 0.0


def test_independent_applications():
    assert group_odds([0.5, 0.5]) == pytest.approx(0.75)


def test_rejects_invalid_odds():
    with pytest.raises(ValueError):
        group_odds([1.5])


def row(date, river, applications, permits):
    return {
        "date": date,
        "river": river,
        "applications": str(applications),
        "permits": str(permits),
    }


def test_season_odds_use_lottery_dates_only():
    rows = [
        row("2025-07-07", "Selway", 100, 1),
        row("2025-07-08", "Selway", 98.5, 1),
        row("2025-10-01", "Selway", 0, 3),
    ]
    assert season_odds(rows) == {("Selway", 2025): pytest.approx(2 / 198.5)}


def test_season_odds_without_permits():
    assert season_odds([row("2025-07-07", "Rogue", 50, 0)]) == {("Rogue", 2025): None}


SALT_FACTORS = {0: 1.5, 1: 1.0, 2: 0.9, 3: 1.0, 4: 1.1, 5: 0.6, 6: 0.9}


def salt_season(year, level, permits=4.0, factors=SALT_FACTORS):
    """A Salt season whose applications rise each week, times weekday factors."""
    start, end = seasons.season("Salt", year)
    past = {}
    for offset in range((end - start).days + 1):
        date = start + datetime.timedelta(offset)
        past[date] = level * (1 + offset // 7) * factors[date.weekday()], permits
    return past


def test_weekday_effect_recovers_factors():
    past = salt_season(2024, 50) | salt_season(2025, 80)
    effect = weekday_effect("Salt", {date: a for date, (a, _) in past.items()})
    ratio = {k: effect[k] / SALT_FACTORS[k] for k in effect}
    assert max(ratio.values()) == pytest.approx(min(ratio.values()))


def test_launch_odds_scale_to_the_latest_season():
    past = salt_season(2024, 50, permits=2.0) | salt_season(2025, 100)
    launches = launch_odds("Salt", past, 2025)
    latest = salt_season(2025, 100)
    for launch in launches:
        applications, permits = latest[launch["date"]]
        assert launch["applications"] == pytest.approx(applications, abs=0.05)
        assert launch["permits"] == pytest.approx(permits)
        assert launch["odds"] == pytest.approx(permits / applications, abs=1e-4)


def test_launch_odds_scale_is_the_latest_seasons_overall_odds():
    past = salt_season(2024, 50) | salt_season(2025, 100)
    past[datetime.date(2025, 3, 1)] = 300.0, 30.0
    latest = [launch for date, launch in past.items() if date.year == 2025]
    overall = sum(p for _, p in latest) / sum(a for a, _ in latest)
    scales = {launch["scale_2025"] for launch in launch_odds("Salt", past, 2027)}
    assert scales == {round(overall, 4)}


def test_launch_odds_interval_closes_when_seasons_agree():
    past = salt_season(2024, 50, permits=2.0) | salt_season(2025, 100)
    for launch in launch_odds("Salt", past, 2025):
        assert launch["odds_low"] == launch["odds"] == launch["odds_high"]


def test_launch_odds_interval_spans_seasons_that_differ():
    past = salt_season(2024, 50) | salt_season(2025, 100)
    past[datetime.date(2024, 3, 1)] = past[datetime.date(2024, 3, 1)][0], 8.0
    launch = launch_odds("Salt", past, 2025)[0]
    assert launch["odds_low"] < launch["odds"] < launch["odds_high"]


def test_launch_odds_moves_to_the_target_years_dates():
    launches = launch_odds("Salt", salt_season(2025, 100), 2027)
    assert launches[0]["date"] == datetime.date(2027, 3, 1)
    assert launches[0]["weekday"] == "Monday"


def test_launch_odds_skip_days_missing_from_most_seasons():
    past = salt_season(2023, 50) | salt_season(2024, 50) | salt_season(2025, 50)
    for year in (2023, 2024):
        del past[datetime.date(year, 3, 10)]
    dates = {launch["date"] for launch in launch_odds("Salt", past, 2025)}
    assert datetime.date(2025, 3, 10) not in dates
    assert datetime.date(2025, 3, 11) in dates


def test_outfitter_days_are_never_lottery_launches(monkeypatch):
    monkeypatch.setitem(config.OUTFITTER_LAUNCHES, "Salt", ((3, 10),))
    past = salt_season(2023, 50) | salt_season(2024, 50) | salt_season(2025, 50)
    dates = {launch["date"] for launch in launch_odds("Salt", past, 2025)}
    assert datetime.date(2025, 3, 10) not in dates


def test_a_river_with_outfitter_days_keeps_a_day_one_season_had(monkeypatch):
    monkeypatch.setitem(config.OUTFITTER_LAUNCHES, "Salt", ((3, 10),))
    past = salt_season(2023, 50) | salt_season(2024, 50) | salt_season(2025, 50)
    for year in (2023, 2024):
        del past[datetime.date(year, 3, 11)]
    dates = {launch["date"] for launch in launch_odds("Salt", past, 2025)}
    assert datetime.date(2025, 3, 11) in dates


def test_selway_has_62_private_launches_and_16_outfitter_days():
    start, end = seasons.season("Selway", 2027)
    assert (end - start).days + 1 - len(config.OUTFITTER_LAUNCHES["Selway"]) == 62
    assert len(set(config.OUTFITTER_LAUNCHES["Selway"])) == 16


def test_launch_odds_round_to_odds_digits(monkeypatch):
    monkeypatch.setattr(config, "ODDS_DIGITS", 2)
    past = salt_season(2024, 50, permits=3.0) | salt_season(2025, 70, permits=3.0)
    for launch in launch_odds("Salt", past, 2025):
        for key in ("odds", "odds_low", "odds_high", "scale_2025"):
            assert launch[key] == round(launch[key], 2)


def test_launch_odds_without_permits():
    launches = launch_odds("Salt", salt_season(2025, 100, permits=0.0), 2025)
    blank = {"permits", "odds", "odds_low", "odds_high", "scale_2025"}
    assert {launch[key] for launch in launches for key in blank} == {None}


def test_history_keeps_lottery_launches():
    rows = [
        row("2025-03-01", "Salt", 5, 1),
        row("2025-03-02", "Salt", 0, 1),
        row("2025-06-01", "Salt", 5, 1),
        row("2025-03-03", "Selway", 5, 1),
    ]
    assert history(rows, "Salt") == {datetime.date(2025, 3, 1): (5.0, 1.0)}
