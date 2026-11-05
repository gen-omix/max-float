import datetime
from collections import Counter

from max_float import config
from max_float.ingest import clean

URL = "https://ridb.recreation.gov/downloads/reservations{}.zip"


def rows(permits: list[int], ridb_id: str = "234624", year: int = 2021):
    start = datetime.date(year, 5, 15)
    return [
        {
            "date": (start + datetime.timedelta(day)).isoformat(),
            "weekday": "Monday",
            "river": "Selway",
            "ridb_id": ridb_id,
            "applications": "0",
            "permits": str(count),
            "source_url": URL.format(year),
        }
        for day, count in enumerate(permits)
    ]


def test_fiscal_year():
    assert clean.fiscal_year({"source_url": URL.format(2023)}) == 2023


def test_all_even_is_doubled():
    assert clean.doubled(rows([2, 4, 2, 0] * 10)) == {("234624", 2021)}


def test_some_odd_is_not_doubled():
    assert clean.doubled(rows([2, 4, 2, 1] * 10)) == set()


def test_few_dates_are_not_doubled():
    assert clean.doubled(rows([2, 4])) == set()


def test_launches_halve_only_doubled_years():
    data = rows([2, 4] * 10) + rows([1, 2] * 10, year=2022)
    out = clean.launches(data, Counter())
    assert [row["permits"] for row in out[:2]] == [1, 2]
    assert [int(row["permits"]) for row in out[20:22]] == [1, 2]


def test_launches_keep_the_lottery_season():
    out = clean.launches(rows([1] * 80), Counter())
    assert [row["date"] for row in out] == [
        (datetime.date(2021, 5, 15) + datetime.timedelta(day)).isoformat()
        for day in range(78)
    ]


def test_launches_keep_every_date_without_season_only(monkeypatch):
    monkeypatch.setattr(config, "SEASON_ONLY", False)
    assert len(clean.launches(rows([1] * 80), Counter())) == 80


def test_columns_drop_source():
    assert "source_url" not in clean.COLUMNS
