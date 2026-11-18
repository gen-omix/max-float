"""`rivers`, `launches` and `plan`: what the page and the API show.

Rivers and launches are read from the graph once, as they only change when it's
loaded, so restart the service after loading. A party's plan reads the party and
other parties' locked-in applications each time.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from functools import cache
from math import comb, isnan, prod
from statistics import fmean

from neo4j import Driver

from max_float import config
from max_float.graph import driver, party
from max_float.graph import subgraph as sg
from max_float.odds import group_odds
from max_float.plan import Application, best, diluted, solve, won

RIVERS = (
    "MATCH (r:River)-[i:IN]->(l:Lottery) "
    "RETURN r.name AS name, r.code AS code, l.ridb_id AS lottery, "
    "coalesce(l.choices_per_application, $choices) AS choices, "
    "r.max_trip_days AS max_trip_days, "
    "r.flow_starts AS flow_starts, "
    "i.season_start AS season_start, i.season_end AS season_end "
    "ORDER BY name"
)

Counts = Mapping[tuple[str, object], int]


@cache
def rivers() -> list[dict[str, object]]:
    """Each river in the graph, with its code, its lottery and how many choices
    an application to it has, its longest trip, where each flow category after
    "not running" starts in cfs, and season."""
    with driver() as connection, connection.session() as session:
        return [
            record.data()
            | {
                "season_start": record["season_start"].to_native(),
                "season_end": record["season_end"].to_native(),
            }
            for record in session.run(RIVERS, choices=config.DEFAULT_CHOICES)
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


def typical_flows(river: str) -> list[int | None]:
    """The typical flow category of each of a river's launches, by date."""
    found = sorted(
        (launch["date"], sg.typical(launch["flow_years"]))
        for launch in launches()
        if launch["river"] == river
    )
    return [step for _, step in found]


def against(every: Iterable[sg.Launch], counts: Counts) -> list[dict[str, object]]:
    """The launches with other parties' locked-in applications counted: n more
    applications each, and odds of p′ = permits / (applications + n), as p′ = p ·
    applications / (applications + n). A launch with no expected applications is
    left as it is."""
    out = []
    for launch in every:
        n = counts.get((launch["river"], launch["date"]), 0)
        applications = launch["applications"]
        if n and applications:
            odds = min(1.0, launch["odds"] * applications / (applications + n))
            launch = dict(launch) | {
                "odds": round(odds, config.ODDS_DIGITS),
                "applications": applications + n,
            }
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
    with as many at random from its launches. `chosen` has a launch once for each
    of the party's applications for it, and the launches it's compared with get as
    many each as the recommended ones have on average. With them, how many
    launches were recommended, and how many of those are among the most common.
    First for all rivers, then for each river with launches recommended."""
    held = Counter((launch["river"], launch["date"]) for launch in chosen)
    by_river = defaultdict(list)
    for launch in chosen:
        count = held.pop((launch["river"], launch["date"]), None)
        if count:
            by_river[launch["river"]].append((launch, count))
    pools = defaultdict(list)
    for launch in every:
        if launch["river"] in by_river:
            pools[launch["river"]].append(launch)
    rivers = []
    for river, found in by_river.items():
        pool = pools[river]
        common = sorted(
            pool, key=lambda launch: (-(launch["applications"] or 0), launch["date"])
        )
        mean = fmean(count for _, count in found)
        most = {launch["date"] for launch in common[: len(found)]}
        rivers.append(
            {
                "river": river,
                "launches": len(found),
                "in_common": sum(1 for launch, _ in found if launch["date"] in most),
                "recommended": group_odds(
                    won(launch, count) for launch, count in found
                ),
                "common": group_odds(
                    won(launch, mean) for launch in common[: len(found)]
                ),
                "random": at_random([won(launch, mean) for launch in pool], len(found)),
            }
        )
    overall = {
        "river": None,
        "launches": sum(each["launches"] for each in rivers),
        "in_common": sum(each["in_common"] for each in rivers),
        "recommended": 1 - prod(1 - each["recommended"] for each in rivers),
        "common": 1 - prod(1 - each["common"] for each in rivers),
        "random": 1 - prod(1 - each["random"] for each in rivers),
    }
    return [
        {
            name: round(value, config.ODDS_DIGITS)
            if isinstance(value, float)
            else value
            for name, value in each.items()
        }
        for each in [overall, *rivers]
    ]


def reading(value: float | None) -> float | None:
    """A reading, or None for a year without one."""
    return None if value is None or isnan(value) else value


def history(launch: sg.Launch) -> list[dict[str, object]]:
    """A launch's conditions in each of `config.FLOW_YEARS`: the mean
    flow over the trip in cfs, the mean high and the lowest low over the trip in °F, and
    the categories those were, by name. None where a year has no reading."""
    years = zip(
        config.FLOW_YEARS,
        launch["flow_years"],
        launch["flow_cfs_years"],
        launch["temperature_years"],
        launch["high_f_years"],
        launch["low_f_years"],
        strict=False,
    )
    return [
        {
            "year": year,
            "flow_cfs": reading(cfs),
            "flow": config.FLOW_CATEGORIES[flow] if flow >= 0 else None,
            "high_f": reading(high),
            "low_f": reading(low),
            "temperature": (
                config.TEMPERATURE_CATEGORIES[temperature] if temperature >= 0 else None
            ),
        }
        for year, flow, cfs, temperature, high, low in years
    ]


def row(launch: sg.Launch, application: Application, held: int, widened: bool) -> dict:
    """An application for the page: its launch and its lottery, with the typical categories by
    name, its history, who applies for it, its place on their application, its
    odds as one of the party's `held` for the launch, and the party's odds of
    winning the launch with them all."""
    flow = sg.typical(launch["flow_years"])
    temperature = sg.typical(launch["temperature_years"])
    return {
        "river": launch["river"],
        "code": launch["code"],
        "lottery": launch["lottery"],
        "date": launch["date"],
        "weekday": launch["date"].strftime("%A"),
        "odds": round(diluted(launch, held), config.ODDS_DIGITS),
        "party_odds": round(won(launch, held), config.ODDS_DIGITS),
        "flow_typical": config.FLOW_CATEGORIES[flow],
        "temperature_typical": config.TEMPERATURE_CATEGORIES[temperature],
        "widened": widened,
        "history": history(launch),
        "applicant": application.applicant,
        "choice": application.choice,
    }


def rows(
    applications: list[Application],
    by_launch: Mapping[tuple[str, object], sg.Launch],
    widened: Mapping[str, object],
) -> list[dict]:
    """A row for each application, with the applications for one launch together."""
    held = Counter((each.river, each.date) for each in applications)
    return [
        row(
            by_launch[each.river, each.date],
            each,
            held[each.river, each.date],
            each.river in widened,
        )
        for each in applications
    ]


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
    return {
        "launches": sorted(
            rows(applications, by_launch, found.widened),
            key=lambda found_row: (
                found_row["river"],
                best(by_launch[found_row["river"], found_row["date"]]),
            ),
        ),
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


def choices(river: str) -> int:
    """How many launch dates one application in a river's lottery can list."""
    found = config.LOTTERY_RULES.get(river, {}).get("choices_per_application")
    return found or config.DEFAULT_CHOICES


