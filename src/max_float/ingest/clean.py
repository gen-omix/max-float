"""Build data/applications_cleaned.csv from data/applications.csv.

Dinosaur's lottery is split into Gates of Lodore and the Yampa, and permits are
halved in fiscal years where RIDB recorded every permit twice.
"""

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from max_float.ingest import dinosaur, reservations

MIN_DATES = 20
COLUMNS = [column for column in reservations.COLUMNS if column != "source_url"]


def fiscal_year(row: dict[str, object]) -> int:
    """The fiscal year of the RIDB file a row came from."""
    return int(re.search(r"reservations(\d+)", str(row["source_url"])).group(1))


def doubled(rows: list[dict[str, str]]) -> set[tuple[str, int]]:
    """(ridb_id, fiscal year) pairs whose permits were all recorded twice.

    A permit's year counts as doubled when every launch date with permits has an
    even count, over at least MIN_DATES dates. In a normal year about half are odd.
    """
    counts: dict[tuple[str, int], list[int]] = defaultdict(list)
    for row in rows:
        if int(row["permits"]):
            counts[row["ridb_id"], fiscal_year(row)].append(int(row["permits"]))
    return {
        key
        for key, values in counts.items()
        if len(values) >= MIN_DATES and all(value % 2 == 0 for value in values)
    }


def launches(
    rows: list[dict[str, str]], permits: Counter[tuple[str, str]]
) -> list[dict[str, object]]:
    """Launch rows with Dinosaur split and doubled permits halved."""
    twice = doubled(rows)
    return [
        row | {"permits": int(row["permits"]) // 2}
        if (row["ridb_id"], fiscal_year(row)) in twice
        else row
        for row in dinosaur.launches(rows, permits)
    ]


def main(
    source: Path = Path("data/applications.csv"),
    path: Path = Path("data/applications_cleaned.csv"),
) -> None:
    """Write data/applications_cleaned.csv from data/applications.csv."""
    with source.open() as file:
        rows = list(csv.DictReader(file))
    permits: Counter[tuple[str, str]] = Counter()
    for year in sorted({fiscal_year(row) for row in rows}):
        with reservations.lines(year) as lines:
            permits += dinosaur.permits(lines)
    reservations.write(launches(rows, permits), path, COLUMNS)


if __name__ == "__main__":
    main()
