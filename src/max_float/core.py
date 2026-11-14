"""`rivers`, `launches` and `plan`: what the page and the API show.

Rivers and launches are read from the graph once, as they only change when it's
loaded, so restart the service after loading. A party's plan reads the party and
other parties' locked-in applications each time.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from functools import cache
from math import comb, prod

from neo4j import Driver

from max_float import config
from max_float.graph import driver, party
from max_float.graph import subgraph as sg
from max_float.odds import group_odds
from max_float.plan import Application, best, solve

RIVERS = (
    "MATCH (r:River)-[i:IN]->(:Lottery) "
    "RETURN r.name AS name, r.code AS code, r.max_trip_days AS max_trip_days, "
    "r.flow_starts AS flow_starts, "
    "i.season_start AS season_start, i.season_end AS season_end "
    "ORDER BY name"
)

Counts = Mapping[tuple[str, object], int]


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


def against(every: Iterable[sg.Launch], counts: Counts) -> list[dict[str, object]]:
    """The launches with other parties' locked-in applications counted in their
    odds: p′ = permits / (applications + n), as p′ = p · applications / (applications
    + n). A launch with no expected applications keeps its odds."""
    out = []
    for launch in every:
        n = counts.get((launch["river"], launch["date"]), 0)
        applications = launch["applications"]
        if n and applications:
            odds = min(1.0, launch["odds"] * applications / (applications + n))
            launch = dict(launch) | {"odds": round(odds, config.ODDS_DIGITS)}
        out.append(launch)
    return out


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


def row(launch: sg.Launch, application: Application, widened: bool) -> dict:
    """An application for the page: its launch, with the typical categories by
    name, who applies for it, and its place on their application."""
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
        "applicant": application.applicant,
        "choice": application.choice,
    }


def plan(party_: sg.Party, counts: Counts | None = None) -> dict[str, object]:
    """The launches to apply for and who applies for each, by river with each
    river's best first; the odds of at least one permit with them against the most
    common launches and launches at random; any rivers widened; and any rivers with
    no launch the party is free for. `counts` are other parties' locked-in
    applications by launch."""
    every = launches() if not counts else against(launches(), counts)
    found = sg.subgraph(party_, every)
    by_launch = {(launch["river"], launch["date"]): launch for launch in found.launches}
    applications = solve(found.launches)
    chosen = [
        by_launch[application.river, application.date] for application in applications
    ]
    rows = sorted(
        (
            row(launch, application, launch["river"] in found.widened)
            for launch, application in zip(chosen, applications, strict=True)
        ),
        key=lambda found_row: (
            found_row["river"],
            best(by_launch[found_row["river"], found_row["date"]]),
        ),
    )
    return {
        "launches": rows,
        "odds": compared(chosen, every),
        "widened": found.widened,
        "unavailable": found.unavailable,
    }


def river_mean(
    name: str, people: list[party.Applicant], owns: list[party.Own], combine
) -> object:
    """A party's preference on one scale for one river: None unless an applicant
    set one for it, else the mean of each applicant's for that river, or their
    general one where they set none."""
    if not any(getattr(own, name) for own in owns):
        return None
    return combine(
        [
            getattr(own, name) or getattr(person, name)
            for own, person in zip(owns, people, strict=True)
        ]
    )


def for_group(stored: party.Party) -> sg.Party:
    """The party as its plan sees it: its applicants' votes and priority averaged,
    for all rivers and for each river any of them set, everyone's days away, and
    its minimum, the whole party unless set lower."""
    people = list(stored.applicants.values())
    if people:
        preferences = sg.Preferences(
            sg.mean_votes([person.flow for person in people]),
            sg.mean_votes([person.temperature for person in people]),
            sg.mean_priority([person.priority for person in people]),
        )
    else:
        preferences = sg.Preferences(
            sg.votes(config.START_FLOW),
            sg.votes(config.START_TEMPERATURE),
            sg.Priority(*config.START_PRIORITY),
        )
    rivers = {}
    for river, days in stored.rivers.items():
        owns = [person.rivers.get(river, party.Own()) for person in people]
        rivers[river] = sg.Considered(
            days,
            river_mean("flow", people, owns, sg.mean_votes),
            river_mean("temperature", people, owns, sg.mean_votes),
            river_mean("priority", people, owns, sg.mean_priority),
        )
    return sg.Party(
        preferences,
        rivers,
        min(stored.minimum or len(people), len(people)),
        {name: person.away for name, person in stored.applicants.items()},
    )


def for_applicant(stored: party.Party, name: str) -> sg.Party:
    """The party as one applicant's own plan sees it: their preferences, their days
    away, and the party's rivers, as if they were applying alone."""
    person = stored.applicants[name]
    rivers = {}
    for river, days in stored.rivers.items():
        own = person.rivers.get(river, party.Own())
        rivers[river] = sg.Considered(
            days,
            sg.votes(own.flow),
            sg.votes(own.temperature),
            None if own.priority is None else sg.Priority(*own.priority),
        )
    return sg.Party(
        sg.Preferences(
            sg.votes(person.flow),
            sg.votes(person.temperature),
            sg.Priority(*person.priority),
        ),
        rivers,
        1,
        {name: person.away},
    )


@cache
def connected() -> Driver:
    """One driver for the party calls, which come with every request."""
    return driver()