def shared(chosen: Iterable[str]) -> list[list[str]]:
    """Rivers among these that share a lottery, each such group in name order."""
    by_lottery: dict[object, list[str]] = defaultdict(list)
    for river in sorted(chosen):
        by_lottery[config.RIVERS.get(river, river)].append(river)
    return [names for names in by_lottery.values() if len(names) > 1]


def placed(person: party.Applicant, names: list[str]) -> bool:
    """Whether an applicant has given each choice on a shared lottery's
    application to exactly one of these rivers."""
    slots = [slot for name in names for slot in person.rivers[name].slots or []]
    return sorted(slots) == list(range(choices(names[0])))


def split(person: party.Applicant) -> bool:
    """Whether an applicant has given every choice of each lottery they share
    between rivers to one of them."""
    return all(placed(person, names) for names in shared(person.rivers))


def caps(stored: party.Party) -> dict[str, dict[str, int]]:
    """For each river that shares a lottery with another an applicant chose, how
    many of that applicant's choices go to it, where they've given each choice to
    one river. The plan decides for anyone who hasn't."""
    found: dict[str, dict[str, int]] = defaultdict(dict)
    for name, person in stored.applicants.items():
        for rivers_ in shared(person.rivers):
            if placed(person, rivers_):
                for river in rivers_:
                    found[river][name] = len(person.rivers[river].slots or [])
    return dict(found)


def rated(person: party.Applicant) -> bool:
    """Whether an applicant has rated every row of their preferences for all
    rivers, with at least one flow and one temperature category above No."""
    return (
        sg.rated(person.flow)
        and sg.rated(person.temperature)
        and sg.rated(person.priority, scale=False)
    )


