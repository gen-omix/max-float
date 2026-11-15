"""Daily readings from NOAA GHCN-Daily: highs and lows, precipitation and snowfall
at the station that stands in for a point on a river, and wind at the closest
station that measures it."""

import datetime
import json
import time
import urllib.request
from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from math import asin, cos, radians, sin, sqrt
from typing import NamedTuple

from max_float import config
from max_float.ingest import seasons

Weather = dict[datetime.date, tuple[float | None, float | None]]

# Each day's readings by element, such as {"PRCP": 0.12, "SNOW": None}, for the
# days with any.
Readings = dict[datetime.date, dict[str, float | None]]


class Station(NamedTuple):
    """A GHCN-Daily station. Elevation is in meters."""

    id: str
    latitude: float
    longitude: float
    elevation: float


def recording(
    inventory: Iterable[str],
    years: range,
    elements: Sequence[str] = config.TEMPERATURE_ELEMENTS,
) -> set[str]:
    """IDs of the stations an inventory lists with every one of `elements` across
    `years`, by default highs and lows."""
    spans: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    for line in inventory:
        if line[31:35] in elements:
            spans[line[:11]][line[31:35]] = int(line[36:40]), int(line[41:45])
    return {
        station
        for station, span in spans.items()
        if len(span) == len(elements)
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


def stations(years: range, *element_sets: Sequence[str]) -> list[list[Station]]:
    """For each set of elements, every station with all of them across `years`.
    The inventory and station list are read once for them all."""
    inventory, listing = text(config.NOAA_INVENTORY), text(config.NOAA_STATIONS)
    return [
        parse_stations(listing, recording(inventory, years, elements))
        for elements in element_sets
    ]


def elevation(latitude: float, longitude: float) -> float:
    """A point's elevation in meters, from USGS. The service often fails for a
    while, so failures are retried for about a minute."""
    url = config.USGS_ELEVATION.format(latitude=latitude, longitude=longitude)

    def fetch() -> float:
        with urllib.request.urlopen(url, timeout=30) as response:
            return float(json.load(response)["value"])

    for wait in (2, 4, 8, 16, 32):
        try:
            return fetch()
        except (OSError, KeyError, ValueError):
            time.sleep(wait)
    return fetch()


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


def fetch(station: str, elements: Sequence[str], years: range) -> list[dict]:
    """A station's daily-summary rows for `elements` over `years`, in standard
    units, with NOAA's quality flags."""
    url = config.NOAA_DAILY.format(
        station=station,
        start=f"{years[0]}-01-01",
        end=f"{years[-1]}-12-31",
        elements=",".join(elements),
    )
    with urllib.request.urlopen(url, timeout=180) as response:
        return json.load(response)


def daily(station: str, years: range) -> Weather:
    """A station's high and low in degrees F on each day of `years` it has them."""
    return parse_daily(fetch(station, config.TEMPERATURE_ELEMENTS, years))


def parse_readings(rows: Iterable[dict[str, str]], elements: Sequence[str]) -> Readings:
    """Each day's reading of each element, None where it is missing or failed
    NOAA's quality checks, leaving out days with none."""
    found: Readings = {}
    for row in rows:
        day = {element: reading(row, element) for element in elements}
        if any(value is not None for value in day.values()):
            found[datetime.date.fromisoformat(row["DATE"])] = day
    return found


def readings(station: str, elements: Sequence[str], years: range) -> Readings:
    """A station's readings of `elements` on each day of `years` it has any, such
    as `config.PRECIPITATION_ELEMENTS` or `config.WIND_ELEMENTS`."""
    return parse_readings(fetch(station, elements, years), elements)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (latitude, longitude) points."""
    lat_a, lon_a, lat_b, lon_b = map(radians, (*a, *b))
    half = (
        sin((lat_b - lat_a) / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin((lon_b - lon_a) / 2) ** 2
    )
    return 2 * 6371 * asin(sqrt(half))


def share(river: str, dates: Collection[datetime.date], year: int) -> float:
    """The share of the river's lottery-season days in `year` that are in
    `dates`."""
    start, end = seasons.season(river, year)
    days = (end - start).days + 1
    return (
        sum(start + datetime.timedelta(offset) in dates for offset in range(days))
        / days
    )


def coverage(river: str, weather: Weather, year: int) -> float:
    """The share of the river's lottery-season days in `year` with a high and a
    low."""
    both = {
        day
        for day, (high, low) in weather.items()
        if high is not None and low is not None
    }
    return share(river, both, year)


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


class Wind(NamedTuple):
    """A river's wind station, how far it is from the river's point in km, and its
    wind readings."""

    station: Station
    distance: float
    readings: Readings


def nearest_wind(
    river: str, point: tuple[float, float], candidates: list[Station], years: range
) -> Wind | None:
    """The closest station to `point` within `config.WIND_DISTANCE` km with an
    average wind speed on `config.STATION_COVERAGE` of the river's lottery-season
    days in every year, or None if none has. Its readings have
    `config.WIND_ELEMENTS`."""
    close = [
        (distance(point, station[1:3]), station)
        for station in candidates
        if distance(point, station[1:3]) <= config.WIND_DISTANCE
    ]
    close.sort(key=lambda pair: pair[0])
    average = config.WIND_ELEMENTS[0]
    for km, station in close:
        found = readings(station.id, config.WIND_ELEMENTS, years)
        windy = {
            day for day, values in found.items() if values.get(average) is not None
        }
        if min(share(river, windy, year) for year in years) >= config.STATION_COVERAGE:
            return Wind(station, round(km, 1), found)
    return None
