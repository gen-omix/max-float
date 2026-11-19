import copy
import datetime

import pytest

from max_float import config
from max_float.graph import subgraph as sg

D = datetime.date(2027, 6, 1)
GOOD = sg.Preferences({3: 1, 4: 1}, {2: 1, 3: 1})


def launch(
    flow=(3, 3, 3), temperature=(2, 2, 2), river="Salt", date=D, odds=0.2, choices=1
):
    return {
        "river": river,
        "date": date,
        "odds": odds,
        "choices": choices,
        "trip_days": 3,
        "flow_years": list(flow),
        "temperature_years": list(temperature),
    }


def party(rivers=None, preferences=GOOD, minimum=1, away=None):
    return sg.Party(
        preferences,
        {"Salt": sg.Considered()} if rivers is None else rivers,
        minimum,
        {"A": []} if away is None else away,
    )


def test_typical_takes_the_lower_middle_and_skips_missing_readings():
    assert sg.typical([1, 2, 3, 4]) == 2
    assert sg.typical([1, -1, 5]) == 1
    assert sg.typical([-1, -1]) is None


def test_match_counts_years_with_the_category_voted_for():
    assert sg.match([3, 3, 1], GOOD.flow) == pytest.approx(2 / 3)
    assert sg.match([2, -1, 5], GOOD.temperature) == pytest.approx(1 / 3)


def test_match_weighs_each_year_by_its_categorys_share_over_the_most():
    shares = {2: 1, 3: 4, 4: 2}
    assert sg.match([3, 3, 3], shares) == pytest.approx(1)
    assert sg.match([2, 3, 4, 5], shares) == pytest.approx((1 + 4 + 2 + 0) / 16)


def test_a_category_rated_no_leaves_out_launches_typically_in_it():
    shares = sg.Preferences({2: 3, 4: 1}, {2: 1})
    found = sg.subgraph(party(preferences=shares), [launch(flow=(3, 3, 2))])
    assert found.widened["Salt"]["flow"] == [3]


def test_widened_categories_count_as_ok_beside_ideal():
    shares = sg.Preferences({1: 0.6}, {2: 1})
    found = sg.subgraph(party(preferences=shares), [launch(flow=(2, 2, 1))])
    assert found.widened == {"Salt": {"flow": [2], "temperature": []}}
    assert found.launches[0]["flow_match"] == pytest.approx((1 / 3 + 1 / 3 + 1) / 3)


def test_unchecked_typical_category_leaves_a_launch_out():
    left_out = launch(flow=(1, 1, 3))
    good = launch(date=D + datetime.timedelta(1))
    found = sg.subgraph(party(), [left_out, good])
    assert [row["date"] for row in found.launches] == [good["date"]]
    assert found.widened == {}


def test_kept_launch_has_its_matches_and_priorities():
    own = {"Salt": sg.Considered(priority=sg.Priority(0, 12, 0))}
    found = sg.subgraph(party(own), [launch(flow=(3, 3, 1))]).launches[0]
    assert found["flow_match"] == pytest.approx(2 / 3)
    assert found["temperature_match"] == pytest.approx(1)
    assert found["priority"] == (0, 12, 0)
    assert found["party_priority"] == GOOD.priority
    assert found["applicants"] == ["A"]


def test_river_preferences_replace_the_partys_one_scale_at_a_time():
    rivers = {"Salt": sg.Considered(flow={1: 1})}
    found = sg.subgraph(party(rivers), [launch(flow=(1, 1, 1))]).launches
    assert len(found) == 1
    assert sg.subgraph(party(), [launch(flow=(1, 1, 1))]).widened


def test_a_river_not_considered_is_left_out():
    assert sg.subgraph(party(), [launch(river="Yampa")]).launches == []


def test_a_day_away_in_the_trip_leaves_the_applicant_off_the_launch():
    away = {"A": [D + datetime.timedelta(2)], "B": []}
    assert sg.subgraph(party(away=away), [launch()]).launches[0]["applicants"] == ["B"]
    rivers = {"Salt": sg.Considered(days=2)}
    found = sg.subgraph(party(rivers, away=away), [launch()]).launches[0]
    assert found["applicants"] == ["A", "B"]


def test_minimum_leaves_out_launches_too_few_applicants_are_free_for():
    away = {"A": [D], "B": []}
    assert sg.subgraph(party(away=away, minimum=2), [launch()]).unavailable == ["Salt"]


def test_widen_adds_only_the_nearest_categories_for_the_river():
    far = launch(flow=(0, 0, 0))
    near = launch(flow=(1, 1, 1), date=D + datetime.timedelta(1))
    found = sg.subgraph(party(), [far, near])
    assert found.widened == {"Salt": {"flow": [1, 2], "temperature": []}}
    assert [row["date"] for row in found.launches] == [near["date"]]


def test_widening_counts_the_added_categories_in_the_match():
    found = sg.subgraph(party(), [launch(flow=(1, 1, 3))])
    assert found.launches[0]["flow_match"] == pytest.approx((1 / 3 + 1 / 3 + 1) / 3)


