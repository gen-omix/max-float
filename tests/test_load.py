import datetime
import re

from max_float import config
from max_float.graph import load

D = datetime.date(2027, 6, 1)


def river(name="Salt", ridb_id="249275", **changes):
    row = {
        "river": name,
        "ridb_id": ridb_id,
        "ridb_name": "Salt River Canyon Wilderness Permit",
        "agency": "USDA Forest Service",
        "section": "Gleason Flat to Highway 288",
        "latitude": "33.8",
        "longitude": "-110.5",
        "year": "2027",
        "applications_open": "2026-12-01",
        "application_deadline": "2027-01-31",
        "season_start": "2027-03-01",
        "season_end": "2027-05-15",
        "choices_per_application": "3",
        "applications_per_person": "1",
        "on_trip": "holder",
        "permits_per_person": "",
        "launches_per_day": "4",
        "max_group": "15",
        "max_trip_days": "2",
        "rules_source": "https://www.recreation.gov/permits/249275",
        "gauge_id": "09497500",
        "gauge_name": "SALT RIVER NEAR CHRYSOTILE, AZ",
    }
    for category in load.CATEGORIES:
        row[f"{category}_share"] = "0.1"
    return row | changes


def launch(name="Salt", odds="0.2"):
    return {
        "date": "2027-06-01",
        "weekday": "Tuesday",
        "river": name,
        "ridb_id": "249275",
        "applications": "50.0",
        "permits": "10.0",
        "odds": odds,
        "odds_low": "0.1" if odds else "",
        "odds_high": "0.3" if odds else "",
        "scale_2025": "0.05" if odds else "",
    }


def condition(date, flow="3", high="70.0", low="40.0", name="Salt"):
    return {
        "date": date,
        "river": name,
        "station_id": "USC00000001",
        "flow_step": flow,
        "high_f": high,
        "low_f": low,
    }


def test_past_trips_use_the_launch_day_flow_and_the_whole_trips_temperature():
    days = {
        datetime.date(2015, 6, 1): condition("2015-06-01", flow="3", high="70.0"),
        datetime.date(2015, 6, 2): condition("2015-06-02", flow="5", high="90.0"),
    }
    found = load.past_trips(D, days, 2)
    assert found["flow_years"][0] == 3
    assert found["temperature_years"][0] == 3


def test_past_trips_mark_a_year_with_no_reading():
    found = load.past_trips(D, {}, 2)
    years = len(config.FLOW_YEARS)
    assert found["flow_years"] == [load.NO_READING] * years
    assert found["temperature_years"] == [load.NO_READING] * years
    assert found["freezing_years"] == [False] * years


def test_past_trips_mark_a_freezing_night_on_any_day_of_the_trip():
    days = {
        datetime.date(2016, 6, 1): condition("2016-06-01", low="40.0"),
        datetime.date(2016, 6, 2): condition("2016-06-02", low="31.0"),
    }
    assert load.past_trips(D, days, 2)["freezing_years"][1] is True
    assert load.past_trips(D, days, 1)["freezing_years"][1] is False


def test_a_river_without_odds_is_left_out():
    rows = load.tables(
        [river(), river(name="Rogue", ridb_id="251982")],
        [launch(), launch(name="Rogue", odds="")],
        [condition("2015-06-01"), condition("2015-06-01", name="Rogue")],
    )
    assert [row["name"] for row in rows["River"]] == ["Salt"]
    assert {row["river"] for row in rows["Launch"]} == {"Salt"}


def test_rivers_in_one_lottery_make_one_lottery_with_a_relationship_each():
    rows = load.tables(
        [river(), river(name="Yampa")],
        [launch(), launch(name="Yampa")],
        [condition("2015-06-01"), condition("2015-06-01", name="Yampa")],
    )
    assert len(rows["Lottery"]) == 1
    assert len(rows["Agency"]) == 1
    assert len(rows["Day"]) == 1
    assert [row["river"] for row in rows["IN"]] == ["Salt", "Yampa"]


def test_tables_convert_cells_to_types_and_blanks_to_none():
    rows = load.tables([river()], [launch()], [condition("2015-06-01")])
    lottery = rows["Lottery"][0]
    assert lottery["ridb_id"] == 249275
    assert lottery["applications_open"] == datetime.date(2026, 12, 1)
    assert lottery["permits_per_person"] is None
    salt = rows["River"][0]
    assert salt["flow_starts"] == list(config.FLOWS["Salt"])
    assert (salt["overall_odds"], salt["overall_odds_season"]) == (0.05, 2025)
    assert rows["Launch"][0]["odds"] == 0.2


def test_every_statement_only_reads_fields_its_rows_have():
    rows = load.tables([river()], [launch()], [condition("2015-06-01")])
    assert set(rows) == set(load.STATEMENTS)
    for name, statement in load.STATEMENTS.items():
        assert set(re.findall(r"row\.(\w+)", statement)) <= set(rows[name][0]), name


def test_every_list_fits_neo4j_with_no_nulls():
    rows = load.tables([river()], [launch()], [condition("2015-06-01")])
    for row in rows["Launch"]:
        for value in row.values():
            if isinstance(value, list):
                assert None not in value


class Result:
    def consume(self):
        return self

    def __iter__(self):
        return iter([{"name": "Launch", "n": 1}])


class Session:
    def __init__(self):
        self.statements = []
        self.written = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, statement, **params):
        self.statements.append(statement)
        return Result()

    def execute_write(self, work, rows):
        self.written = rows
        work(self, rows)


class Driver:
    def __init__(self, session):
        self.opened = session

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def session(self):
        return self.opened


def test_load_makes_constraints_then_runs_every_statement(monkeypatch):
    session = Session()
    files = {
        config.RIVERS_CSV: [river()],
        config.ODDS_CSV: [launch()],
        config.CONDITIONS_CSV: [condition("2015-06-01")],
    }
    monkeypatch.setattr(load, "read", files.__getitem__)
    monkeypatch.setattr(load, "driver", lambda: Driver(session))
    assert load.load() == {"Launch": 1}
    first = len(load.CONSTRAINTS)
    assert session.statements[:first] == load.CONSTRAINTS
    written = first + len(load.STATEMENTS)
    assert session.statements[first:written] == list(load.STATEMENTS.values())
