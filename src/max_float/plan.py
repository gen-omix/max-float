"""The plan: which applicant applies for which launch, as a min-cost flow over the
party's subgraph.

    source → application → launch → place → river → sink

An application is one applicant in one lottery, and holds as many launches as the
lottery allows. A launch has a place for each applicant free for it, so the whole
party can apply for the same launch. Its first place costs what one application is
worth, and each place after costs what one more adds, which is never more: the
party's own applications share the launch's permits. Every cost is zero or less, so
the cheapest maximum flow fills every application with the launches worth most at
the priority, together where that's worth most. It's solved twice: first at the party's priority, which
sets how many launches each river gets, then at each river's own priority with
that share fixed, so a river's priority changes which launches it gets, never how
many. Nothing here is stored.
"""

import datetime
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from math import log
from typing import NamedTuple

import networkx as nx

from max_float import config
from max_float.graph import subgraph as sg

SOURCE, SINK = "source", "sink"

# Costs are integers for the solver: the log of one less the launch's value, to a
# trillionth, then its odds to a thousandth and its day of the season, so that ties
# break the way `best` sorts. Values under a trillionth, which a lopsided priority
# can give, tie on the first and are told apart by odds.
SCALE = 10**12
TIES = 1_000
NEARLY_ONE = 1 - 1e-9


class Application(NamedTuple):
    """One of a party's applications: who applies for which launch, as which
    choice on their application."""

    applicant: str
    river: str
    date: datetime.date
    choice: int


def score(launch: sg.Launch, priority: sg.Priority | None = None) -> float:
    """A launch's score at a priority, by default its river's: its odds, flow match
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


def diluted(launch: sg.Launch, held: int = 1) -> float:
    """The odds of one of a party's `held` applications for a launch. The launch's
    odds are for one application among those expected, and each further one of the
    party's joins them: p · applications / (applications + held − 1). A launch
    with no expected applications keeps its odds."""
    applications = launch.get("applications")
    if held < 2 or not applications:
        return launch["odds"]
    return launch["odds"] * applications / (applications + held - 1)


def won(launch: sg.Launch, held: int = 1) -> float:
    """The party's odds of winning a launch with `held` applications for it."""
    return 1 - (1 - diluted(launch, held)) ** held


def value(launch: sg.Launch, priority: sg.Priority, held: int = 1) -> float:
    """What a launch is worth in the plan at a priority with `held` of the party's
    applications: p·f^a·t^b, with p the party's odds of winning it and a and b
    flow's and temperature's slices over odds', so that 1 − ∏(1 − value) over a
    plan is its chance of at least one permit in matching conditions at 4 slices
    each. With one application it ranks launches as `best` does. With no slices on
    odds each application is worth the score, and odds only break ties. The
    party's noise for the launch multiplies what each application is worth."""
    odds, flow, temperature = priority
    noise = launch.get("noise", 1.0)
    if odds == 0:
        return 1 - (1 - min(1.0, score(launch, priority) * noise)) ** held
    return (
        (1 - (1 - min(1.0, diluted(launch, held) * noise)) ** held)
        * launch["flow_match"] ** (flow / odds)
        * launch["temperature_match"] ** (temperature / odds)
    )


def costs(
    launch: sg.Launch, priority: sg.Priority, first: datetime.date, places: int
) -> list[int]:
    """The cost of each of a launch's places in turn: what one more application
    takes off log(1 − value), scaled to a whole number, with odds and then the date
    breaking ties. Zero or less, and never less than the place before."""
    odds = round(launch["odds"] * (TIES - 1))
    date = max(0, TIES - 1 - (launch["date"] - first).days)
    out, before, least = [], 0.0, None
    for held in range(1, places + 1):
        worth = max(before, min(value(launch, priority, held), NEARLY_ONE))
        adds = round((log(1 - before) - log(1 - worth)) * SCALE)
        least = adds if least is None else min(least, adds)
        out.append(-((least * TIES + odds) * TIES + date))
        before = worth
    return out


def cost(launch: sg.Launch, priority: sg.Priority, first: datetime.date) -> int:
    """The cost of a launch's first place."""
    return costs(launch, priority, first, 1)[0]


def network(
    launches: list[sg.Launch],
    priority_of: Callable[[sg.Launch], sg.Priority],
    shares: Mapping[str, int] | None = None,
) -> nx.DiGraph:
    """The flow network for these launches, costed at `priority_of` each. Each
    river's edge to the sink takes its share, or everything with no shares."""
    graph = nx.DiGraph()
    graph.add_nodes_from([SOURCE, SINK])
    first = min(launch["date"] for launch in launches)
    everything = sum(len(launch["applicants"]) for launch in launches)
    for index, launch in enumerate(launches):
        node = ("launch", index)
        river = ("river", launch["river"])
        if not graph.has_edge(river, SINK):
            share = everything if shares is None else shares.get(launch["river"], 0)
            graph.add_edge(river, SINK, capacity=share, weight=0)
        places = costs(launch, priority_of(launch), first, len(launch["applicants"]))
        for held, weight in enumerate(places, 1):
            place = ("place", index, held)
            graph.add_edge(node, place, capacity=1, weight=weight)
            graph.add_edge(place, river, capacity=1, weight=0)
        choices = launch["choices"] or config.DEFAULT_CHOICES
        holds = choices * (launch.get("per_person") or 1)
        for applicant in launch["applicants"]:
            application = ("application", applicant, launch["lottery"])
            if not graph.has_edge(SOURCE, application):
                graph.add_edge(SOURCE, application, capacity=holds, weight=0)
            graph.add_edge(application, node, capacity=1, weight=0)
    return graph


def chosen(graph: nx.DiGraph) -> list[tuple[str, int]]:
    """The (applicant, launch index) pairs the cheapest maximum flow uses."""
    flow = nx.max_flow_min_cost(graph, SOURCE, SINK)
    return [
        (node[1], target[1])
        for node, edges in flow.items()
        if isinstance(node, tuple) and node[0] == "application"
        for target, amount in edges.items()
        if amount
    ]


def lottery_plan(launches: list[sg.Launch]) -> list[Application]:
    """The plan for one lottery's launches: solved at the party's priority for each
    river's share, then at each river's own priority with that share fixed."""
    first = chosen(network(launches, lambda launch: launch["party_priority"]))
    shares = Counter(launches[index]["river"] for _, index in first)
    second = chosen(network(launches, lambda launch: launch["priority"], shares))
    held: dict[str, list[sg.Launch]] = defaultdict(list)
    for applicant, index in second:
        held[applicant].append(launches[index])
    out = []
    for applicant, found in held.items():
        ordered = sorted(
            found, key=lambda launch: best(launch, launch["party_priority"])
        )
        out += [
            Application(applicant, launch["river"], launch["date"], choice)
            for choice, launch in enumerate(ordered, 1)
        ]
    return out


def solve(launches: list[sg.Launch]) -> list[Application]:
    """The plan over a party's subgraph: each applicant's launches in each lottery,
    numbered best first at the party's priority. Nothing joins one lottery's
    network to another's, so each is solved on its own."""
    by_lottery: dict[object, list[sg.Launch]] = defaultdict(list)
    for launch in launches:
        by_lottery[launch["lottery"]].append(launch)
    out = [
        application
        for found in by_lottery.values()
        for application in lottery_plan(found)
    ]
    return sorted(
        out,
        key=lambda application: (
            application.applicant,
            application.river,
            application.choice,
        ),
    )
