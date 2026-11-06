"""`rivers`, `launches` and `plan`: what the page and the API show.

For now a plan is for one applicant, so it doesn't need the flow. Rivers and
launches are read from the graph once, as they only change when it's loaded, so
restart the service after loading.
"""

from collections import Counter, defaultdict
from functools import cache

from max_float import config
from max_float.graph import driver
from max_float.graph import subgraph as sg

RIVERS = (
    "MATCH (r:River)-[i:IN]->(:Lottery) "
    "RETURN r.name AS name, r.code AS code, r.max_trip_days AS max_trip_days, "
    "i.season_start AS season_start, i.season_end AS season_end "
    "ORDER BY name"
)


@cache
def rivers() -> list[dict[str, object]]:
    """Each river in the graph, with its code, longest trip and season."""
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


def score(launch: sg.Launch, w: float | None = None) -> float:
    """A launch's value at a weight on conditions, by default its river's: its odds
    times m to the w."""
    return launch["odds"] * launch["m"] ** (launch["w"] if w is None else w)


def ranked(found: list[sg.Launch]) -> list[sg.Launch]:
    """Every launch, by river, with each river's best first."""
    return sorted(
        found,
        key=lambda launch: (launch["river"], -score(launch), launch["date"]),
    )


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
        best = sorted(
            launches_in_lottery,
            key=lambda launch: (-score(launch, launch["party_w"]), launch["date"]),
        )
        taken.update(launch["river"] for launch in best[:choices])
    return taken


def recommended(found: list[sg.Launch]) -> set[tuple[str, object]]:
    """The (river, date) of each launch to apply for: each river's share, chosen at
    its own priority, so a river's priority changes which launches it gets but never
    how many."""
    chosen = set()
    for river, share in shares(found).items():
        own = sorted(
            (launch for launch in found if launch["river"] == river),
            key=lambda launch: (-score(launch), launch["date"]),
        )
        chosen |= {(river, launch["date"]) for launch in own[:share]}
    return chosen


def row(launch: sg.Launch, widened: bool, chosen: bool) -> dict[str, object]:
    """A launch for the page, with its typical categories by name."""
    flow = sg.typical(launch["flow_years"])
    temperature = sg.typical(launch["temperature_years"])
    return {
        "river": launch["river"],
        "code": launch["code"],
        "date": launch["date"],
        "weekday": launch["date"].strftime("%A"),
        "odds": launch["odds"],
        "m": launch["m"],
        "flow_typical": config.FLOW_CATEGORIES[flow],
        "temperature_typical": config.TEMPERATURE_CATEGORIES[temperature],
        "widened": widened,
        "recommended": chosen,
    }


def plan(party: sg.Party) -> dict[str, object]:
    """Every launch left for a party, with each river's best first and the ones to
    apply for marked, any rivers widened, and any rivers with no launch the party is
    free for."""
    found = sg.subgraph(party, launches())
    chosen = recommended(found.launches)
    return {
        "launches": [
            row(
                launch,
                launch["river"] in found.widened,
                (launch["river"], launch["date"]) in chosen,
            )
            for launch in ranked(found.launches)
        ],
        "widened": found.widened,
        "unavailable": found.unavailable,
    }
