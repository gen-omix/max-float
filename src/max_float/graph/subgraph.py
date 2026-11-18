"""A party's own view of the public graph, built in memory for each plan.

Nothing here writes to the graph: launches a party's preferences leave out are only
left out of its subgraph, so every party starts from the same public graph.
"""

import datetime
import random
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from statistics import fmean
from typing import NamedTuple

from neo4j import Session

from max_float import config

Launch = Mapping[str, object]

# One rating for each row of a set, from 0 (No, or Not) to 3 (Ideal, or Most),
# or None for a row not rated yet.
Ratings = Sequence[int | None]

# Each category's share of the ratings on one scale, by step, for only the
# categories with any. A party's are the means of its applicants'.
Shares = Mapping[int, float]

# The share a category widening adds counts as having, of the most any has: OK
# beside Ideal.
WIDENED_SHARE = 1 / 3

READ = (
    "MATCH (n:Launch)-[:OF]->(r:River)-[:IN]->(l:Lottery) "
    "WHERE n.active AND n.river IN $rivers "
    "RETURN n.river AS river, r.code AS code, l.ridb_id AS lottery, "
    "l.choices_per_application AS choices, "
    "l.applications_per_person AS per_person, n.date AS date, n.odds AS odds, "
    "n.applications AS applications, "
    "n.trip_days AS trip_days, n.flow_years AS flow_years, "
    "n.temperature_years AS temperature_years, "
    "n.flow_cfs_years AS flow_cfs_years, n.high_f_years AS high_f_years, "
    "n.low_f_years AS low_f_years "
    "ORDER BY river, date"
)


class Priority(NamedTuple):
    """The shares of the priority that go to odds, to flow and to temperature.
    Only their ratios matter. A party's are the means of its applicants'."""

    odds: float
    flow: float
    temperature: float


class Preferences(NamedTuple):
    """The shares on each scale, and the priority."""

    flow: Shares
    temperature: Shares
    priority: Priority = Priority(1, 1, 1)


class Considered(NamedTuple):
    """A river a party is considering: its trip length, if the party has set one,
    and any preferences of its own. None follows the party."""

    days: int | None = None
    flow: Shares | None = None
    temperature: Shares | None = None
    priority: Priority | None = None


class Party(NamedTuple):
    """What a subgraph needs from a party. `away` is each applicant's days marked
    off. `applying` is who applies for each river, or None when everyone applies
    for them all. `minimum` is how many of a river's applicants must be free for
    a launch, or all of them where it has fewer. `seed` fixes the party's noise,
    and None gives none. `caps` has, for each river that shares a lottery with
    another an applicant chose, how many of that applicant's applications it can
    have."""

    preferences: Preferences
    rivers: Mapping[str, Considered]
    minimum: int
    away: Mapping[str, Iterable[datetime.date]]
    applying: Mapping[str, Collection[str]] | None = None
    seed: int | None = None
    caps: Mapping[str, Mapping[str, int]] | None = None


class Subgraph(NamedTuple):
    """A party's launches, each with its flow and temperature matches, its river's
    `priority`, the `party_priority`, the party's `noise` for it, and the
    `applicants` free for it who apply for its river. `widened` has
    the steps added for each river widened, and `unavailable` the rivers with no
    launch the party is free for."""

    launches: list[dict[str, object]]
    widened: dict[str, dict[str, list[int]]]
    unavailable: list[str]


