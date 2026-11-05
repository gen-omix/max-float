"""One row per river and day: its flow at its USGS gauge and the flow's category.

`date` and `river` match applications_cleaned.csv and `river` matches rivers.csv.
`date` and `ridb_id` match applications.csv, which has one row a day for the
lottery Gates of Lodore and the Yampa share, so that lottery's days join to two.
"""

import datetime

from max_float import config
from max_float.ingest import reservations, rivers, usgs

COLUMNS = [
    "date",
    "river",
    "ridb_id",
    "gauge_id",
    "flow_cfs",
    "flow_step",
    "flow_category",
]


def days(
    river: str, flows: dict[datetime.date, float], years: range
) -> list[dict[str, object]]:
    """A row for each day of `years`. The flow and its category are None on days
    `flows` has no reading for."""
    first = datetime.date(years[0], 1, 1)
    count = (datetime.date(years[-1], 12, 31) - first).days + 1
    out = []
    for offset in range(count):
        date = first + datetime.timedelta(offset)
        cfs = flows.get(date)
        step = None if cfs is None else rivers.category(river, cfs)
        out.append(
            {
                "date": date,
                "river": river,
                "ridb_id": config.RIVERS[river],
                "gauge_id": config.GAUGES[river],
                "flow_cfs": cfs,
                "flow_step": step,
                "flow_category": None if step is None else config.FLOW_CATEGORIES[step],
            }
        )
    return out


def main() -> None:
    """Write conditions.csv for `config.FLOW_YEARS`, sorted like the application
    files."""
    rows = [
        row
        for river, site in sorted(config.GAUGES.items())
        for row in days(
            river, usgs.daily(site, config.FLOW_YEARS)[1], config.FLOW_YEARS
        )
    ]
    reservations.write(rows, config.CONDITIONS_CSV, COLUMNS)


if __name__ == "__main__":
    main()
