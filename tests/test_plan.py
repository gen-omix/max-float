import datetime
import random

import pytest

from max_float import config, plan
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
    per_person=1,
    applicants=("A",),
):
    return {
        "river": river,
        "code": river[:3].upper(),
        "lottery": lottery or river,
        "choices": choices,
        "per_person": per_person,
        "date": D + datetime.timedelta(day),
        "odds": odds,
        "applications": 100,
        "flow_match": flow,
        "temperature_match": temperature,
        "priority": priority,
        "party_priority": party_priority,
        "applicants": list(applicants),
        "flow_years": [3, 3, 3],
        "temperature_years": [2, 2, 2],
    }


def days(applications):
    return [application.date.day - D.day for application in applications]


def test_score_weighs_each_by_its_share_of_the_slices():
    salt = launch(
        "Salt", 0, 0.2, flow=0.5, temperature=0.8, priority=sg.Priority(6, 6, 0)
    )
    assert plan.score(salt) == pytest.approx((0.2 * 0.5) ** 0.5)
    assert plan.score(salt, ODDS) == pytest.approx(0.2)
    assert plan.score(salt, FLOW) == pytest.approx(0.5)


def test_even_slices_rank_by_odds_times_both_matches():
    found = [
        launch("Salt", 0, 0.4, flow=0.5),
        launch("Salt", 1, 0.3, flow=0.9),
        launch("Salt", 2, 0.5, temperature=0.3),
    ]
    assert [each["date"].day - 1 for each in sorted(found, key=plan.best)] == [1, 0, 2]


def test_value_is_odds_times_the_matches_to_their_slices_over_odds():
    salt = launch("Salt", 0, 0.2, flow=0.5, temperature=0.8)
    assert plan.value(salt, EVEN) == pytest.approx(0.2 * 0.5 * 0.8)
    assert plan.value(salt, sg.Priority(2, 4, 6)) == pytest.approx(
        0.2 * 0.5**2 * 0.8**3
    )
    assert plan.value(salt, FLOW) == pytest.approx(0.5)


def test_cost_orders_launches_as_best_does_and_is_never_positive():
    rng = random.Random(3)
    found = [
        launch(
            "Salt",
            day,
            rng.uniform(0.001, 0.4),
            rng.uniform(0.1, 1),
            rng.uniform(0.1, 1),
        )
        for day in range(40)
    ]
    found += [launch("Salt", 40, 0.1, 0.5, 0.5), launch("Salt", 41, 0.1, 0.5, 0.5)]
    for priority in (EVEN, ODDS, FLOW, sg.Priority(2, 5, 5)):
        by_cost = sorted(found, key=lambda each: plan.cost(each, priority, D))
        by_best = sorted(found, key=lambda each: plan.best(each, priority))
        assert [each["date"] for each in by_cost] == [each["date"] for each in by_best]
        assert all(plan.cost(each, priority, D) <= 0 for each in found)


def test_one_applicant_gets_a_lotterys_choices_numbered_best_first():
    found = [launch("Salt", day, 0.5 - day / 100, choices=3) for day in range(6)]
    chosen = plan.solve(found)
    assert days(chosen) == [0, 1, 2]
    assert [each.choice for each in chosen] == [1, 2, 3]
    assert {each.applicant for each in chosen} == {"A"}


def test_a_river_with_fewer_launches_gets_them_all():
    assert len(plan.solve([launch("Salt", 0, 0.5, choices=3)])) == 1


def test_a_lottery_with_no_stated_choices_uses_the_default():
    found = [launch("Salt", day, 0.5, choices=None) for day in range(9)]
    assert len(plan.solve(found)) == config.DEFAULT_CHOICES


def test_rivers_sharing_a_lottery_share_its_choices():
    found = [
        launch("Yampa", 0, 0.5, lottery=1, choices=2),
        launch("Yampa", 1, 0.4, lottery=1, choices=2),
        launch("Lodore", 2, 0.45, lottery=1, choices=2),
        launch("Lodore", 3, 0.1, lottery=1, choices=2),
    ]
    chosen = plan.solve(found)
    assert sorted((each.river, each.date.day - 1) for each in chosen) == [
        ("Lodore", 2),
        ("Yampa", 0),
    ]


def test_a_river_priority_changes_its_picks_but_never_any_rivers_count():
    def world(priority):
        return [
            launch("Yampa", 0, 0.5, flow=0.4, priority=priority, lottery=1, choices=2),
            launch("Yampa", 1, 0.25, priority=priority, lottery=1, choices=2),
            launch("Lodore", 2, 0.28, lottery=1, choices=2),
            launch("Lodore", 3, 0.2, lottery=1, choices=2),
        ]

    at_odds = {(each.river, each.date.day - 1) for each in plan.solve(world(ODDS))}
    at_flow = {(each.river, each.date.day - 1) for each in plan.solve(world(FLOW))}
    assert ("Yampa", 0) in at_odds
    assert ("Yampa", 1) in at_flow
    assert len(at_odds) == len(at_flow) == 2


def test_each_applicant_gets_their_own_application_and_no_launch_twice():
    found = [
        launch("Salt", day, 0.3 - day / 100, choices=3, applicants=("A", "B"))
        for day in range(10)
    ]
    chosen = plan.solve(found)
    assert len(chosen) == 6
    assert len({each.date for each in chosen}) == 6
    assert sorted(days(chosen)) == [0, 1, 2, 3, 4, 5]
    by_applicant = {
        name: [each for each in chosen if each.applicant == name] for name in "AB"
    }
    assert [len(by_applicant[name]) for name in "AB"] == [3, 3]
    assert [each.choice for each in by_applicant["A"]] == [1, 2, 3]


def test_an_applicant_holds_only_launches_they_are_free_for():
    both = [
        launch("Salt", day, 0.1, choices=3, applicants=("A", "B")) for day in range(3)
    ]
    only_a = [
        launch("Salt", day, 0.5, choices=3, applicants=("A",)) for day in range(3, 6)
    ]
    chosen = plan.solve(both + only_a)
    assert sorted(days(each for each in chosen if each.applicant == "B")) == [0, 1, 2]
    assert sorted(days(each for each in chosen if each.applicant == "A")) == [3, 4, 5]


def test_applications_per_person_multiply_what_an_applicant_holds():
    found = [launch("Rio Chama", day, 0.2, choices=2, per_person=2) for day in range(6)]
    assert len(plan.solve(found)) == 4


def test_no_launches_or_no_one_free_gives_no_plan():
    assert plan.solve([]) == []
    assert plan.solve([launch("Salt", 0, 0.5, applicants=())]) == []
