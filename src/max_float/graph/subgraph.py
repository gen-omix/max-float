"""A party's own view of the public graph, built in memory for each plan.

Nothing here writes to the graph: launches a party's preferences leave out are only
left out of its subgraph, so every party starts from the same public graph.
"""

import datetime
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import NamedTuple

from neo4j import Session

Launch = Mapping[str, object]

# The weight on conditions runs from 1/SPREAD at priority 0 to SPREAD at priority
# 10, and is 1 at MIDDLE, where a plan maximizes its reported chance.
SPREAD = 4
MIDDLE = 5

READ = (
    "MATCH (n:Launch)-[:OF]->(r:River)-[:IN]->(l:Lottery) "
    "WHERE n.active AND n.river IN $rivers "
    "RETURN n.river AS river, r.code AS code, l.ridb_id AS lottery, "
    "l.choices_per_application AS choices, n.date AS date, n.odds AS odds, "
    "n.trip_days AS trip_days, n.flow_years AS flow_years, "
    "n.temperature_years AS temperature_years "
    "ORDER BY river, date"
)


class Preferences(NamedTuple):
    """The steps checked on each scale, and the priority."""

    flow: frozenset[int]
    temperature: frozenset[int]
    priority: int = MIDDLE


class Considered(NamedTuple):
    """A river a party is considering: its trip length, if the party has set one,
    and any preferences of its own. None follows the party."""

    days: int | None = None
    flow: frozenset[int] | None = None
    temperature: frozenset[int] | None = None
    priority: int | None = None


class Party(NamedTuple):
    """What a subgraph needs from a party. `away` is each applicant's days marked
    off."""

    preferences: Preferences
    rivers: Mapping[str, Considered]
    minimum: int
    away: Mapping[str, Iterable[datetime.date]]


class Subgraph(NamedTuple):
    """A party's launches, each with its m, its w from its river's priority,
    `party_w` from the party's priority, and the `applicants` free for it. `widened`
    has the steps added for each river widened, and `unavailable` the rivers with
    no launch the party is free for."""

    launches: list[dict[str, object]]
    widened: dict[str, dict[str, list[int]]]
    unavailable: list[str]


def weight(priority: int) -> float:
    """A priority's w, the power on m in the plan's costs."""
    return SPREAD ** ((priority - MIDDLE) / MIDDLE)


def typical(years: Iterable[int]) -> int | None:
    """The median step over the years with a reading, taking the lower of two
    middle steps, or None with no readings."""
    steps = sorted(step for step in years if step >= 0)
    return steps[(len(steps) - 1) // 2] if steps else None


def own(preferences: Preferences, river: Considered) -> Preferences:
    """The preferences for one river: its own where set, else the party's."""
    return Preferences(
        preferences.flow if river.flow is None else river.flow,
        preferences.temperature if river.temperature is None else river.temperature,
        preferences.priority if river.priority is None else river.priority,
    )


def chance(launch: Launch, preferences: Preferences) -> float:
    """m: the share of past years with both of the launch's categories checked."""
    years = list(zip(launch["flow_years"], launch["temperature_years"]))
    matched = sum(
        flow in preferences.flow and temperature in preferences.temperature
        for flow, temperature in years
    )
    return matched / len(years)


def kept(launch: Launch, preferences: Preferences) -> bool:
    """Whether the preferences keep a launch: its typical flow and temperature are
    checked, and they were both checked in at least one past year."""
    return (
        typical(launch["flow_years"]) in preferences.flow
        and typical(launch["temperature_years"]) in preferences.temperature
        and chance(launch, preferences) > 0
    )


def between(step: int, checked: frozenset[int]) -> set[int]:
    """A step, the nearest checked step, and any between them. The lower one is
    nearest if two are equally near."""
    nearest = min(checked, key=lambda other: (abs(other - step), other))
    return set(range(min(step, nearest), max(step, nearest) + 1))


def widen(launches: list[Launch], preferences: Preferences) -> Preferences | None:
    """The preferences with the nearest categories added, so that at least one
    launch is kept, or None if none can be. Launches are scored by the steps from
    their typical flow and temperature to the nearest checked ones, and the lowest
    score with a launch kept decides."""
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
    for score in sorted(scored):
        flows, temperatures = set(preferences.flow), set(preferences.temperature)
        for flow, temperature in scored[score]:
            flows |= between(flow, preferences.flow)
            temperatures |= between(temperature, preferences.temperature)
        wider = preferences._replace(
            flow=frozenset(flows), temperature=frozenset(temperatures)
        )
        if any(kept(launch, wider) for launch in launches):
            return wider
    return None


def free(
    launch: Launch, days: int, away: Mapping[str, Iterable[datetime.date]]
) -> list[str]:
    """The applicants with no day marked off in a trip from this launch."""
    trip = {launch["date"] + datetime.timedelta(day) for day in range(days)}
    return sorted(name for name, marked in away.items() if not trip & set(marked))


def subgraph(party: Party, launches: Iterable[Launch]) -> Subgraph:
    """A party's subgraph from the public graph's launches, which it doesn't change.
    A launch is left out if it's for a river the party isn't considering, if fewer
    than `minimum` applicants are free for it, or if the river's preferences don't
    keep it. A river they leave with no launches is widened."""
    open_launches: dict[str, list[tuple[Launch, list[str]]]] = {
        river: [] for river in party.rivers
    }
    for launch in launches:
        river = party.rivers.get(launch["river"])
        if river is None:
            continue
        applicants = free(launch, river.days or launch["trip_days"], party.away)
        if len(applicants) >= party.minimum:
            open_launches[launch["river"]].append((launch, applicants))
    out, widened, unavailable = [], {}, []
    for name, river in party.rivers.items():
        found = open_launches[name]
        if not found:
            unavailable.append(name)
            continue
        preferences = own(party.preferences, river)
        if not any(kept(launch, preferences) for launch, _ in found):
            wider = widen([launch for launch, _ in found], preferences)
            if wider is None:
                unavailable.append(name)
                continue
            widened[name] = {
                "flow": sorted(wider.flow - preferences.flow),
                "temperature": sorted(wider.temperature - preferences.temperature),
            }
            preferences = wider
        out += [
            dict(launch)
            | {
                "m": chance(launch, preferences),
                "w": weight(preferences.priority),
                "party_w": weight(party.preferences.priority),
                "applicants": applicants,
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
