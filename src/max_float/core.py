"""`rivers`, `launches` and `plan`: what the page and the API show.

For now a plan is for one applicant, so it doesn't need the flow. Rivers and
launches are read from the graph once, as they only change when it's loaded, so
restart the service after loading.
"""

from collections import Counter
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


def score(launch: sg.Launch, w: float) -> float:
    """A launch's value in a plan at a weight on conditions: p times m to the w."""
    return launch["odds"] * launch["m"] ** w


def shares(found: list[sg.Launch], count: int) -> Counter:
    """How many launches each river gets: the best `count` launches with every
    river at the party's priority, up to each lottery's choices per application."""
    taken, by_lottery = Counter(), Counter()
    best_first = sorted(found, key=lambda launch: -score(launch, launch["party_w"]))
    for launch in best_first:
        if sum(taken.values()) == count:
            break
        choices = launch["choices"]
        if choices is None or by_lottery[launch["lottery"]] < choices:
            taken[launch["river"]] += 1
            by_lottery[launch["lottery"]] += 1
    return taken


def recommend(found: list[sg.Launch], count: int) -> list[sg.Launch]:
    """The launches to apply for: each river's share, chosen at its own priority, so
    a river's priority changes which launches it gets but never how many."""
    chosen = []
    for river, share in shares(found, count).items():
        own = [launch for launch in found if launch["river"] == river]
        own.sort(key=lambda launch: (-score(launch, launch["w"]), launch["date"]))
        chosen += own[:share]
    return sorted(chosen, key=lambda launch: (-launch["odds"], launch["date"]))


def row(launch: sg.Launch, widened: bool) -> dict[str, object]:
    """A recommended launch, with its typical categories by name."""
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
    """The launches to recommend to a party, any rivers widened, and any rivers with
    no launch the party is free for."""
    found = sg.subgraph(party, launches())
    chosen = recommend(found.launches, config.RECOMMENDED_LAUNCHES)
    return {
        "launches": [
            row(launch, launch["river"] in found.widened) for launch in chosen
        ],
        "widened": found.widened,
        "unavailable": found.unavailable,
    }
