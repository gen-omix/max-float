from datetime import date, timedelta

import pytest

from max_float import config
from max_float.ingest import noaa, seasons
from max_float.ingest.noaa import Station

YEARS = range(2024, 2026)


def inventory_line(station, element, first=2000, last=2025):
    return f"{station:<11} {44.0:8.4f} {-115.0:9.4f} {element} {first} {last}"


def station_line(station, latitude, longitude, elevation):
    name = "SOME PLACE"
    return (
        f"{station:<11} {latitude:8.4f} {longitude:9.4f} {elevation:6.1f} ID {name:<30}"
    )


def test_recording_needs_highs_and_lows_across_the_years():
    lines = [
        inventory_line("USC00000001", "TMAX"),
        inventory_line("USC00000001", "TMIN"),
        inventory_line("USC00000001", "PRCP"),
        inventory_line("USC00000002", "TMAX"),
        inventory_line("USC00000003", "TMAX"),
        inventory_line("USC00000003", "TMIN", last=2024),
        inventory_line("USC00000004", "TMAX", first=2025),
        inventory_line("USC00000004", "TMIN"),
    ]
    assert noaa.recording(lines, YEARS) == {"USC00000001"}


def test_parse_stations():
    lines = [
        station_line("USC00000001", 44.5, -115.25, 1640.0),
        station_line("USC00000002", 1, 2, 3),
    ]
    assert noaa.parse_stations(lines, {"USC00000001"}) == [
        Station("USC00000001", 44.5, -115.25, 1640.0)
    ]


def test_parse_daily_drops_readings_that_failed_quality_checks():
    rows = [
        {
            "DATE": "2024-10-14",
            "TMAX": "102",
            "TMAX_ATTRIBUTES": ",S,T,",
            "TMIN": "30",
            "TMIN_ATTRIBUTES": ",,T,",
        },
        {
            "DATE": "2024-10-15",
            "TMAX": "58",
            "TMAX_ATTRIBUTES": ",,T,",
            "TMIN": "28",
            "TMIN_ATTRIBUTES": ",,T,",
        },
        {"DATE": "2024-10-16"},
    ]
    assert noaa.parse_daily(rows) == {
        date(2024, 10, 14): (None, 30.0),
        date(2024, 10, 15): (58.0, 28.0),
    }


def test_distance():
    assert noaa.distance((45, -115), (46, -115)) == pytest.approx(111.2, abs=0.1)


def full_season(river="Salt", years=YEARS, skip=0):
    """A high and low on every day of the river's seasons but the first `skip`."""
    weather = {}
    for year in years:
        start, end = seasons.season(river, year)
        for offset in range(skip, (end - start).days + 1):
            weather[start + timedelta(offset)] = 80.0, 50.0
    return weather


def test_coverage_counts_days_with_both_readings():
    assert noaa.coverage("Salt", full_season(), 2025) == 1
    high_only = {day: (80.0, None) for day in full_season()}
    assert noaa.coverage("Salt", high_only, 2025) == 0
    assert noaa.coverage("Salt", {}, 2025) == 0


def test_nearest_skips_stations_too_high_or_with_gaps(monkeypatch):
    point = 34.0, -110.0
    weather = {
        "GAPS": full_season(years=range(2024, 2025)),
        "SOME": full_season(skip=20),
        "GOOD": full_season(),
    }
    monkeypatch.setattr(noaa, "elevation", lambda *_: 1000.0)
    monkeypatch.setattr(noaa, "daily", lambda station, _: weather[station])
    candidates = [
        Station("FAR", 36.0, -110.0, 1000.0),
        Station("GOOD", 34.5, -110.0, 1000.0 + config.STATION_ELEVATION),
        Station("GAPS", 34.2, -110.0, 1000.0),
        Station("SOME", 34.6, -110.0, 1000.0),
        Station("MOUNTAIN", 34.1, -110.0, 2000.0),
    ]
    station, found = noaa.nearest("Salt", point, candidates, YEARS)
    assert station.id == "GOOD"
    assert found == weather["GOOD"]


def test_nearest_says_when_no_station_qualifies(monkeypatch):
    monkeypatch.setattr(noaa, "elevation", lambda *_: 1000.0)
    with pytest.raises(LookupError):
        noaa.nearest("Salt", (34.0, -110.0), [], YEARS)


def test_nearest_accepts_a_close_station_with_some_gaps(monkeypatch):
    monkeypatch.setattr(noaa, "elevation", lambda *_: 1000.0)
    monkeypatch.setattr(noaa, "daily", lambda *_: full_season(skip=20))
    close = Station("CLOSE", 34.0, -110.0, 1000.0)
    station, _ = noaa.nearest("Salt", (34.0, -110.0), [close], YEARS)
    assert station == close