def days(count, **changes):
    return [launch(date=D + datetime.timedelta(day), **changes) for day in range(count)]


def test_a_river_keeping_fewer_launches_than_its_choices_is_widened_to_fill_them():
    good = launch(choices=3)
    near = days(4, flow=(2, 2, 2), choices=3)[1:]
    far = launch(flow=(0, 0, 0), date=D + datetime.timedelta(9), choices=3)
    found = sg.subgraph(party(), [good, *near, far])
    assert found.widened == {"Salt": {"flow": [2], "temperature": []}}
    assert len(found.launches) == 4
    assert far["date"] not in [row["date"] for row in found.launches]


def test_widening_to_fill_adds_further_categories_only_while_short():
    good = launch(choices=3)
    near = launch(flow=(2, 2, 2), date=D + datetime.timedelta(1), choices=3)
    far = launch(flow=(0, 0, 0), date=D + datetime.timedelta(2), choices=3)
    found = sg.subgraph(party(), [good, near, far])
    assert found.widened == {"Salt": {"flow": [0, 1, 2], "temperature": []}}
    assert len(found.launches) == 3


def test_matching_launches_still_match_best_once_widened_to_fill():
    good = launch(choices=2)
    near = launch(flow=(2, 2, 2), date=D + datetime.timedelta(1), choices=2)
    found = {row["date"]: row for row in sg.subgraph(party(), [good, near]).launches}
    assert found[D]["flow_match"] == pytest.approx(1)
    assert found[near["date"]]["flow_match"] == pytest.approx(1 / 3)


def test_a_river_with_enough_launches_for_its_choices_is_not_widened():
    found = sg.subgraph(
        party(), [*days(3, choices=3), launch(flow=(2, 2, 2), choices=3)]
    )
    assert found.widened == {}
    assert len(found.launches) == 3


def test_a_river_short_with_nothing_nearer_keeps_what_it_has_unwidened():
    found = sg.subgraph(party(), days(2, choices=4))
    assert (found.widened, found.unavailable) == ({}, [])
    assert len(found.launches) == 2


def test_a_shared_lottery_river_needs_only_the_choices_given_it():
    rivers = {"Salt": sg.Considered()}
    shared = sg.Party(GOOD, rivers, 1, {"A": []}, caps={"Salt": {"A": 1}})
    found = sg.subgraph(
        shared,
        [
            launch(choices=4),
            launch(flow=(2, 2, 2), date=D + datetime.timedelta(1), choices=4),
        ],
    )
    assert found.widened == {}


def test_a_river_with_no_free_launches_is_not_widened():
    found = sg.subgraph(party(away={"A": [D]}), [launch(flow=(1, 1, 1))])
    assert (found.widened, found.unavailable) == ({}, ["Salt"])


def test_a_river_with_no_launches_at_all_is_unavailable():
    assert sg.subgraph(party(), []).unavailable == ["Salt"]


def test_subgraph_leaves_the_public_launches_as_they_were():
    launches = [launch(), launch(flow=(1, 1, 1), date=D + datetime.timedelta(1))]
    before = copy.deepcopy(launches)
    sg.subgraph(party(), launches)
    assert launches == before


def test_one_partys_subgraph_doesnt_change_anothers():
    launches = [launch(), launch(flow=(1, 1, 1), date=D + datetime.timedelta(1))]
    narrow = sg.subgraph(party(), launches)
    broad = sg.subgraph(
        party(preferences=sg.Preferences({1: 1, 3: 1}, {2: 1})), launches
    )
    assert len(narrow.launches) == 1
    assert len(broad.launches) == 2


class Date:
    def to_native(self):
        return D


class Session:
    def __init__(self):
        self.calls = []

    def run(self, statement, **params):
        self.calls.append((statement, params))
        return [launch() | {"date": Date()}]


def test_for_party_reads_active_launches_and_writes_nothing():
    session = Session()
    found = sg.for_party(session, party())
    assert len(found.launches) == 1
    assert found.launches[0]["date"] == D
    statement, params = session.calls[0]
    assert params == {"rivers": ["Salt"]}
    assert "n.active" in statement
    assert not {"MERGE", "SET", "DELETE", "CREATE", "REMOVE"} & set(statement.split())


def test_a_set_is_rated_once_every_row_is_and_a_scale_has_one_above_no():
    assert sg.rated([0, 3, 1])
    assert not sg.rated([0, None, 1])
    assert not sg.rated(None)
    assert not sg.rated([0, 0, 0])
    assert sg.rated([0, 0, 0], scale=False)


def test_a_rows_share_is_its_rating_over_the_sets_total():
    assert sg.shares([0, 1, 3]) == [0, 0.25, 0.75]
    assert sg.shares([0, 0, 0]) == pytest.approx([1 / 3] * 3)
    assert sg.scale([0, 1, 0, 3]) == {1: 0.25, 3: 0.75}
    assert sg.priority([0, 0, 0]) == pytest.approx(sg.Priority(1 / 3, 1 / 3, 1 / 3))
    assert sg.by_step(None) is None


