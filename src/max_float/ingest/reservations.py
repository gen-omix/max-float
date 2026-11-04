"""Count lottery applications and permits for each launch from RIDB reservations."""

import csv
import datetime
import io
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from max_float.ingest.ridb import RIVERS

URL = "https://ridb.recreation.gov/downloads/reservations{year}.zip"
FIRST_YEAR = 2019
KINDS = {"LOTTERY_PERMIT": "applications", "PERMIT": "permits"}
COLUMNS = ["date", "river", "ridb_id", "applications", "permits", "source_url"]


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


def count(lines: Iterable[str], ids: set[str]) -> Counter[tuple[str, str, str]]:
    """Rows per (date, ridb_id, kind) in a reservations CSV, for these permits."""
    reader = csv.reader(lines)
    header = [name.lower() for name in next(reader)]
    kind, facility, start = (
        header.index(name) for name in ("inventorytype", "facilityid", "startdate")
    )
    counts: Counter[tuple[str, str, str]] = Counter()
    for row in reader:
        if len(row) > start and row[facility] in ids and row[kind] in KINDS:
            counts[row[start][:10], row[facility], KINDS[row[kind]]] += 1
    return counts


def launches(year: int, rivers: dict[str, int] = RIVERS) -> list[dict[str, object]]:
    """Applications and permits per launch for one fiscal year of reservations."""
    if year < FIRST_YEAR:
        raise ValueError(f"Reservation files before FY{FIRST_YEAR} have no types.")
    names: dict[str, list[str]] = {}
    for river, ridb_id in rivers.items():
        names.setdefault(str(ridb_id), []).append(river)
    url = URL.format(year=year)
    with tempfile.TemporaryFile() as archive:
        with urllib.request.urlopen(url, timeout=60) as response:
            while chunk := response.read(1 << 20):
                archive.write(chunk)
        with (
            zipfile.ZipFile(archive) as files,
            files.open(files.namelist()[0]) as raw,
        ):
            lines = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            counts = count(lines, set(names))
    keys = sorted({(date, ridb_id) for date, ridb_id, _ in counts})
    return [
        {
            "date": date,
            "river": " / ".join(names[ridb_id]),
            "ridb_id": ridb_id,
            "applications": counts[date, ridb_id, "applications"],
            "permits": counts[date, ridb_id, "permits"],
            "source_url": url,
        }
        for date, ridb_id in keys
    ]


def write(rows: list[dict[str, object]], path: Path) -> None:
    """Write launch rows as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, COLUMNS)
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
    main()
