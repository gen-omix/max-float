import datetime
from itertools import combinations
from math import prod

import pytest

from max_float import config, core
from max_float.graph import party
from max_float.graph import subgraph as sg
from max_float.plan import Application

D = datetime.date(2027, 6, 1)
EVEN = sg.Priority(4, 4, 4)
FLOW = [0, 0, 2, 3, 3, 2, 0]
TEMPERATURE = [0, 2, 3, 3, 2, 0]


def launch(river, day, odds, applications=100, applicants=("A",), **changes):
    return {
        "river": river,
        "code": river[:3].upper(),
        "lottery": river,
        "choices": 4,
        "per_person": 1,
        "date": D + datetime.timedelta(day),
        "odds": odds,
        "applications": applications,
        "trip_days": 3,
        "flow_match": 1.0,
        "temperature_match": 1.0,
        "priority": EVEN,
        "party_priority": EVEN,
        "applicants": list(applicants),
        "flow_years": [3, 3, 3],
        "temperature_years": [2, 2, 2],
    } | changes


def applicant(**changes):
    return party.Applicant(FLOW, TEMPERATURE, [4, 4, 4], {}, [])._replace(**changes)


def stored(**changes):
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    return party.Party(None, {"Salt": None}, {}, [], None, when, when)._replace(
        **changes
    )


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
    assert [each["river"] for each in found] == [None, "Salt"]
    salt = found[1]
    assert salt["recommended"] == pytest.approx(1 - 0.5 * 0.6)
    assert salt["common"] == pytest.approx(1 - 0.9 * 0.8)
    assert salt["random"] == pytest.approx(
        core.at_random([0.1, 0.2, 0.5, 0.4], 2), abs=1e-4
    )


def test_compared_for_all_rivers_combines_each_rivers_odds():
    every = [launch("Salt", day, 0.1 * (day + 1)) for day in range(3)]
    every += [launch("Yampa", day, 0.05 * (day + 1)) for day in range(3)]
    overall, salt, yampa = core.compared([every[2], every[5]], every)
    assert overall["recommended"] == pytest.approx(1 - 0.7 * 0.85)
    assert overall["common"] == pytest.approx(
        1 - (1 - salt["common"]) * (1 - yampa["common"]), abs=1e-4
    )
    assert overall["random"] == pytest.approx(
        1 - (1 - salt["random"]) * (1 - yampa["random"]), abs=1e-4
    )


def test_compared_leaves_out_rivers_with_nothing_recommended():
    every = [launch("Salt", 0, 0.1), launch("Yampa", 0, 0.2)]
    assert [each["river"] for each in core.compared([every[0]], every)] == [
        None,
        "Salt",
    ]


def test_row_names_the_typical_categories_and_who_applies():
    found = core.row(
        launch("Salt", 0, 0.2), Application("Gen", "Salt", D, 2), widened=True
    )
    assert found["flow_typical"] == "normal"
    assert found["temperature_typical"] == "mild"
    assert found["weekday"] == "Tuesday"
    assert found["widened"] is True
    assert found["code"] == "SAL"
    assert (found["applicant"], found["choice"]) == ("Gen", 2)


def test_dates_are_one_rivers_launch_dates_in_order(monkeypatch):
    every = [launch("Salt", 2, 0.1), launch("Yampa", 0, 0.1), launch("Salt", 0, 0.1)]
    monkeypatch.setattr(core, "launches", lambda: every)
    assert core.dates("Salt") == [D, D + datetime.timedelta(2)]


def test_against_counts_other_parties_locked_applications_in_the_odds():
    every = [
        launch("Salt", 0, 0.1, applications=100),
        launch("Salt", 1, 0.1, applications=0),
    ]
    found = core.against(
        every, {("Salt", D): 25, ("Salt", D + datetime.timedelta(1)): 25}
    )
    assert found[0]["odds"] == pytest.approx(0.08)
    assert found[1]["odds"] == 0.1
    assert every[0]["odds"] == 0.1


