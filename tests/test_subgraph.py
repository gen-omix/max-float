import copy
import datetime

import pytest

from max_float.graph import subgraph as sg

D = datetime.date(2027, 6, 1)
GOOD = sg.Preferences(frozenset({3, 4}), frozenset({2, 3}))


def launch(flow=(3, 3, 3), temperature=(2, 2, 2), river="Salt", date=D, odds=0.2):
    return {
        "river": river,
        "date": date,
        "odds": odds,
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


def test_match_counts_years_with_the_category_checked():
    assert sg.match([3, 3, 1], GOOD.flow) == pytest.approx(2 / 3)
    assert sg.match([2, -1, 5], GOOD.temperature) == pytest.approx(1 / 3)


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
    rivers = {"Salt": sg.Considered(flow=frozenset({1}))}
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
    assert found.launches[0]["flow_match"] == pytest.approx(1)


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
        party(preferences=sg.Preferences(frozenset({1, 3}), frozenset({2}))), launches
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
