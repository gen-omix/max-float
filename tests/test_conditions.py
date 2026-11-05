import csv
from datetime import date

from max_float.ingest import conditions, reservations


def test_a_row_for_each_day_of_each_year():
    rows = conditions.days("Salt", {}, range(2024, 2026))
    assert len(rows) == 366 + 365
    assert rows[0]["date"] == date(2024, 1, 1)
    assert rows[-1]["date"] == date(2025, 12, 31)


def test_flow_and_category():
    rows = conditions.days("Salt", {date(2025, 1, 1): 1_500.0}, range(2025, 2026))
    assert rows[0] == {
        "date": date(2025, 1, 1),
        "river": "Salt",
        "ridb_id": 249275,
        "gauge_id": "09497500",
        "flow_cfs": 1_500.0,
        "flow_step": 3,
        "flow_category": "normal",
    }


def test_no_reading_is_blank_and_no_flow_is_not_running(tmp_path):
    flows = {date(2025, 1, 1): 0.0}
    rows = conditions.days("Salt", flows, range(2025, 2026))
    path = tmp_path / "conditions.csv"
    reservations.write(rows, path, conditions.COLUMNS)
    written = list(csv.DictReader(path.open()))
    assert written[0]["flow_category"] == "not running"
    assert written[1]["flow_cfs"] == written[1]["flow_category"] == ""
    assert written[1]["flow_step"] == ""
