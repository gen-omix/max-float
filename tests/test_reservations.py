import csv

import pytest

from max_float import config
from max_float.ingest import reservations

HEADER = "historicalreservationid,inventorytype,facilityid,startdate,orderdate\n"


def lines(*rows: str) -> list[str]:
    return [HEADER, *(row + "\n" for row in rows)]


def test_counts_applications_and_permits():
    counts = reservations.count(
        lines(
            "a,LOTTERY_PERMIT,234623,2025-07-07T00:00:00Z,2025-01-10",
            "b,LOTTERY_PERMIT,234623,2025-07-07T00:00:00Z,2025-01-11",
            "c,PERMIT,234623,2025-07-07T00:00:00Z,2025-03-01",
        ),
        {"234623"},
    )
    assert counts == {
        ("2025-07-07", "234623", "applications"): 2,
        ("2025-07-07", "234623", "permits"): 1,
    }


def test_ignores_other_permits_and_types():
    counts = reservations.count(
        lines(
            "a,LOTTERY_PERMIT,251576,2025-07-07T00:00:00Z,2025-01-10",
            "b,CAMPING,234623,2025-07-07T00:00:00Z,2025-01-10",
        ),
        {"234623"},
    )
    assert counts == {}


def test_reads_capitalized_header():
    header = "InventoryType,FacilityID,StartDate\n"
    rows = [header, "PERMIT,234623,2025-07-07\n"]
    assert reservations.count(rows, {"234623"}) == {
        ("2025-07-07", "234623", "permits"): 1
    }


def test_rejects_years_without_types():
    with pytest.raises(ValueError):
        reservations.launches(2018)


def test_write(tmp_path):
    row = {
        "date": "2025-07-07",
        "weekday": "Monday",
        "river": "Middle Fork Salmon",
        "ridb_id": "234623",
        "applications": 2,
        "permits": 1,
        "source_url": config.RESERVATIONS.format(year=2025),
    }
    path = tmp_path / "data" / "applications.csv"
    reservations.write([row], path)
    assert list(csv.DictReader(path.open())) == [
        {key: str(value) for key, value in row.items()}
    ]


def test_write_refuses_non_ascii(tmp_path):
    with pytest.raises(UnicodeEncodeError):
        reservations.write([{"river": "Snake – Hells Canyon"}], tmp_path / "a.csv")
