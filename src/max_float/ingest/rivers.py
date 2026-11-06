"""One row per river: its RIDB permit, agency, section, point, application window,
season, lottery rules, gauge and flow categories.

The permit, agency and point come from the RIDB API, unless `config.POINTS` has
the river's point, the gauge's name and flows from USGS, and the section, window,
season, rules and flow categories from `config`.
"""

import datetime
import sys
from bisect import bisect_right
from collections import Counter

from max_float import config
from max_float.ingest import reservations, ridb, seasons, usgs

CATEGORIES = [category.replace(" ", "_") for category in config.FLOW_CATEGORIES]

COLUMNS = [
    "river",
    "code",
    "ridb_id",
    "ridb_name",
    "agency",
    "section",
    "latitude",
    "longitude",
    "year",
    "applications_open",
    "application_deadline",
    "season_start",
    "season_end",
    "choices_per_application",
    "applications_per_person",
    "on_trip",
    "permits_per_person",
    "launches_per_day",
    "max_group",
    "max_trip_days",
    "rules_source",
    "gauge_id",
    "gauge_name",
    *(f"{category}_cfs" for category in CATEGORIES),
    *(f"{category}_share" for category in CATEGORIES),
]


def point(river: str, facility: dict, entrances: list[dict]) -> tuple[float, float]:
    """The river's point: from `config.POINTS` if it's there, else its own permit
    entrance's if RIDB locates one, else the permit's."""
    if river in config.POINTS:
        return config.POINTS[river]
    for entrance in entrances:
        located = entrance["Latitude"] or entrance["Longitude"]
        zones = [zone["Zone"].removesuffix(" River") for zone in entrance["ZONES"]]
        if located and any(zone in river for zone in zones):
            return entrance["Latitude"], entrance["Longitude"]
    return facility["FacilityLatitude"], facility["FacilityLongitude"]


def permit(river: str, facility: dict, entrances: list[dict]) -> dict[str, object]:
    """A river's code, RIDB permit name, agency and point."""
    latitude, longitude = point(river, facility, entrances)
    return {
        "river": river,
        "code": config.RIVER_CODES[river],
        "ridb_id": facility["FacilityID"],
        "ridb_name": facility["FacilityName"].strip(),
        "agency": ", ".join(org["OrgName"] for org in facility["ORGANIZATION"]),
        "section": config.SECTIONS[river],
        "latitude": latitude,
        "longitude": longitude,
    }


def lottery(river: str, year: int) -> dict[str, object]:
    """A river's application window and season for the lottery in `year`."""
    opens, deadline = seasons.window(year)
    start, end = seasons.season(river, year)
    return {
        "year": year,
        "applications_open": opens,
        "application_deadline": deadline,
        "season_start": start,
        "season_end": end,
    }


def rules(river: str, ridb_id: int) -> dict[str, object]:
    """A river's lottery rules from `config.LOTTERY_RULES`, with the Recreation.gov
    permit page that has most of them."""
    source = config.RECREATION_GOV_PERMIT.format(ridb_id=ridb_id)
    return config.LOTTERY_RULES[river] | {"rules_source": source}


def category(river: str, cfs: float) -> int:
    """The index in `config.FLOW_CATEGORIES` of a flow at the river's gauge."""
    return bisect_right(config.FLOWS[river], cfs)


def flow(
    river: str, gauge_name: str, flows: dict[datetime.date, float]
) -> dict[str, object]:
    """A river's gauge, and each flow category's range in cfs and share of the
    lottery-season days in `flows`."""
    counts = Counter(
        category(river, cfs)
        for date, cfs in flows.items()
        if seasons.in_season(river, date)
    )
    days = sum(counts.values())
    starts = (0, *config.FLOWS[river])
    row: dict[str, object] = {
        "gauge_id": config.GAUGES[river],
        "gauge_name": gauge_name,
    }
    for index, name in enumerate(CATEGORIES):
        low, high = starts[index], starts[index + 1 : index + 2]
        row[f"{name}_cfs"] = f"{low}-{high[0]}" if high else f"{low}+"
        row[f"{name}_share"] = round(counts[index] / days, 3)
    return row


def main(year: int = config.YEAR) -> None:
    """Write one row per river for the lottery in `year`."""
    records = {
        ridb_id: (
            ridb.get(f"facilities/{ridb_id}", full="true"),
            ridb.get(f"facilities/{ridb_id}/permitentrances", full="true", limit=50)[
                "RECDATA"
            ],
        )
        for ridb_id in set(config.RIVERS.values())
    }
    gauges = {
        river: usgs.daily(site, config.FLOW_YEARS)
        for river, site in config.GAUGES.items()
    }
    reservations.write(
        [
            permit(river, *records[ridb_id])
            | lottery(river, year)
            | rules(river, ridb_id)
            | flow(river, *gauges[river])
            for river, ridb_id in config.RIVERS.items()
        ],
        config.RIVERS_CSV,
        COLUMNS,
    )


if __name__ == "__main__":
    main(*(int(arg) for arg in sys.argv[1:]))
