import datetime
from itertools import combinations
from math import prod

import pytest

from max_float import config, core
from max_float.graph import subgraph as sg

D = datetime.date(2027, 6, 1)
EVEN = sg.Priority(4, 4, 4)
ODDS = sg.Priority(12, 0, 0)
FLOW = sg.Priority(0, 12, 0)


def launch(
    river,
    day,
    odds,
    flow=1.0,
    temperature=1.0,
    priority=EVEN,
    party_priority=EVEN,
    lottery=None,
    choices=4,
    applications=100,
):
    return {
        "river": river,
        "code": river[:3].upper(),
        "lottery": lottery or river,
        "choices": choices,
        "date": D + datetime.timedelta(day),
        "odds": odds,
        "applications": applications,
        "flow_match": flow,
        "temperature_match": temperature,
        "priority": priority,
        "party_priority": party_priority,
        "flow_years": [3, 3, 3],
        "temperature_years": [2, 2, 2],
    }


def days(chosen):
    return [launch["date"].day - D.day for launch in chosen]


def test_score_weighs_each_by_its_share_of_the_slices():
    salt = launch(
        "Salt", 0, 0.2, flow=0.5, temperature=0.8, priority=sg.Priority(6, 6, 0)
    )
    assert core.score(salt) == pytest.approx((0.2 * 0.5) ** 0.5)
    assert core.score(salt, ODDS) == pytest.approx(0.2)
    assert core.score(salt, FLOW) == pytest.approx(0.5)


def test_even_slices_rank_by_odds_times_both_matches():
    found = [
        launch("Salt", 0, 0.4, flow=0.5),
        launch("Salt", 1, 0.3, flow=0.9),
        launch("Salt", 2, 0.5, temperature=0.3),
    ]
    ordered = sorted(found, key=core.best)
    assert days(ordered) == [1, 0, 2]


def test_with_no_slices_on_odds_ties_go_to_the_best_odds():
    found = [
        launch("Salt", 0, 0.1, priority=FLOW),
        launch("Salt", 1, 0.3, priority=FLOW),
    ]
    assert days(sorted(found, key=core.best)) == [1, 0]


def test_recommended_groups_rivers_with_each_rivers_best_first():
    found = [
        launch("Yampa", 0, 0.1),
        launch("Salt", 1, 0.1),
        launch("Salt", 2, 0.3),
        launch("Yampa", 3, 0.5),
    ]
    chosen = core.recommended(found)
    assert [row["river"] for row in chosen] == ["Salt", "Salt", "Yampa", "Yampa"]
    assert days(chosen) == [2, 1, 3, 0]


def test_row_names_the_typical_categories():
    row = core.row(launch("Salt", 0, 0.2), widened=True)
    assert row["flow_typical"] == "normal"
    assert row["temperature_typical"] == "mild"
    assert row["weekday"] == "Tuesday"
    assert row["widened"] is True
    assert row["code"] == "SAL"


def test_a_lottery_recommends_up_to_its_choices():
    found = [launch("Salt", day, 0.5 - day / 100, choices=3) for day in range(6)]
    assert core.shares(found) == {"Salt": 3}
    assert days(core.recommended(found)) == [0, 1, 2]


def test_a_river_with_fewer_launches_recommends_them_all():
    assert core.shares([launch("Salt", 0, 0.5, choices=3)]) == {"Salt": 1}


def test_a_lottery_with_no_stated_choices_uses_the_default():
    found = [launch("Salt", day, 0.5, choices=None) for day in range(9)]
    assert core.shares(found) == {"Salt": config.DEFAULT_CHOICES}


def test_rivers_sharing_a_lottery_share_its_choices():
    found = [
        launch("Yampa", 0, 0.5, lottery=1, choices=2),
        launch("Yampa", 1, 0.4, lottery=1, choices=2),
        launch("Lodore", 2, 0.45, lottery=1, choices=2),
        launch("Lodore", 3, 0.1, lottery=1, choices=2),
    ]
    assert core.shares(found) == {"Yampa": 1, "Lodore": 1}


def test_a_river_priority_changes_its_picks_but_never_any_rivers_count():
    def world(priority):
        return [
            launch("Yampa", 0, 0.5, flow=0.4, priority=priority, lottery=1, choices=2),
            launch("Yampa", 1, 0.25, priority=priority, lottery=1, choices=2),
            launch("Lodore", 2, 0.28, lottery=1, choices=2),
            launch("Lodore", 3, 0.2, lottery=1, choices=2),
        ]

    assert core.shares(world(ODDS)) == core.shares(world(FLOW))
    assert ("Yampa", 0) in {
        (row["river"], days([row])[0]) for row in core.recommended(world(ODDS))
    }
    assert ("Yampa", 1) in {
        (row["river"], days([row])[0]) for row in core.recommended(world(FLOW))
    }


def test_at_random_is_the_mean_over_every_pick():
    odds = [0.1, 0.4, 0.05, 0.3, 0.2]
    every = [
        1 - prod(1 - odds[i] for i in picked) for picked in combinations(range(5), 3)
    ]
    assert core.at_random(odds, 3) == pytest.approx(sum(every) / len(every))


def test_at_random_with_every_launch_is_the_odds_of_them_all():
    assert core.at_random([0.5, 0.5], 2) == pytest.approx(0.75)


def test_compared_takes_the_most_applied_for_launches_as_most_common():
    every = [
        launch("Salt", 0, 0.1, applications=500),
        launch("Salt", 1, 0.2, applications=300),
        launch("Salt", 2, 0.5, applications=50),
        launch("Salt", 3, 0.4, applications=60),
    ]
    found = core.compared([every[2], every[3]], every)
    assert [row["river"] for row in found] == [None, "Salt"]
    salt = found[1]
    assert salt["recommended"] == pytest.approx(1 - 0.5 * 0.6)
    assert salt["common"] == pytest.approx(1 - 0.9 * 0.8)
    assert salt["random"] == pytest.approx(
        core.at_random([0.1, 0.2, 0.5, 0.4], 2), abs=1e-4
    )


def test_compared_for_all_rivers_combines_each_rivers_odds():
    every = [launch("Salt", day, 0.1 * (day + 1)) for day in range(3)]
    every += [launch("Yampa", day, 0.05 * (day + 1)) for day in range(3)]
    chosen = [every[2], every[5]]
    overall, salt, yampa = core.compared(chosen, every)
    assert overall["recommended"] == pytest.approx(1 - 0.7 * 0.85)
    assert overall["common"] == pytest.approx(
        1 - (1 - salt["common"]) * (1 - yampa["common"]), abs=1e-4
    )
    assert overall["random"] == pytest.approx(
        1 - (1 - salt["random"]) * (1 - yampa["random"]), abs=1e-4
    )


def test_compared_leaves_out_rivers_with_nothing_recommended():
    every = [launch("Salt", 0, 0.1), launch("Yampa", 0, 0.2)]
    assert [row["river"] for row in core.compared([every[0]], every)] == [None, "Salt"]
