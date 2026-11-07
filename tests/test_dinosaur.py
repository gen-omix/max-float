import datetime
from collections import Counter

import numpy as np
import pytest

from max_float.ingest import dinosaur, seasons


def simulate(seed: int) -> tuple[dict[datetime.date, int], float]:
    """Applications from known curves, and the true Yampa share."""
    start, lodore_end = seasons.season(dinosaur.LODORE, 2025)
    yampa_end = seasons.season(dinosaur.YAMPA, 2025)[1]
    length = (lodore_end - start).days
    weekday = np.log([1.6, 1.0, 0.9, 0.9, 1.1, 1.0, 0.8])
    rng = np.random.default_rng(seed)
    counts, yampa_total = {}, 0.0
    for day in range(length + 1):
        date = start + datetime.timedelta(day)
        t = day / length
        effect = weekday[date.weekday()]
        lodore = np.exp(4.0 + 1.5 * t - 2.5 * t**2 + effect)
        yampa = np.exp(4.5 + 2.0 * t - 6.0 * t**2 + effect) if date <= yampa_end else 0
        counts[date] = int(rng.poisson(lodore + yampa))
        yampa_total += yampa * counts[date] / (lodore + yampa)
    return counts, yampa_total / sum(counts.values())


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_recovers_yampa_share(seed):
    counts, truth = simulate(seed)
    share = dinosaur.lodore_share(counts)
    estimate = sum(counts[d] * (1 - s) for d, s in share.items()) / sum(counts.values())
    assert estimate == pytest.approx(truth, abs=0.03)


def test_after_yampa_season_is_all_lodore():
    counts, _ = simulate(0)
    yampa_end = seasons.season(dinosaur.YAMPA, 2025)[1]
    share = dinosaur.lodore_share(counts)
    assert all(s == 1 for d, s in share.items() if d > yampa_end)


def application_rows(counts):
    return [
        {
            "date": d.isoformat(),
            "weekday": d.strftime("%A"),
            "river": "Green - Gates of Lodore / Yampa",
            "ridb_id": "250014",
            "applications": str(n),
            "permits": "0",
            "source_url": "u",
        }
        for d, n in counts.items()
    ]


def test_launches_keep_application_totals():
    counts, _ = simulate(0)
    out = dinosaur.launches(application_rows(counts), Counter())
    assert sum(row["applications"] for row in out) == pytest.approx(
        sum(counts.values()), abs=len(out) * 0.05
    )
    assert {row["river"] for row in out} == {dinosaur.LODORE, dinosaur.YAMPA}


def test_launches_keep_other_rivers_and_permits():
    other = {
        "date": "2025-07-07",
        "weekday": "Monday",
        "river": "Selway",
        "ridb_id": "234624",
        "applications": "300",
        "permits": "1",
        "source_url": "u",
    }
    counts, _ = simulate(0)
    permits = Counter({("2025-06-02", dinosaur.YAMPA): 1})
    out = dinosaur.launches([other, *application_rows(counts)], permits)
    assert other in out
    yampa = next(
        row
        for row in out
        if row["date"] == "2025-06-02" and row["river"] == dinosaur.YAMPA
    )
    assert yampa["permits"] == 1


HEADER = "inventorytype,facilityid,startdate,enddate,orderdate\n"


def test_lottery_permits_by_trip_length():
    rows = [
        HEADER,
        "PERMIT,250014,2025-06-02T00:00:00Z,2025-06-05T00:00:00Z,2025-02-20T18:00:00Z\n",
        "PERMIT,250014,2025-06-02T00:00:00Z,2025-06-06T00:00:00Z,2025-02-20T18:00:00Z\n",
        "PERMIT,250014,2025-06-02T00:00:00Z,2025-06-07T00:00:00Z,2025-02-20T18:00:00Z\n",
        "PERMIT,250014,2025-06-02T00:00:00Z,2025-06-07T00:00:00Z,2025-03-06T15:00:00Z\n",
        "LOTTERY_PERMIT,250014,2025-06-02T00:00:00Z,,2025-01-20T18:00:00Z\n",
        "PERMIT,234623,2025-06-02T00:00:00Z,2025-06-08T00:00:00Z,2025-02-20T18:00:00Z\n",
    ]
    assert dinosaur.permits(rows) == {
        ("2025-06-02", dinosaur.LODORE): 2,
        ("2025-06-02", dinosaur.YAMPA): 1,
    }
