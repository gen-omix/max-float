import pytest

from max_float.odds import group_odds, season_odds


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