def for_team(stored: party.Party) -> sg.Party:
    """The party as its plan sees it: the rivers any of its applicants applies
    for, with who applies for each and the trip length the party set, the shares
    of its applicants' ratings averaged over those who have rated them all, for
    all rivers and for each river any of them set, or the typical ones while no
    one has, everyone's days away, its minimum, one unless set higher, and its
    seed."""
    people = [person for person in stored.applicants.values() if rated(person)]
    if people:
        preferences = sg.Preferences(
            sg.mean_shares([person.flow for person in people]),
            sg.mean_shares([person.temperature for person in people]),
            sg.mean_priority([person.priority for person in people]),
        )
    else:
        preferences = sg.Preferences(
            sg.scale(config.TYPICAL_FLOW),
            sg.scale(config.TYPICAL_TEMPERATURE),
            sg.priority(config.TYPICAL_PRIORITY),
        )
    applying: dict[str, list[str]] = defaultdict(list)
    for name, person in stored.applicants.items():
        for river in person.rivers:
            applying[river].append(name)
    rivers = {}
    for river in sorted(applying):
        owns = [person.rivers.get(river, party.Own()) for person in people]
        rivers[river] = sg.Considered(
            stored.rivers.get(river),
            river_mean("flow", people, owns, sg.mean_shares),
            river_mean("temperature", people, owns, sg.mean_shares),
            river_mean("priority", people, owns, sg.mean_priority),
        )
    return sg.Party(
        preferences,
        rivers,
        stored.minimum or 1,
        {name: person.away for name, person in stored.applicants.items()},
        dict(applying),
        stored.seed,
        caps(stored),
    )


@cache
def connected() -> Driver:
    """One driver for the party calls, which come with every request."""
    return driver()


def shares_of(found: sg.Shares | None, categories: int) -> list[float] | None:
    """Shares as one for each category in step order, as the page takes them."""
    if found is None:
        return None
    return [round(found.get(step, 0), 4) for step in range(categories)]


def priority_of(priority: Iterable[float] | None) -> dict[str, float] | None:
    """A priority's ratings or shares as the page takes them, by part."""
    return None if priority is None else sg.Priority(*priority)._asdict()


def party_view(key: str) -> dict[str, object] | None:
    """A party as the page shows it: its rivers' trip lengths, minimum and
    applicants as stored, with each applicant's ratings and whether they've rated
    them all; the shares of its preferences averaged over those who have, for all
    rivers and for each river any applicant applies for, or None while no one
    has; its applications and when they were locked in; and how many other
    parties have locked in for each river. None for a key that opens nothing."""
    with connected().session() as session:
        stored = party.read(session, key)
        others = {} if stored is None else party.locked_parties(session, key)
    if stored is None:
        return None
    seen = for_team(stored)
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
                "priority": priority_of(person.priority),
                "rivers": {
                    river: {
                        "flow": own.flow,
                        "temperature": own.temperature,
                        "priority": priority_of(own.priority),
                        "slots": own.slots,
                    }
                    for river, own in person.rivers.items()
                },
                "away": person.away,
                "rated": rated(person),
                "done": person.done,
            }
            for name, person in stored.applicants.items()
        },
        "preferences": {
            "flow": shares_of(seen.preferences.flow, flows),
            "temperature": shares_of(seen.preferences.temperature, temperatures),
            "priority": priority_of(seen.preferences.priority),
            "rivers": {
                river: {
                    "flow": shares_of(considered.flow, flows),
                    "temperature": shares_of(considered.temperature, temperatures),
                    "priority": priority_of(considered.priority),
                }
                for river, considered in seen.rivers.items()
            },
        }
        if any(rated(person) for person in stored.applicants.values())
        else None,
        "applications": [each._asdict() for each in stored.applications],
        "locked": stored.locked,
        "edited": stored.edited,
        "locked_parties": others,
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


class NotSplit(Exception):
    """An applicant chose rivers that share a lottery without giving each of its
    application's choices to one of them."""


class NotRated(Exception):
    """An applicant hasn't rated every row of their preferences, or no one in a
    party has, so there's nothing to plan with yet."""


class Locked(Exception):
    """A party's dates are locked in, so who is in it can't change."""


def remove_applicant(key: str, name: str) -> bool:
    """Remove an applicant from the party, with their days away and applications.
    False for a key that opens nothing. Raises `Locked` while the party's dates
    are locked in, as that would change them."""
    with connected().session() as session:
        stored = party.read(session, key)
        if stored is None:
            return False
        if stored.locked:
            raise Locked
        return party.remove_applicant(session, key, name)


def mark_done(key: str, name: str) -> object | None:
    """Mark an applicant done with their rivers, preferences and days, until they
    next change anything, and return when. None for a key that opens nothing. An
    applicant not in the party is a KeyError, one with no rivers chosen is
    `NoRivers`, one who hasn't rated every row is `NotRated`, one who hasn't
    given each choice of a shared lottery to a river is `NotSplit`, and a party
    whose dates are locked in is `Locked`."""
    with connected().session() as session:
        stored = party.read(session, key)
        if stored is None:
            return None
        if name not in stored.applicants:
            raise KeyError(name)
        if stored.locked:
            raise Locked
        if not stored.applicants[name].rivers:
            raise NoRivers
        if not rated(stored.applicants[name]):
            raise NotRated
        if not split(stored.applicants[name]):
            raise NotSplit
        when = party.done(session, key, name)
        if when is None:
            raise Locked
        return when


