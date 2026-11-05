"""One row per river: its RIDB permit, agency, point, application window and season.

The permit, agency and point come from the RIDB API; the window and season from
the rules in `seasons`.
"""

import sys

from max_float import config
from max_float.ingest import reservations, ridb, seasons

COLUMNS = [
    "river",
    "ridb_id",
    "ridb_name",
    "agency",
    "latitude",
    "longitude",
    "year",
    "applications_open",
    "application_deadline",
    "season_start",
    "season_end",
]


def point(river: str, facility: dict, entrances: list[dict]) -> tuple[float, float]:
    """The river's point: its own permit entrance's if RIDB locates one, else the
    permit's."""
    for entrance in entrances:
        located = entrance["Latitude"] or entrance["Longitude"]
        zones = [zone["Zone"].removesuffix(" River") for zone in entrance["ZONES"]]
        if located and any(zone in river for zone in zones):
            return entrance["Latitude"], entrance["Longitude"]
    return facility["FacilityLatitude"], facility["FacilityLongitude"]


def permit(river: str, facility: dict, entrances: list[dict]) -> dict[str, object]:
    """A river's RIDB permit name, agency and point."""
    latitude, longitude = point(river, facility, entrances)
    return {
        "river": river,
        "ridb_id": facility["FacilityID"],
        "ridb_name": facility["FacilityName"].strip(),
        "agency": ", ".join(org["OrgName"] for org in facility["ORGANIZATION"]),
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
    reservations.write(
        [
            permit(river, *records[ridb_id]) | lottery(river, year)
            for river, ridb_id in config.RIVERS.items()
        ],
        config.RIVERS_CSV,
        COLUMNS,
    )


if __name__ == "__main__":
    main(*(int(arg) for arg in sys.argv[1:]))
