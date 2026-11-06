import csv
from datetime import date

import pytest

from max_float import config
from max_float.ingest import conditions, reservations


def test_a_row_for_each_day_of_each_year():
    rows = conditions.days("Salt", {}, "S", {}, range(2024, 2026))
    assert len(rows) == 366 + 365
    assert rows[0]["date"] == date(2024, 1, 1)
    assert rows[-1]["date"] == date(2025, 12, 31)


def test_flow_temperature_and_categories():
    rows = conditions.days(
        "Salt",
        {date(2025, 1, 1): 1_500.0},
        "USC00023501",
        {date(2025, 1, 1): (75.0, 41.0)},
        range(2025, 2026),
    )
    assert rows[0] == {
        "date": date(2025, 1, 1),
        "river": "Salt",
        "ridb_id": 249275,
        "gauge_id": "09497500",
        "flow_cfs": 1_500.0,
        "flow_step": 3,
        "flow_category": "normal",
        "station_id": "USC00023501",
        "high_f": 75.0,
        "low_f": 41.0,
        "temperature_step": 2,
        "temperature_category": "mild",
    }


@pytest.mark.parametrize(
    ("high", "category"),
    [
        (-5, "cold"),
        (59, "cold"),
        (60, "cool"),
        (69, "cool"),
        (70, "mild"),
        (80, "warm"),
        (90, "hot"),
        (99, "hot"),
        (100, "extra hot"),
    ],
)
def test_temperature_categories_match_the_graph_scale(high, category):
    step = conditions.temperature_step(high)
    assert config.TEMPERATURE_CATEGORIES[step] == category


def test_no_reading_is_blank_and_no_flow_is_not_running(tmp_path):
    day = date(2025, 1, 1)
    rows = conditions.days("Salt", {day: 0.0}, "S", {}, range(2025, 2026))
    path = tmp_path / "conditions.csv"
    reservations.write(rows, path, conditions.COLUMNS)
    written = list(csv.DictReader(path.open()))
    assert written[0]["flow_category"] == "not running"
    assert written[0]["high_f"] == written[0]["temperature_category"] == ""
    assert written[1]["flow_cfs"] == written[1]["flow_category"] == ""
    assert written[1]["flow_step"] == ""


def test_a_high_without_a_low_still_has_a_category():
    day = date(2025, 1, 1)
    rows = conditions.days("Salt", {}, "S", {day: (95.0, None)}, range(2025, 2026))
    assert rows[0]["low_f"] is None
    assert rows[0]["temperature_category"] == "hot"
