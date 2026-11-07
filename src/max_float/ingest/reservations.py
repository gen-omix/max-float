"""Count lottery applications and lottery permits for each launch from RIDB
reservations."""

import csv
import datetime
import io
import tempfile
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from max_float import config
from max_float.ingest import seasons

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


@contextmanager
def lines(year: int) -> Iterator[Iterable[str]]:
    """The lines of one fiscal year's reservations CSV, downloaded to a temp file."""
    if year < 2019:
        raise ValueError("Reservation files before FY2019 have no types.")
    url = config.RESERVATIONS.format(year=year)
    with tempfile.TemporaryFile() as archive:
        with urllib.request.urlopen(url, timeout=60) as response:
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


def lottery(record: dict[str, str], river: str) -> bool:
    """Whether a reservation counts: every application, and the permits the
    river's lottery awarded."""
    launch = datetime.date.fromisoformat(record["startdate"][:10])
    return record["inventorytype"] == "LOTTERY_PERMIT" or seasons.lottery_permit(
        river, launch, record.get("orderdate", "")
    )


def count(rows: Iterable[str], rivers: dict[str, str]) -> Counter[tuple[str, str, str]]:
    """Applications and lottery permits per (date, ridb_id, kind), for permits
    keyed by RIDB ID with a river whose lottery they're for."""
    return Counter(
        (record["startdate"][:10], record["facilityid"], KINDS[record["inventorytype"]])
        for record in records(rows, set(rivers))
        if record.get("inventorytype") in KINDS
        and lottery(record, rivers[record["facilityid"]])
    )


def launches(
    year: int, rivers: dict[str, int] = config.RIVERS
) -> list[dict[str, object]]:
    """Applications and lottery permits per launch for one fiscal year of
    reservations."""
    names: dict[str, list[str]] = {}
    for river, ridb_id in rivers.items():
        names.setdefault(str(ridb_id), []).append(river)
    url = config.RESERVATIONS.format(year=year)
    with lines(year) as rows:
        counts = count(rows, {ridb_id: rivers[0] for ridb_id, rivers in names.items()})
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


def main() -> None:
    """Write applications and lottery permits per launch for `config.FISCAL_YEARS`."""
    rows = [row for year in config.FISCAL_YEARS for row in launches(year)]
    rows.sort(key=lambda row: (row["river"], row["date"]))
    write(rows, config.APPLICATIONS_CSV)


if __name__ == "__main__":
    main()