def seeded(session: object, key: str, stored: party.Party) -> party.Party:
    """The party with its seed, given one now if it was made before parties had
    them."""
    if stored.seed is not None:
        return stored
    return stored._replace(seed=party.seeded(session, key))


def applications_of(found: dict[str, object]) -> list[Application]:
    """A plan's rows as applications."""
    return [
        Application(each["applicant"], each["river"], each["date"], each["choice"])
        for each in found["launches"]
    ]


def frozen(stored: party.Party, counts: Counts) -> dict[str, object]:
    """The team's plan while its dates are locked in: its applications as locked,
    with their launches' odds as they are now."""
    every = against(launches(), counts) if counts else launches()
    by_launch = {(launch["river"], launch["date"]): launch for launch in every}
    applications = [
        Application(*each)
        for each in stored.applications
        if (each.river, each.date) in by_launch
    ]
    chosen = [by_launch[each.river, each.date] for each in applications]
    return {
        "launches": sorted(
            rows(applications, by_launch, {}),
            key=lambda found_row: (
                found_row["river"],
                -found_row["party_odds"],
                found_row["date"],
            ),
        ),
        "odds": compared(chosen, every),
        "widened": {},
        "unavailable": [],
    }


class NoRivers(Exception):
    """An applicant said they were done without choosing any river to apply for."""


def party_plan(key: str, applicant: str | None = None) -> dict[str, object] | None:
    """A party's plan by key, with other parties' locked-in applications counted,
    or None for a key that opens nothing. It's saved with the party, or, once its
    dates are locked in, it is the locked dates. Each launch says how many other
    parties have locked in for it. With an applicant it has only the launches they
    apply for, and their own odds of at least one permit with them. An applicant
    not in the party is a KeyError. While the dates can
    change, an applicant who hasn't rated every row, or a party where no one has,
    is `NotRated`."""
    with connected().session() as session:
        stored = party.read(session, key)
        if stored is None:
            return None
        if applicant is not None and applicant not in stored.applicants:
            raise KeyError(applicant)
        if not stored.locked and (
            not any(rated(person) for person in stored.applicants.values())
            or (applicant is not None and not rated(stored.applicants[applicant]))
        ):
            raise NotRated
        counts = party.applied(session, key)
        teams = party.locked_launches(session, key)
        if stored.locked:
            found = frozen(stored, counts)
        else:
            found = plan(for_team(seeded(session, key, stored)), counts)
            party.save_plan(session, key, applications_of(found))
    for each in found["launches"]:
        each["locked_parties"] = teams.get((each["river"], each["date"]), 0)
    if applicant is None:
        return found
    theirs = [each for each in found["launches"] if each["applicant"] == applicant]
    return found | {"launches": theirs, "odds": own_odds(theirs, counts)}


def own_odds(theirs: list[dict], counts: Counts) -> list[dict]:
    """One applicant's odds of at least one permit with their own applications,
    against as many of the most common launches and launches at random, each
    with one application."""
    every = against(launches(), counts) if counts else launches()
    by_launch = {(launch["river"], launch["date"]): launch for launch in every}
    return compared([by_launch[each["river"], each["date"]] for each in theirs], every)


class NothingToLock(Exception):
    """A party's plan has no launches, so there are no dates to lock in."""


class NotDone(Exception):
    """Some of a party's applicants aren't done, so it can't lock in its dates.
    Its argument is their names."""


def lock(key: str) -> object | None:
    """Lock in the team's dates: plan afresh, save the plan as applied, and return
    when, or None for a key that opens nothing. Raises `NotDone`, with their names,
    when any applicant isn't done, as locking in says the team agrees, and
    `NothingToLock` when the plan has no launches."""
    with connected().session() as session:
        stored = party.read(session, key)
        if stored is None:
            return None
        waiting = [
            name for name, person in stored.applicants.items() if not person.done
        ]
        if waiting:
            raise NotDone(waiting)
        seen = for_team(seeded(session, key, stored))
        found = plan(seen, party.applied(session, key))
        if not found["launches"]:
            raise NothingToLock
        return party.lock(session, key, applications_of(found))


def unlock(key: str) -> bool:
    """Unlock the team's dates, so its plan is worked out and saved again. False
    for a key that opens nothing."""
    with connected().session() as session:
        return party.unlock(session, key)