def test_plan_gives_each_applicant_an_application_with_rows_by_river(monkeypatch):
    every = [launch("Salt", day, 0.3 - day / 100) for day in range(10)]
    every += [launch("Yampa", day, 0.5 - day / 100) for day in range(10)]
    monkeypatch.setattr(core, "launches", lambda: every)
    seen = sg.Party(
        sg.Preferences(sg.votes(FLOW), sg.votes(TEMPERATURE), EVEN),
        {"Salt": sg.Considered(), "Yampa": sg.Considered()},
        1,
        {"Gen": [], "Sam": [D + datetime.timedelta(10)]},
    )
    found = core.plan(seen)
    rows = found["launches"]
    assert len(rows) == 16
    assert [each["river"] for each in rows] == ["Salt"] * 8 + ["Yampa"] * 8
    assert [each["odds"] for each in rows[:8]] == sorted(
        (each["odds"] for each in rows[:8]), reverse=True
    )
    assert {each["applicant"] for each in rows} == {"Gen", "Sam"}
    assert all(
        each["river"] != "Yampa" or each["date"] != D + datetime.timedelta(10)
        for each in rows
        if each["applicant"] == "Sam"
    )
    assert [each["river"] for each in found["odds"]] == [None, "Salt", "Yampa"]


def test_for_group_averages_the_applicants_and_keeps_everyones_days():
    gen = applicant(away=[D])
    sam = applicant(
        flow=[0, 0, 0, 5, 5, 0, 0],
        priority=[12, 0, 0],
        away=[D + datetime.timedelta(1)],
    )
    seen = core.for_group(stored(applicants={"Gen": gen, "Sam": sam}))
    assert seen.preferences.flow == {2: 1, 3: 4, 4: 4, 5: 1}
    assert seen.preferences.priority == sg.Priority(8, 2, 2)
    assert seen.minimum == 2
    assert seen.away == {"Gen": [D], "Sam": [D + datetime.timedelta(1)]}
    assert seen.rivers == {"Salt": sg.Considered()}


def test_for_group_averages_a_rivers_own_preferences_with_the_others_general_ones():
    gen = applicant(rivers={"Salt": party.Own(flow=[0, 0, 0, 0, 0, 10, 0])})
    sam = applicant()
    seen = core.for_group(
        stored(applicants={"Gen": gen, "Sam": sam}, rivers={"Salt": 4})
    )
    assert seen.rivers["Salt"].days == 4
    assert seen.rivers["Salt"].flow == {2: 1, 3: 1.5, 4: 1.5, 5: 6}
    assert seen.rivers["Salt"].temperature is None
    assert seen.rivers["Salt"].priority is None


def test_for_group_minimum_is_the_party_unless_set_lower():
    people = {"Gen": applicant(), "Sam": applicant(), "Ana": applicant()}
    assert core.for_group(stored(applicants=people, minimum=2)).minimum == 2
    assert core.for_group(stored(applicants=people, minimum=5)).minimum == 3


def test_for_group_with_no_one_starts_where_a_new_party_does():
    seen = core.for_group(stored())
    assert seen.preferences.flow == sg.votes(config.START_FLOW)
    assert seen.preferences.priority == sg.Priority(*config.START_PRIORITY)
    assert (seen.minimum, seen.away) == (0, {})


def test_for_applicant_is_that_person_alone():
    gen = applicant(
        flow=[0, 0, 0, 5, 5, 0, 0],
        away=[D],
        rivers={"Salt": party.Own(priority=[12, 0, 0])},
    )
    seen = core.for_applicant(
        stored(applicants={"Gen": gen, "Sam": applicant()}), "Gen"
    )
    assert seen.preferences.flow == {3: 5, 4: 5}
    assert seen.rivers["Salt"].priority == sg.Priority(12, 0, 0)
    assert seen.rivers["Salt"].flow is None
    assert (seen.minimum, seen.away) == (1, {"Gen": [D]})


class Session:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def session(self):
        return self


@pytest.fixture
def graph(monkeypatch):
    every = [launch("Salt", day, 0.3 - day / 100) for day in range(6)]
    monkeypatch.setattr(core, "launches", lambda: every)
    monkeypatch.setattr(core, "connected", Session)
    saved = []
    people = {"Gen": applicant(), "Sam": applicant(away=[D])}
    monkeypatch.setattr(
        party,
        "read",
        lambda s, key: (
            stored(applicants=people) if key == "good-key-for-tests" else None
        ),
    )
    monkeypatch.setattr(party, "applied", lambda s, key: {("Salt", D): 1})
    monkeypatch.setattr(
        party,
        "save_plan",
        lambda s, key, applications: saved.append((key, list(applications))),
    )
    return saved


