"""Daily highs and lows from NOAA GHCN-Daily, at the station that stands in for a
point on a river."""

import datetime
import json
import time
import urllib.request
from collections import defaultdict
from collections.abc import Iterable
from math import asin, cos, radians, sin, sqrt
from typing import NamedTuple

from max_float import config
from max_float.ingest import seasons

Weather = dict[datetime.date, tuple[float | None, float | None]]


class Station(NamedTuple):
    """A GHCN-Daily station. Elevation is in meters."""

    id: str
    latitude: float
    longitude: float
    elevation: float


def recording(inventory: Iterable[str], years: range) -> set[str]:
    """IDs of the stations an inventory lists with highs and lows across `years`."""
    spans: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    for line in inventory:
        if line[31:35] in ("TMAX", "TMIN"):
            spans[line[:11]][line[31:35]] = int(line[36:40]), int(line[41:45])
    return {
        station
        for station, span in spans.items()
        if len(span) == 2
        and all(
            first <= years[0] and last >= years[-1] for first, last in span.values()
        )
    }


def parse_stations(lines: Iterable[str], ids: set[str]) -> list[Station]:
    """The stations in `ids` from the fixed-width station list."""
    return [
        Station(line[:11], float(line[12:20]), float(line[21:30]), float(line[31:37]))
        for line in lines
        if line[:11] in ids
    ]


def text(url: str) -> list[str]:
    """The lines of a text file at `url`."""
    with urllib.request.urlopen(url, timeout=300) as response:
        return response.read().decode("utf-8", "replace").splitlines()


def stations(years: range) -> list[Station]:
    """Every station with highs and lows across `years`."""
    ids = recording(text(config.NOAA_INVENTORY), years)
    return parse_stations(text(config.NOAA_STATIONS), ids)


def elevation(latitude: float, longitude: float, attempts: int = 5) -> float:
    """A point's elevation in meters, from USGS. The service often fails once, so
    it is tried `attempts` times."""
    url = config.USGS_ELEVATION.format(latitude=latitude, longitude=longitude)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return float(json.load(response)["value"])
        except (OSError, KeyError, ValueError):
            if attempt == attempts - 1:
                raise
            time.sleep(3)
    raise ValueError("attempts must be at least 1")


def reading(row: dict[str, str], name: str) -> float | None:
    """A row's TMAX or TMIN, or None if it is missing or failed NOAA's quality
    checks. Attributes are `measurement,quality,source,time`."""
    value = row.get(name, "").strip()
    _, quality, *_ = row.get(f"{name}_ATTRIBUTES", ",").split(",")
    return float(value) if value and not quality.strip() else None


def parse_daily(rows: Iterable[dict[str, str]]) -> Weather:
    """Each day's high and low in degrees F, leaving out days with neither."""
    weather: Weather = {}
    for row in rows:
        high, low = reading(row, "TMAX"), reading(row, "TMIN")
        if high is not None or low is not None:
            weather[datetime.date.fromisoformat(row["DATE"])] = high, low
    return weather


def daily(station: str, years: range) -> Weather:
    """A station's high and low in degrees F on each day of `years` it has them."""
    url = config.NOAA_DAILY.format(
        station=station, start=f"{years[0]}-01-01", end=f"{years[-1]}-12-31"
    )
    with urllib.request.urlopen(url, timeout=180) as response:
        return parse_daily(json.load(response))


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (latitude, longitude) points."""
    lat_a, lon_a, lat_b, lon_b = map(radians, (*a, *b))
    half = (
        sin((lat_b - lat_a) / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin((lon_b - lon_a) / 2) ** 2
    )
    return 2 * 6371 * asin(sqrt(half))


def coverage(river: str, weather: Weather, year: int) -> float:
    """The share of the river's lottery-season days in `year` with a high and a
    low."""
    start, end = seasons.season(river, year)
    days = (end - start).days + 1
    found = 0
    for offset in range(days):
        high, low = weather.get(start + datetime.timedelta(offset), (None, None))
        found += high is not None and low is not None
    return found / days


def nearest(
    river: str, point: tuple[float, float], candidates: list[Station], years: range
) -> tuple[Station, Weather]:
    """The closest station to `point` within `config.STATION_ELEVATION` meters of
    its elevation and with readings on `config.STATION_COVERAGE` of the river's
    lottery-season days in every year, and that station's weather."""
    height = elevation(*point)
    close = [
        station
        for station in candidates
        if abs(station.elevation - height) <= config.STATION_ELEVATION
    ]
    close.sort(key=lambda station: distance(point, station[1:3]))
    for station in close:
        weather = daily(station.id, years)
        worst = min(coverage(river, weather, year) for year in years)
        if worst >= config.STATION_COVERAGE:
            return station, weather
    raise LookupError(f"No station qualifies for {river}.")
