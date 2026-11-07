"""`rivers`, `launches` and `plan`: what the page and the API show.

For now a plan is for one applicant, so it doesn't need the flow. Rivers and
launches are read from the graph once, as they only change when it's loaded, so
restart the service after loading.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from functools import cache
from math import comb, prod

from max_float import config
from max_float.graph import driver
from max_float.graph import subgraph as sg
from max_float.odds import group_odds

RIVERS = (
    "MATCH (r:River)-[i:IN]->(:Lottery) "
    "RETURN r.name AS name, r.code AS code, r.max_trip_days AS max_trip_days, "
    "r.flow_starts AS flow_starts, "
    "i.season_start AS season_start, i.season_end AS season_end "
    "ORDER BY name"
)


@cache
def rivers() -> list[dict[str, object]]:
    """Each river in the graph, with its code, longest trip, where each flow
    category after "not running" starts in cfs, and season."""
    with driver() as connection, connection.session() as session:
        return [
            record.data()
            | {
                "season_start": record["season_start"].to_native(),
                "season_end": record["season_end"].to_native(),
            }
            for record in session.run(RIVERS)
        ]


@cache
def launches() -> list[dict[str, object]]:
    """Every active launch in the graph."""
    names = [river["name"] for river in rivers()]
    with driver() as connection, connection.session() as session:
        return sg.read(session, names)


def dates(river: str) -> list[object]:
    """The dates of a river's launches."""
    return sorted(launch["date"] for launch in launches() if launch["river"] == river)


def score(launch: sg.Launch, priority: sg.Priority | None = None) -> float:
    """A launch's value at a priority, by default its river's: its odds, flow match
    and temperature match, each to the power of its share of the slices."""
    odds, flow, temperature = launch["priority"] if priority is None else priority
    total = odds + flow + temperature
    return (
        launch["odds"] ** (odds / total)
        * launch["flow_match"] ** (flow / total)
        * launch["temperature_match"] ** (temperature / total)
    )


def best(launch: sg.Launch, priority: sg.Priority | None = None) -> tuple:
    """Sorts launches best first at a priority: by score, then odds, then date."""
    return (-score(launch, priority), -launch["odds"], launch["date"])


def shares(found: list[sg.Launch]) -> Counter:
    """How many launches to recommend from each river: its lottery's choices per
    application, with rivers in one lottery sharing them by their best launches at
    the party's priority."""
    by_lottery = defaultdict(list)
    for launch in found:
        by_lottery[launch["lottery"]].append(launch)
    taken: Counter = Counter()
    for launches_in_lottery in by_lottery.values():
        choices = launches_in_lottery[0]["choices"] or config.DEFAULT_CHOICES
        ordered = sorted(
            launches_in_lottery,
            key=lambda launch: best(launch, launch["party_priority"]),
        )
        taken.update(launch["river"] for launch in ordered[:choices])
    return taken


def recommended(found: list[sg.Launch]) -> list[sg.Launch]:
    """The launches to apply for, by river with each river's best first: each
    river's share, chosen at its own priority, so a river's priority changes which
    launches it gets but never how many."""
    chosen = []
    for river, share in sorted(shares(found).items()):
        own = sorted((launch for launch in found if launch["river"] == river), key=best)
        chosen += own[:share]
    return chosen


def at_random(odds: list[float], count: int) -> float:
    """The odds of at least one permit from `count` launches picked at random from
    launches with these odds: one less the mean, over every way to pick them, of the
    chance that none wins."""
    none = [1.0] + [0.0] * count
    for each in odds:
        for picked in range(count, 0, -1):
            none[picked] += none[picked - 1] * (1 - each)
    return 1 - none[count] / comb(len(odds), count)


def compared(chosen: list[sg.Launch], every: Iterable[sg.Launch]) -> list[dict]:
    """The odds of at least one permit with the recommended launches, with as many
    of each river's most common launches, those with the most applications, and
    with as many at random from its launches. First for all rivers, then for each
    river with launches recommended."""
    by_river = defaultdict(list)
    for launch in chosen:
        by_river[launch["river"]].append(launch["odds"])
    pools = defaultdict(list)
    for launch in every:
        if launch["river"] in by_river:
            pools[launch["river"]].append(launch)
    rivers = []
    for river, odds in by_river.items():
        pool = pools[river]
        common = sorted(
            pool, key=lambda launch: (-(launch["applications"] or 0), launch["date"])
        )
        rivers.append(
            {
                "river": river,
                "recommended": group_odds(odds),
                "common": group_odds(launch["odds"] for launch in common[: len(odds)]),
                "random": at_random([launch["odds"] for launch in pool], len(odds)),
            }
        )
    overall = {
        "river": None,
        "recommended": group_odds(launch["odds"] for launch in chosen),
        "common": 1 - prod(1 - each["common"] for each in rivers),
        "random": 1 - prod(1 - each["random"] for each in rivers),
    }
    return [
        {
            name: round(value, config.ODDS_DIGITS) if name != "river" else value
            for name, value in each.items()
        }
        for each in [overall, *rivers]
    ]


def row(launch: sg.Launch, widened: bool) -> dict[str, object]:
    """A launch for the page, with its typical categories by name."""
    flow = sg.typical(launch["flow_years"])
    temperature = sg.typical(launch["temperature_years"])
    return {
        "river": launch["river"],
        "code": launch["code"],
        "date": launch["date"],
        "weekday": launch["date"].strftime("%A"),
        "odds": launch["odds"],
        "flow_typical": config.FLOW_CATEGORIES[flow],
        "temperature_typical": config.TEMPERATURE_CATEGORIES[temperature],
        "widened": widened,
    }


def plan(party: sg.Party) -> dict[str, object]:
    """The launches to apply for, by river with each river's best first; the odds
    of at least one permit with them against the most common launches and launches
    at random; any rivers widened; and any rivers with no launch the party is free
    for."""
    every = launches()
    found = sg.subgraph(party, every)
    chosen = recommended(found.launches)
    return {
        "launches": [
            row(launch, launch["river"] in found.widened) for launch in chosen
        ],
        "odds": compared(chosen, every),
        "widened": found.widened,
        "unavailable": found.unavailable,
    }
