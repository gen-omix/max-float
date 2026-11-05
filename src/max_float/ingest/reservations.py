"""Count lottery applications and permits for each launch from RIDB reservations."""

import csv
import datetime
import io
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from max_float.ingest.ridb import RIVERS

URL = "https://ridb.recreation.gov/downloads/reservations{year}.zip"
FIRST_YEAR = 2019
KINDS = {"LOTTERY_PERMIT": "applications", "PERMIT": "permits"}
COLUMNS = [
    "date",
    "weekday",
    "river",
    "ridb_id",
    "applications",
    "permits",
    "source_url",
]


def published(year: int) -> bool:
    """Whether RIDB has published reservations for this fiscal year."""
    request = urllib.request.Request(URL.format(year=year), method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=30):
            return True
    except urllib.error.HTTPError:
        return False


def latest_year(today: datetime.date | None = None) -> int:
    """The most recent fiscal year RIDB has published."""
    year = (today or datetime.date.today()).year + 1
    while not published(year):
        year -= 1
        if year < FIRST_YEAR:
            raise RuntimeError("RIDB has no reservation files from FY2019 on.")
    return year


@contextmanager
def lines(year: int) -> Iterator[Iterable[str]]:
    """The lines of one fiscal year's reservations CSV, downloaded to a temp file."""
    if year < FIRST_YEAR:
        raise ValueError(f"Reservation files before FY{FIRST_YEAR} have no types.")
    with tempfile.TemporaryFile() as archive:
        with urllib.request.urlopen(URL.format(year=year), timeout=60) as response:
            while chunk := response.read(1 << 20):
                archive.write(chunk)
        with (
            zipfile.ZipFile(archive) as files,
            files.open(files.namelist()[0]) as raw,
        ):
            yield io.TextIOWrapper(raw, encoding="utf-8", errors="replace")


def records(rows: Iterable[str], ids: set[str]) -> Iterator[dict[str, str]]:
    """Reservations for these permits, keyed by lowercase column name."""
    reader = csv.reader(rows)
    header = [name.lower() for name in next(reader)]
    facility = header.index("facilityid")
    for row in reader:
        if len(row) > facility and row[facility] in ids:
            yield dict(zip(header, row, strict=False))


def count(rows: Iterable[str], ids: set[str]) -> Counter[tuple[str, str, str]]:
    """Reservations per (date, ridb_id, kind) for these permits."""
    return Counter(
        (record["startdate"][:10], record["facilityid"], KINDS[record["inventorytype"]])
        for record in records(rows, ids)
        if record.get("inventorytype") in KINDS
    )


def launches(year: int, rivers: dict[str, int] = RIVERS) -> list[dict[str, object]]:
    """Applications and permits per launch for one fiscal year of reservations."""
    names: dict[str, list[str]] = {}
    for river, ridb_id in rivers.items():
        names.setdefault(str(ridb_id), []).append(river)
    url = URL.format(year=year)
    with lines(year) as rows:
        counts = count(rows, set(names))
    keys = sorted({(date, ridb_id) for date, ridb_id, _ in counts})
    return [
        {
            "date": date,
            "weekday": datetime.date.fromisoformat(date).strftime("%A"),
            "river": " / ".join(names[ridb_id]),
            "ridb_id": ridb_id,
            "applications": counts[date, ridb_id, "applications"],
            "permits": counts[date, ridb_id, "permits"],
            "source_url": url,
        }
        for date, ridb_id in keys
    ]


def write(
    rows: list[dict[str, object]], path: Path, columns: list[str] = COLUMNS
) -> None:
    """Write launch rows as ASCII CSV, keeping only `columns`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="ascii") as file:
        writer = csv.DictWriter(file, columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(years: int = 5, path: Path = Path("data/applications.csv")) -> None:
    """Write applications and permits per launch for the last `years` fiscal years."""
    last = latest_year()
    rows = []
    for year in range(last - years + 1, last + 1):
        rows += launches(year)
    write(sorted(rows, key=lambda row: (row["river"], row["date"])), path)


if __name__ == "__main__":
    main(*(int(arg) for arg in sys.argv[1:]))