def typical(years: Iterable[int]) -> int | None:
    """The median step over the years with a reading, taking the lower of two
    middle steps, or None with no readings."""
    steps = sorted(step for step in years if step >= 0)
    return steps[(len(steps) - 1) // 2] if steps else None


def rated(ratings: Ratings | None, scale: bool = True) -> bool:
    """Whether a set is rated: every row, and on a scale at least one row above
    No, as a scale with none would leave out every launch."""
    if ratings is None or any(rating is None for rating in ratings):
        return False
    return not scale or any(ratings)


def shares(ratings: Sequence[int]) -> list[float]:
    """Each row's share of a rated set: its rating over the set's total, or equal
    shares when every rating is 0."""
    total = sum(ratings)
    if not total:
        return [1 / len(ratings)] * len(ratings)
    return [rating / total for rating in ratings]


def by_step(values: Sequence[float] | None) -> Shares | None:
    """Shares by step, for the categories with any, from one for each category
    in step order. None stays None."""
    if values is None:
        return None
    return {step: value for step, value in enumerate(values) if value}


def scale(ratings: Sequence[int]) -> Shares:
    """One rated scale's shares by step."""
    return by_step(shares(ratings))


def priority(ratings: Sequence[int]) -> Priority:
    """One rated priority's shares."""
    return Priority(*shares(ratings))


def mean_shares(each: Sequence[Sequence[int]]) -> Shares:
    """A party's shares on one scale: the mean of its applicants' for each
    category. A category gets none only when no applicant rates it above No."""
    found = [shares(ratings) for ratings in each]
    return by_step([fmean(one[step] for one in found) for step in range(len(found[0]))])


def mean_priority(each: Sequence[Sequence[int]]) -> Priority:
    """A party's priority: the mean of its applicants' shares for each part."""
    found = [shares(ratings) for ratings in each]
    return Priority(*(fmean(one[part] for one in found) for part in range(3)))


def own(preferences: Preferences, river: Considered) -> Preferences:
    """The preferences for one river: its own where set, else the party's."""
    return Preferences(
        preferences.flow if river.flow is None else river.flow,
        preferences.temperature if river.temperature is None else river.temperature,
        preferences.priority if river.priority is None else river.priority,
    )


def match(years: list[int], found: Shares) -> float:
    """How well a launch's past years match the shares on one scale: the mean of
    each year's category's share over the most any category has. A year with no
    reading, or in a category with no share, counts 0."""
    most = max(found.values())
    return sum(found.get(step, 0) for step in years) / (most * len(years))


def kept(launch: Launch, preferences: Preferences) -> bool:
    """Whether the preferences keep a launch: its typical flow and temperature have
    shares."""
    return (
        typical(launch["flow_years"]) in preferences.flow
        and typical(launch["temperature_years"]) in preferences.temperature
    )


def between(step: int, found: Shares) -> set[int]:
    """A step, the nearest step with a share, and any between them. The lower one
    is nearest if two are equally near."""
    nearest = min(found, key=lambda other: (abs(other - step), other))
    return set(range(min(step, nearest), max(step, nearest) + 1))


def widen(launches: list[Launch], preferences: Preferences) -> Preferences | None:
    """The preferences with the nearest categories added, each with
    `WIDENED_SHARE` of the most any category has, so that at least one launch is
    kept, or None if none can be. Launches are scored by the steps from their
    typical flow and temperature to the nearest with a share, and the lowest score
    with a launch kept decides."""
    scored: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for launch in launches:
        flow = typical(launch["flow_years"])
        temperature = typical(launch["temperature_years"])
        if flow is None or temperature is None:
            continue
        score = min(abs(flow - step) for step in preferences.flow) + min(
            abs(temperature - step) for step in preferences.temperature
        )
        scored[score].append((flow, temperature))
    added_flow = WIDENED_SHARE * max(preferences.flow.values())
    added_temperature = WIDENED_SHARE * max(preferences.temperature.values())
    for score in sorted(scored):
        flows, temperatures = dict(preferences.flow), dict(preferences.temperature)
        for flow, temperature in scored[score]:
            for step in between(flow, preferences.flow):
                flows.setdefault(step, added_flow)
            for step in between(temperature, preferences.temperature):
                temperatures.setdefault(step, added_temperature)
        wider = preferences._replace(flow=flows, temperature=temperatures)
        if any(kept(launch, wider) for launch in launches):
            return wider
    return None


def free(
    launch: Launch, days: int, away: Mapping[str, Iterable[datetime.date]]
) -> list[str]:
    """The applicants with no day marked off in a trip from this launch."""
    trip = {launch["date"] + datetime.timedelta(day) for day in range(days)}
    return sorted(name for name, marked in away.items() if not trip & set(marked))


def moved(found: Mapping[int, float], start: Sequence[float]) -> float:
    """How much of a set's shares are placed differently from the typical ones,
    from 0 to 1."""
    total, whole = sum(found.values()), sum(start)
    return (
        sum(
            abs(found.get(step, 0) / total - count / whole)
            for step, count in enumerate(start)
        )
        / 2
    )


def unlike(preferences: Preferences) -> float:
    """How far preferences are from the typical ones, from 0 to 1: how much of the
    flow shares, the temperature shares and the priority have moved, added up,
    and 1 if that's more."""
    return min(
        1.0,
        moved(preferences.flow, config.TYPICAL_FLOW)
        + moved(preferences.temperature, config.TYPICAL_TEMPERATURE)
        + moved(dict(enumerate(preferences.priority)), config.TYPICAL_PRIORITY),
    )


def noise_size(preferences: Preferences) -> float:
    """How much noise preferences get: `config.PLAN_NOISE` at the typical ones,
    down to `config.PLAN_NOISE_LEAST` as they move away."""
    most, least = config.PLAN_NOISE, config.PLAN_NOISE_LEAST
    return most - (most - least) * unlike(preferences)


def noise(seed: int | None, launch: Launch, size: float) -> float:
    """What a party's noise multiplies a launch's worth by in its plan: a number
    from 1 − `size` to 1 + `size`, always the same for one seed and launch. 1 with
    no seed."""
    if seed is None:
        return 1.0
    drawn = random.Random(f"{seed} {launch['river']} {launch['date']}")
    return 1 + size * drawn.uniform(-1, 1)


def subgraph(party: Party, launches: Iterable[Launch]) -> Subgraph:
    """A party's subgraph from the public graph's launches, which it doesn't change.
    A launch is left out if it's for a river the party isn't considering, if fewer
    than `minimum` of the river's applicants are free for it, or if the river's
    preferences don't keep it. Its applicants are those of the river's who are
    free for it, so one who isn't gets other launches. A river they leave with no
    launches is widened."""
    open_launches: dict[str, list[tuple[Launch, list[str]]]] = {
        river: [] for river in party.rivers
    }
    for launch in launches:
        river = party.rivers.get(launch["river"])
        if river is None:
            continue
        away = party.away
        if party.applying is not None:
            applying = party.applying.get(launch["river"], ())
            away = {name: days for name, days in away.items() if name in applying}
        applicants = free(launch, river.days or launch["trip_days"], away)
        if len(applicants) >= max(1, min(party.minimum, len(away))):
            open_launches[launch["river"]].append((launch, applicants))
    out, widened, unavailable = [], {}, []
    for name, river in party.rivers.items():
        found = open_launches[name]
        if not found:
            unavailable.append(name)
            continue
        preferences = own(party.preferences, river)
        size = noise_size(preferences)
        if not any(kept(launch, preferences) for launch, _ in found):
            wider = widen([launch for launch, _ in found], preferences)
            if wider is None:
                unavailable.append(name)
                continue
            widened[name] = {
                "flow": sorted(wider.flow.keys() - preferences.flow.keys()),
                "temperature": sorted(
                    wider.temperature.keys() - preferences.temperature.keys()
                ),
            }
            preferences = wider
        out += [
            dict(launch)
            | {
                "flow_match": match(launch["flow_years"], preferences.flow),
                "temperature_match": match(
                    launch["temperature_years"], preferences.temperature
                ),
                "priority": preferences.priority,
                "party_priority": party.preferences.priority,
                "noise": noise(party.seed, launch, size),
                "applicants": applicants,
                "caps": (party.caps or {}).get(name, {}),
            }
            for launch, applicants in found
            if kept(launch, preferences)
        ]
    return Subgraph(out, widened, unavailable)


def read(session: Session, rivers: Iterable[str]) -> list[dict[str, object]]:
    """The active launches of `rivers` from the public graph."""
    found = []
    for record in session.run(READ, rivers=list(rivers)):
        launch = dict(record)
        found.append(launch | {"date": launch["date"].to_native()})
    return found


def for_party(session: Session, party: Party) -> Subgraph:
    """A party's subgraph, read from the public graph without writing to it."""
    return subgraph(party, read(session, party.rivers))
