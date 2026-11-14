"""The plan: which applicant applies for which launch, as a min-cost flow over the
party's subgraph.

    source → application → launch → river → sink

An application is one applicant in one lottery, and holds as many launches as the
lottery allows. A launch takes one application from the party. Every cost is zero
or less, so the cheapest maximum flow fills every application with the launches
worth most at the priority. It's solved twice: first at the party's priority, which
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


def value(launch: sg.Launch, priority: sg.Priority) -> float:
    """What a launch is worth in the plan at a priority: p·f^a·t^b, with a and b
    flow's and temperature's slices over odds', so that 1 − ∏(1 − value) over a
    plan is its chance of at least one permit in matching conditions at 4 slices
    each. It ranks launches as `best` does. With no slices on odds it's the score,
    and odds only break ties."""
    odds, flow, temperature = priority
    if odds == 0:
        return score(launch, priority)
    return (
        launch["odds"]
        * launch["flow_match"] ** (flow / odds)
        * launch["temperature_match"] ** (temperature / odds)
    )


def cost(launch: sg.Launch, priority: sg.Priority, first: datetime.date) -> int:
    """A launch's cost on its edge: log(1 − value), scaled to a whole number, with
    odds and then the date breaking ties. Zero or less."""
    worth = min(value(launch, priority), NEARLY_ONE)
    primary = round(-log(1 - worth) * SCALE)
    odds = round(launch["odds"] * (TIES - 1))
    date = max(0, TIES - 1 - (launch["date"] - first).days)
    return -((primary * TIES + odds) * TIES + date)


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
    for index, launch in enumerate(launches):
        node = ("launch", index)
        river = ("river", launch["river"])
        graph.add_edge(node, river, capacity=1, weight=0)
        if not graph.has_edge(river, SINK):
            share = len(launches) if shares is None else shares.get(launch["river"], 0)
            graph.add_edge(river, SINK, capacity=share, weight=0)
        weight = cost(launch, priority_of(launch), first)
        choices = launch["choices"] or config.DEFAULT_CHOICES
        holds = choices * (launch.get("per_person") or 1)
        for applicant in launch["applicants"]:
            application = ("application", applicant, launch["lottery"])
            if not graph.has_edge(SOURCE, application):
                graph.add_edge(SOURCE, application, capacity=holds, weight=0)
            graph.add_edge(application, node, capacity=1, weight=weight)
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
