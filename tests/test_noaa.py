import io
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


def test_elevation_retries_until_the_service_answers(monkeypatch):
    answers = [OSError(), io.BytesIO(b"not json"), io.BytesIO(b'{"value": "934.5"}')]

    def urlopen(*_, **__):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(noaa.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(noaa.time, "sleep", lambda _: None)
    assert noaa.elevation(45.0, -115.0) == 934.5


def test_elevation_gives_up_with_the_error(monkeypatch):
    def urlopen(*_, **__):
        raise OSError("down")

    monkeypatch.setattr(noaa.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(noaa.time, "sleep", lambda _: None)
    with pytest.raises(OSError):
        noaa.elevation(45.0, -115.0)


def test_recording_can_ask_for_any_elements():
    lines = [
        inventory_line("USW00000001", "AWND"),
        inventory_line("USW00000002", "AWND", first=2025),
        inventory_line("USC00000003", "TMAX"),
    ]
    assert noaa.recording(lines, YEARS, ("AWND",)) == {"USW00000001"}
    assert noaa.recording(lines, YEARS) == set()


def test_parse_readings_keeps_days_with_any_reading_and_drops_failed_ones():
    rows = [
        {
            "DATE": "2025-06-01",
            "PRCP": "0.25",
            "PRCP_ATTRIBUTES": ",,7,0700",
            "SNOW": "0",
            "SNOW_ATTRIBUTES": ",,7,",
        },
        {"DATE": "2025-06-02", "PRCP": "1.10", "PRCP_ATTRIBUTES": ",X,7,0700"},
        {"DATE": "2025-06-03", "SNOW": "2.0", "SNOW_ATTRIBUTES": ",,7,"},
    ]
    assert noaa.parse_readings(rows, ("PRCP", "SNOW")) == {
        date(2025, 6, 1): {"PRCP": 0.25, "SNOW": 0.0},
        date(2025, 6, 3): {"PRCP": None, "SNOW": 2.0},
    }


def test_fetch_asks_for_the_elements_in_standard_units(monkeypatch):
    asked = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(url, timeout):
        asked.append(url)
        return Response(b"[]")

    monkeypatch.setattr(noaa.urllib.request, "urlopen", urlopen)
    noaa.readings("USW00000001", config.WIND_ELEMENTS, YEARS)
    noaa.daily("USC00000001", YEARS)
    assert "dataTypes=AWND,WSF5" in asked[0] and "units=standard" in asked[0]
    assert "startDate=2024-01-01" in asked[0] and "endDate=2025-12-31" in asked[0]
    assert "dataTypes=TMAX,TMIN" in asked[1]


def windy_season(skip=0, years=YEARS):
    return {
        day: {"AWND": 7.0, "WSF5": 20.0} for day in full_season(years=years, skip=skip)
    }


def test_nearest_wind_takes_the_closest_station_that_measures_it(monkeypatch):
    point = 34.0, -110.0
    found = {
        "GAPS": windy_season(years=range(2024, 2025)),
        "GOOD": windy_season(),
        "BEYOND": windy_season(),
    }
    monkeypatch.setattr(noaa, "readings", lambda station, *_: found[station])
    candidates = [
        Station("BEYOND", 36.0, -110.0, 3000.0),
        Station("GOOD", 34.5, -110.0, 2500.0),
        Station("GAPS", 34.2, -110.0, 1000.0),
    ]
    wind = noaa.nearest_wind("Salt", point, candidates, YEARS)
    assert wind.station.id == "GOOD"
    assert wind.distance == pytest.approx(noaa.distance(point, (34.5, -110.0)), abs=0.1)
    assert wind.readings == found["GOOD"]


def test_nearest_wind_is_none_beyond_its_distance(monkeypatch):
    monkeypatch.setattr(noaa, "readings", lambda *_: windy_season())
    far = Station("FAR", 34.0 + (config.WIND_DISTANCE + 20) / 111, -110.0, 1000.0)
    assert noaa.nearest_wind("Salt", (34.0, -110.0), [far], YEARS) is None
    assert noaa.nearest_wind("Salt", (34.0, -110.0), [], YEARS) is None