def test_mean_shares_weigh_each_applicant_the_same_and_drop_what_no_one_rates():
    found = sg.mean_shares([[0, 1, 1, 0], [0, 0, 3, 3]])
    assert found == pytest.approx({1: 0.25, 2: 0.5, 3: 0.25})
    assert sg.mean_shares([[0, 3, 0], [0, 1, 0]]) == {1: 1}


def test_mean_priority_averages_each_parts_share():
    found = sg.mean_priority([[3, 0, 0], [1, 1, 1]])
    assert found == pytest.approx(sg.Priority(2 / 3, 1 / 6, 1 / 6))


def test_only_those_applying_for_a_river_are_its_launches_applicants():
    everyone = {"A": [], "B": [], "C": [D]}
    rivers = {"Salt": sg.Considered(), "Yampa": sg.Considered()}
    seen = sg.Party(GOOD, rivers, 1, everyone, {"Salt": ["A", "C"], "Yampa": []})
    found = sg.subgraph(seen, [launch(), launch(river="Yampa")])
    assert [(each["river"], each["applicants"]) for each in found.launches] == [
        ("Salt", ["A"])
    ]
    assert found.unavailable == ["Yampa"]


def test_the_minimum_counts_a_rivers_applicants_and_no_more_than_it_has():
    everyone = {"A": [], "B": [D], "C": [D]}
    later = launch(date=D + datetime.timedelta(7))

    def dates(minimum, applying):
        seen = sg.Party(GOOD, {"Salt": sg.Considered()}, minimum, everyone, applying)
        return [each["date"] for each in sg.subgraph(seen, [launch(), later]).launches]

    assert dates(1, {"Salt": ["A", "B", "C"]}) == [D, later["date"]]
    assert dates(2, {"Salt": ["A", "B", "C"]}) == [later["date"]]
    assert dates(3, {"Salt": ["A"]}) == [D, later["date"]]
    assert dates(3, {"Salt": ["B", "C"]}) == [later["date"]]


def test_noise_is_fixed_by_the_seed_and_within_its_size():
    def drawn(seed, size=0.2):
        return [
            sg.noise(seed, launch(date=D + datetime.timedelta(day)), size)
            for day in range(50)
        ]

    assert drawn(7) == drawn(7)
    assert drawn(7) != drawn(8)
    assert all(0.8 <= each <= 1.2 for each in drawn(7))
    assert max(drawn(7)) > 1.1
    assert all(0.99 <= each <= 1.01 for each in drawn(7, 0.01))
    assert sg.noise(None, launch(), 0.2) == 1.0


def typical(**changes):
    return sg.Preferences(
        sg.scale(config.TYPICAL_FLOW),
        sg.scale(config.TYPICAL_TEMPERATURE),
        sg.priority(config.TYPICAL_PRIORITY),
    )._replace(**changes)


def test_typical_preferences_get_the_most_noise_and_far_ones_the_least():
    assert sg.unlike(typical()) == pytest.approx(0)
    assert sg.noise_size(typical()) == pytest.approx(config.PLAN_NOISE)
    high = typical(flow=sg.scale([0, 0, 0, 0, 3, 3, 0]))
    assert sg.unlike(high) == pytest.approx(0.5)
    assert sg.noise_size(high) == pytest.approx(0.105)
    odds = typical(priority=sg.priority([3, 0, 0]))
    assert sg.unlike(odds) == pytest.approx(2 / 3)
    far = high._replace(priority=sg.priority([3, 0, 0]))
    assert sg.unlike(far) == 1
    assert sg.noise_size(far) == pytest.approx(config.PLAN_NOISE_LEAST)
    same = typical(flow=sg.scale([0, 0, 2, 3, 3, 2, 0]))
    assert sg.unlike(same) == pytest.approx(0)


def test_a_rivers_launches_get_noise_sized_by_its_own_preferences():
    far = sg.Considered(
        flow=sg.scale([0, 0, 0, 3, 0, 0, 0]), priority=sg.priority([3, 0, 0])
    )
    seen = sg.Party(
        typical(), {"Salt": sg.Considered(), "Yampa": far}, 1, {"A": []}, None, 7
    )
    days = [D + datetime.timedelta(day) for day in range(40)]
    every = [launch(date=day) for day in days] + [
        launch(river="Yampa", date=day) for day in days
    ]
    found = sg.subgraph(seen, every).launches
    salt = [each["noise"] for each in found if each["river"] == "Salt"]
    yampa = [each["noise"] for each in found if each["river"] == "Yampa"]
    assert salt[0] == sg.noise(7, launch(), config.PLAN_NOISE)
    assert max(abs(each - 1) for each in salt) > 0.1
    assert max(abs(each - 1) for each in yampa) <= config.PLAN_NOISE_LEAST
