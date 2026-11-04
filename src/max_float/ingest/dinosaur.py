"""Split Dinosaur lottery applications between Gates of Lodore and the Yampa.

Both rivers share one lottery (RIDB 250014), and RIDB records only the launch
date. Gates of Lodore's season runs past the Yampa's, so applications after the
Yampa's last launch are all for Gates of Lodore. Before that, each launch date's
applications are treated as a two-component Poisson mixture:

    applications(d) ~ Poisson(lodore(d) + yampa(d))
    log river(d) = a + b·t + c·t² + weekday(d)

where t is the fraction of the season elapsed, each river has its own a, b, c,
and both share the weekday effect. EM allocates each date's applications
between the rivers. The split in the overlap rests on the curves' shape.

Permits record the trip's end date. Yampa trips run 5 nights or more and Gates
of Lodore trips fewer, so each permit is assigned by its length.
"""

import datetime
from collections import Counter, defaultdict
from collections.abc import Iterable

import numpy as np

from max_float.ingest import reservations

RIDB_ID = "250014"
LODORE = "Green – Gates of Lodore"
YAMPA = "Yampa"
YAMPA_NIGHTS = 5


def nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime.date:
    """The nth weekday (Monday is 0) of a month."""
    first = datetime.date(year, month, 1)
    return first + datetime.timedelta((weekday - first.weekday()) % 7 + 7 * (n - 1))


def season(year: int) -> tuple[datetime.date, datetime.date, datetime.date]:
    """First launch, the Yampa's last launch and Gates of Lodore's last launch."""
    return (
        nth_weekday(year, 5, 0, 2),
        nth_weekday(year, 7, 5, 2),
        nth_weekday(year, 9, 4, 2),
    )


def poisson_fit(x: np.ndarray, y: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """Poisson regression coefficients by Newton's method from `beta`."""
    for _ in range(100):
        mu = np.exp(x @ beta)
        step = np.linalg.solve(x.T @ (x * mu[:, None]), x.T @ (y - mu))
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return beta


def lodore_share(
    counts: dict[datetime.date, int], tolerance: float = 1e-9
) -> dict[datetime.date, float]:
    """Share of each launch date's applications that are for Gates of Lodore."""
    dates = sorted(counts)
    start, yampa_end, lodore_end = season(dates[0].year)
    n = np.array([counts[d] for d in dates], dtype=float)
    t = np.array([(d - start).days / (lodore_end - start).days for d in dates])
    curve = np.column_stack([np.ones_like(t), t, t**2])
    weekday = np.array([[d.weekday() == k for k in range(1, 7)] for d in dates])
    overlap = np.array([d <= yampa_end for d in dates])
    zeros = np.zeros_like(curve)
    x = np.vstack(
        [
            np.hstack([curve, zeros, weekday]),
            np.hstack([zeros, curve, weekday])[overlap],
        ]
    )
    beta = np.zeros(x.shape[1])
    beta[[0, 3]] = np.log(n.mean() / 2)
    share = np.where(overlap, 0.5, 1.0)
    for _ in range(10_000):
        y = np.concatenate([n * share, (n * (1 - share))[overlap]])
        beta = poisson_fit(x, y, beta)
        mu = np.exp(x @ beta)
        lodore = mu[: len(dates)]
        yampa = np.zeros(len(dates))
        yampa[overlap] = mu[len(dates) :]
        new = lodore / (lodore + yampa)
        if np.max(np.abs(new - share)) < tolerance:
            share = new
            break
        share = new
    return dict(zip(dates, share.tolist(), strict=True))


def river(record: dict[str, str]) -> str:
    """The river a Dinosaur permit is for, from its trip length."""
    if not record["enddate"]:
        return LODORE
    start, end = (
        datetime.date.fromisoformat(record[name][:10])
        for name in ("startdate", "enddate")
    )
    return YAMPA if (end - start).days >= YAMPA_NIGHTS else LODORE


def permits(rows: Iterable[str]) -> Counter[tuple[str, str]]:
    """Dinosaur permits per (date, river) in a reservations CSV."""
    return Counter(
        (record["startdate"][:10], river(record))
        for record in reservations.records(rows, {RIDB_ID})
        if record["inventorytype"] == "PERMIT"
    )


def launches(
    rows: list[dict[str, str]], counts: Counter[tuple[str, str]]
) -> list[dict[str, object]]:
    """Launch rows with Dinosaur split into Gates of Lodore and the Yampa.

    `rows` come from applications.csv and `counts` from `permits`.
    """
    out: list[dict[str, object]] = [row for row in rows if row["ridb_id"] != RIDB_ID]
    dinosaur = {row["date"]: row for row in rows if row["ridb_id"] == RIDB_ID}
    by_year: dict[int, dict[datetime.date, int]] = defaultdict(dict)
    for date, row in dinosaur.items():
        day = datetime.date.fromisoformat(date)
        start, _, lodore_end = season(day.year)
        if int(row["applications"]) and start <= day <= lodore_end:
            by_year[day.year][day] = int(row["applications"])
    shares = {
        day.isoformat(): share
        for counts_by_day in by_year.values()
        for day, share in lodore_share(counts_by_day).items()
    }
    for date, row in dinosaur.items():
        applications = int(row["applications"])
        share = shares.get(date, 1.0)
        for name, part in ((LODORE, share), (YAMPA, 1 - share)):
            estimate = round(applications * part, 1)
            if estimate or counts[date, name]:
                out.append(
                    row
                    | {
                        "river": name,
                        "applications": estimate,
                        "permits": counts[date, name],
                    }
                )
    return sorted(out, key=lambda row: (row["river"], row["date"]))