def test_party_plan_reads_the_party_counts_others_and_saves_the_group_plan(graph):
    found = core.party_plan("good-key-for-tests")
    rows = found["launches"]
    assert len(rows) == 5
    assert {each["applicant"] for each in rows} == {"Gen", "Sam"}
    assert all(each["date"] != D for each in rows)
    key, saved = graph[0]
    assert key == "good-key-for-tests"
    assert sorted(saved) == sorted(
        Application(each["applicant"], "Salt", each["date"], each["choice"])
        for each in rows
    )


def test_party_plan_for_one_applicant_is_theirs_alone_and_is_not_saved(graph):
    found = core.party_plan("good-key-for-tests", "Gen")
    rows = found["launches"]
    assert len(rows) == 4
    assert {each["applicant"] for each in rows} == {"Gen"}
    assert rows[0]["date"] == D
    assert rows[0]["odds"] == pytest.approx(0.297)
    assert graph == []


def test_party_plan_for_an_unknown_key_is_none(graph):
    assert core.party_plan("some-other-key-words") is None


def test_party_view_shows_the_party_with_its_preferences_averaged(graph):
    found = core.party_view("good-key-for-tests")
    assert found["key"] == "good-key-for-tests"
    assert list(found["applicants"]) == ["Gen", "Sam"]
    assert found["applicants"]["Sam"]["away"] == [D]
    assert found["applicants"]["Gen"]["priority"] == {
        "odds": 4,
        "flow": 4,
        "temperature": 4,
    }
    assert found["preferences"]["flow"] == FLOW
    assert found["preferences"]["rivers"] == {
        "Salt": {"flow": None, "temperature": None, "priority": None}
    }
    assert found["locked"] is None
    assert core.party_view("some-other-key-words") is None


def test_create_party_makes_it_then_saves_the_group_and_its_first_applicant(
    monkeypatch,
):
    monkeypatch.setattr(core, "connected", Session)
    calls = []
    monkeypatch.setattr(
        party,
        "create",
        lambda s, ip: calls.append(("create", ip)) or "new-key-of-words",
    )
    monkeypatch.setattr(
        party,
        "save_party",
        lambda s, key, minimum, rivers: calls.append(("party", key, minimum, rivers)),
    )
    monkeypatch.setattr(
        party,
        "save_applicant",
        lambda s, key, name, a: calls.append(("applicant", key, name)),
    )
    key = core.create_party("203.0.113.9", None, {"Salt": 4}, "Gen", applicant())
    assert key == "new-key-of-words"
    assert calls == [
        ("create", "203.0.113.9"),
        ("party", key, None, {"Salt": 4}),
        ("applicant", key, "Gen"),
    ]


def test_lock_plans_afresh_and_locks_that_plan(graph, monkeypatch):
    locked = []
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    monkeypatch.setattr(
        party,
        "lock",
        lambda s, key, applications: locked.append(list(applications)) or when,
    )
    assert core.lock("good-key-for-tests") == when
    assert len(locked[0]) == 5
    assert graph == []
    assert core.lock("some-other-key-words") is None


def test_a_locked_partys_plan_is_its_locked_dates_and_is_not_saved(monkeypatch):
    every = [launch("Salt", day, 0.3 - day / 100) for day in range(6)]
    monkeypatch.setattr(core, "launches", lambda: every)
    monkeypatch.setattr(core, "connected", Session)
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    kept = [party.Application("Gen", "Salt", D + datetime.timedelta(5), 1)]
    frozen = stored(applicants={"Gen": applicant()}, applications=kept, locked=when)
    monkeypatch.setattr(party, "read", lambda s, key: frozen)
    monkeypatch.setattr(party, "applied", lambda s, key: {})
    monkeypatch.setattr(party, "save_plan", lambda *args: pytest.fail("saved"))
    found = core.party_plan("good-key-for-tests")
    assert [each["date"] for each in found["launches"]] == [D + datetime.timedelta(5)]
    assert found["launches"][0]["applicant"] == "Gen"
    assert found["odds"][0]["recommended"] == pytest.approx(0.25)
    own = core.party_plan("good-key-for-tests", "Gen")
    assert len(own["launches"]) == 4
