"""Build applications_cleaned.csv from applications.csv.

Dinosaur's lottery is split into Gates of Lodore and the Yampa, permits are
halved in fiscal years where RIDB recorded every permit twice, and, with
`config.SEASON_ONLY`, launches outside their river's lottery season are dropped.
"""

import csv
import datetime
import re
from collections import Counter, defaultdict

from max_float import config
from max_float.ingest import dinosaur, reservations, seasons

COLUMNS = [column for column in reservations.COLUMNS if column != "source_url"]


def fiscal_year(row: dict[str, object]) -> int:
    """The fiscal year of the RIDB file a row came from."""
    return int(re.search(r"reservations(\d+)", str(row["source_url"])).group(1))


def doubled(rows: list[dict[str, str]]) -> set[tuple[str, int]]:
    """(ridb_id, fiscal year) pairs whose permits were all recorded twice.

    A permit's year counts as doubled when every launch date with permits has an
    even count, over at least `config.DOUBLED_LAUNCHES` dates. In a normal year
    about half are odd.
    """
    counts: dict[tuple[str, int], list[int]] = defaultdict(list)
    for row in rows:
        if int(row["permits"]):
            counts[row["ridb_id"], fiscal_year(row)].append(int(row["permits"]))
    return {
        key
        for key, values in counts.items()
        if len(values) >= config.DOUBLED_LAUNCHES
        and all(value % 2 == 0 for value in values)
    }


def launches(
    rows: list[dict[str, str]], permits: Counter[tuple[str, str]]
) -> list[dict[str, object]]:
    """Launch rows with Dinosaur split, doubled permits halved and, with
    `config.SEASON_ONLY`, only launches in their river's lottery season."""
    twice = doubled(rows)
    return [
        row | {"permits": int(row["permits"]) // 2}
        if (row["ridb_id"], fiscal_year(row)) in twice
        else row
        for row in dinosaur.launches(rows, permits)
        if not config.SEASON_ONLY
        or seasons.in_season(row["river"], datetime.date.fromisoformat(row["date"]))
    ]


def main() -> None:
    """Write applications_cleaned.csv from applications.csv."""
    with config.APPLICATIONS_CSV.open(newline="") as file:
        rows = list(csv.DictReader(file))
    permits: Counter[tuple[str, str]] = Counter()
    for year in sorted({fiscal_year(row) for row in rows}):
        with reservations.lines(year) as lines:
            permits += dinosaur.permits(lines)
    reservations.write(launches(rows, permits), config.CLEANED_CSV, COLUMNS)


if __name__ == "__main__":
    main()