def counts_of(found: sg.Votes | None, categories: int) -> list[float] | None:
    """Votes as a count for each category in step order, as the page takes them."""
    if found is None:
        return None
    return [found.get(step, 0) for step in range(categories)]


def slices_of(priority: Iterable[float] | None) -> dict[str, float] | None:
    """A priority as the page takes it, by part."""
    return None if priority is None else sg.Priority(*priority)._asdict()


def party_view(key: str) -> dict[str, object] | None:
    """A party as the page shows it: its rivers, minimum and applicants as stored,
    its preferences averaged, its applications and when they were locked in, or
    None for a key that opens nothing."""
    with connected().session() as session:
        stored = party.read(session, key)
    if stored is None:
        return None
    seen = for_group(stored)
    flows, temperatures = (
        len(config.FLOW_CATEGORIES),
        len(config.TEMPERATURE_CATEGORIES),
    )
    return {
        "key": key,
        "minimum": stored.minimum,
        "rivers": stored.rivers,
        "applicants": {
            name: {
                "flow": person.flow,
                "temperature": person.temperature,
                "priority": slices_of(person.priority),
                "rivers": {
                    river: {
                        "flow": own.flow,
                        "temperature": own.temperature,
                        "priority": slices_of(own.priority),
                    }
                    for river, own in person.rivers.items()
                },
                "away": person.away,
            }
            for name, person in stored.applicants.items()
        },
        "preferences": {
            "flow": counts_of(seen.preferences.flow, flows),
            "temperature": counts_of(seen.preferences.temperature, temperatures),
            "priority": slices_of(seen.preferences.priority),
            "rivers": {
                river: {
                    "flow": counts_of(considered.flow, flows),
                    "temperature": counts_of(considered.temperature, temperatures),
                    "priority": slices_of(considered.priority),
                }
                for river, considered in seen.rivers.items()
            },
        },
        "applications": [each._asdict() for each in stored.applications],
        "locked": stored.locked,
        "edited": stored.edited,
    }


def create_party(
    ip: str,
    minimum: int | None,
    rivers: dict[str, int | None],
    name: str,
    applicant: party.Applicant,
) -> str:
    """A new party with its first applicant, and its key. Raises
    `party.TooManyParties` when the IP has made its week's parties."""
    with connected().session() as session:
        key = party.create(session, ip)
        party.save_party(session, key, minimum, rivers)
        party.save_applicant(session, key, name, applicant)
    return key


def save_party(key: str, minimum: int | None, rivers: dict[str, int | None]) -> bool:
    """Save the party's rivers and minimum. False for a key that opens nothing."""
    with connected().session() as session:
        return party.save_party(session, key, minimum, rivers)


def save_applicant(key: str, name: str, applicant: party.Applicant) -> bool:
    """Save an applicant's settings, adding them to the party if new. False for a
    key that opens nothing."""
    with connected().session() as session:
        return party.save_applicant(session, key, name, applicant)


def remove_applicant(key: str, name: str) -> bool:
    """Remove an applicant from the party. False for a key that opens nothing."""
    with connected().session() as session:
        return party.remove_applicant(session, key, name)


def applications_of(found: dict[str, object]) -> list[Application]:
    """A plan's rows as applications."""
    return [
        Application(each["applicant"], each["river"], each["date"], each["choice"])
        for each in found["launches"]
    ]


def frozen(stored: party.Party, counts: Counts) -> dict[str, object]:
    """The group's plan while its dates are locked in: its applications as locked,
    with their launches' odds as they are now."""
    every = against(launches(), counts) if counts else launches()
    by_launch = {(launch["river"], launch["date"]): launch for launch in every}
    applications = [
        Application(*each)
        for each in stored.applications
        if (each.river, each.date) in by_launch
    ]
    chosen = [by_launch[each.river, each.date] for each in applications]
    rows = sorted(
        (
            row(launch, application, False)
            for launch, application in zip(chosen, applications, strict=True)
        ),
        key=lambda each: (each["river"], -each["odds"], each["date"]),
    )
    return {
        "launches": rows,
        "odds": compared(chosen, every),
        "widened": {},
        "unavailable": [],
    }


def party_plan(key: str, applicant: str | None = None) -> dict[str, object] | None:
    """A party's plan by key, or one applicant's own, with other parties' locked-in
    applications counted in the odds, or None for a key that opens nothing. The
    group's plan is saved with the party, or, once its dates are locked in, it is
    the locked dates."""
    with connected().session() as session:
        stored = party.read(session, key)
        if stored is None:
            return None
        counts = party.applied(session, key)
        if applicant is None and stored.locked:
            return frozen(stored, counts)
        seen = (
            for_group(stored) if applicant is None else for_applicant(stored, applicant)
        )
        found = plan(seen, counts)
        if applicant is None:
            party.save_plan(session, key, applications_of(found))
    return found


def lock(key: str) -> object | None:
    """Lock in the group's dates: plan afresh, save the plan as applied, and return
    when, or None for a key that opens nothing."""
    with connected().session() as session:
        stored = party.read(session, key)
        if stored is None:
            return None
        found = plan(for_group(stored), party.applied(session, key))
        return party.lock(session, key, applications_of(found))


def unlock(key: str) -> bool:
    """Unlock the group's dates, so its plan is worked out and saved again. False
    for a key that opens nothing."""
    with connected().session() as session:
        return party.unlock(session, key)
