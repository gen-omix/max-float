"""One row per river and day: its flow at its USGS gauge and its high and low at
its NOAA station, each with its category.

`date` and `river` match applications_cleaned.csv and `river` matches rivers.csv.
`date` and `ridb_id` match applications.csv, which has one row a day for the
lottery Gates of Lodore and the Yampa share, so that lottery's days join to two.
The river's point comes from rivers.csv, so build that first.
"""

import csv
import datetime
from bisect import bisect_right

from max_float import config
from max_float.ingest import noaa, reservations, rivers, usgs

COLUMNS = [
    "date",
    "river",
    "ridb_id",
    "gauge_id",
    "flow_cfs",
    "flow_step",
    "flow_category",
    "station_id",
    "high_f",
    "low_f",
    "temperature_step",
    "temperature_category",
]


def temperature_step(high: float) -> int:
    """The index in `config.TEMPERATURE_CATEGORIES` of a daily high."""
    return bisect_right(config.TEMPERATURE_STARTS, high)


def days(
    river: str,
    flows: dict[datetime.date, float],
    station: str,
    weather: noaa.Weather,
    years: range,
) -> list[dict[str, object]]:
    """A row for each day of `years`. A flow or temperature and its category are
    None on days with no reading."""
    first = datetime.date(years[0], 1, 1)
    count = (datetime.date(years[-1], 12, 31) - first).days + 1
    out = []
    for offset in range(count):
        date = first + datetime.timedelta(offset)
        cfs = flows.get(date)
        high, low = weather.get(date, (None, None))
        flow = None if cfs is None else rivers.category(river, cfs)
        heat = None if high is None else temperature_step(high)
        out.append(
            {
                "date": date,
                "river": river,
                "ridb_id": config.RIVERS[river],
                "gauge_id": config.GAUGES[river],
                "flow_cfs": cfs,
                "flow_step": flow,
                "flow_category": None if flow is None else config.FLOW_CATEGORIES[flow],
                "station_id": station,
                "high_f": high,
                "low_f": low,
                "temperature_step": heat,
                "temperature_category": None
                if heat is None
                else config.TEMPERATURE_CATEGORIES[heat],
            }
        )
    return out


def main() -> None:
    """Write conditions.csv for `config.FLOW_YEARS`, sorted like the application
    files."""
    years = config.FLOW_YEARS
    with config.RIVERS_CSV.open(newline="") as file:
        points = {
            row["river"]: (float(row["latitude"]), float(row["longitude"]))
            for row in csv.DictReader(file)
        }
    candidates = noaa.stations(years)
    rows = []
    for river, site in sorted(config.GAUGES.items()):
        _, flows = usgs.daily(site, years)
        station, weather = noaa.nearest(river, points[river], candidates, years)
        rows += days(river, flows, station.id, weather, years)
    reservations.write(rows, config.CONDITIONS_CSV, COLUMNS)


if __name__ == "__main__":
    main()
