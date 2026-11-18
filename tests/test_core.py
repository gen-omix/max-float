import datetime
from collections import Counter
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
        "flow_years": [3, 3, -1],
        "temperature_years": [2, 2, 2],
        "flow_cfs_years": [1500.0, 1800.0, float("nan")],
        "high_f_years": [71.5, 74.0, 78.2],
        "low_f_years": [40.0, 44.0, 39.0],
    } | changes


def applicant(**changes):
    return party.Applicant(
        FLOW, TEMPERATURE, [2, 2, 2], {"Salt": party.Own()}, []
    )._replace(**changes)


def stored(**changes):
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    return party.Party(None, {}, {}, [], None, when, when, 7)._replace(**changes)


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


def test_compared_says_how_many_recommended_are_among_the_most_common():
    every = [
        launch("Salt", 0, 0.1, applications=500),
        launch("Salt", 1, 0.2, applications=300),
        launch("Salt", 2, 0.5, applications=50),
        launch("Yampa", 0, 0.1, applications=400),
        launch("Yampa", 1, 0.3, applications=40),
    ]
    overall, salt, yampa = core.compared([every[0], every[2], every[4]], every)
    assert (salt["launches"], salt["in_common"]) == (2, 1)
    assert (yampa["launches"], yampa["in_common"]) == (1, 0)
    assert (overall["launches"], overall["in_common"]) == (3, 1)


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
        launch("Salt", 0, 0.2), Application("Gen", "Salt", D, 2), 1, widened=True
    )
    assert found["odds"] == found["party_odds"] == 0.2
    assert found["flow_typical"] == "normal"
    assert found["temperature_typical"] == "mild"
    assert found["weekday"] == "Tuesday"
    assert found["widened"] is True
    assert found["code"] == "SAL"
    assert (found["applicant"], found["choice"]) == ("Gen", 2)


def test_rows_share_a_launchs_odds_among_the_partys_applications_for_it():
    salt = launch("Salt", 0, 0.2, applications=10)
    applications = [Application(name, "Salt", D, 1) for name in ("Gen", "Sam", "Ada")]
    found = core.rows(applications, {("Salt", D): salt}, {})
    assert [each["applicant"] for each in found] == ["Gen", "Sam", "Ada"]
    assert [each["odds"] for each in found] == [pytest.approx(1 / 6, abs=1e-4)] * 3
    assert found[0]["party_odds"] == pytest.approx(
        1 - (1 - 0.2 * 10 / 12) ** 3, abs=1e-4
    )


def test_compared_counts_every_application_for_a_launch():
    every = [launch("Salt", day, 0.2, applications=10 + day) for day in range(4)]
    stacked = core.compared([every[0]] * 3, every)[1]
    assert stacked["recommended"] == pytest.approx(
        1 - (1 - 0.2 * 10 / 12) ** 3, abs=1e-4
    )
    assert stacked["common"] == pytest.approx(1 - (1 - 0.2 * 13 / 15) ** 3, abs=1e-4)
    assert stacked["recommended"] > core.compared([every[0]], every)[1]["recommended"]


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
    assert found[0]["applications"] == 125
    assert found[1]["odds"] == 0.1
    assert (every[0]["odds"], every[0]["applications"]) == (0.1, 100)


def test_plan_gives_each_applicant_an_application_with_rows_by_river(monkeypatch):
    every = [launch("Salt", day, 0.3 - day / 100) for day in range(10)]
    every += [launch("Yampa", day, 0.5 - day / 100) for day in range(10)]
    monkeypatch.setattr(core, "launches", lambda: every)
    seen = sg.Party(
        sg.Preferences(sg.scale(FLOW), sg.scale(TEMPERATURE), EVEN),
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


def test_for_team_averages_the_applicants_shares_and_keeps_everyones_days():
    gen = applicant(away=[D])
    sam = applicant(
        flow=[0, 0, 0, 3, 3, 0, 0],
        priority=[3, 0, 0],
        away=[D + datetime.timedelta(1)],
    )
    seen = core.for_team(stored(applicants={"Gen": gen, "Sam": sam}))
    assert seen.preferences.flow == pytest.approx({2: 0.1, 3: 0.4, 4: 0.4, 5: 0.1})
    assert seen.preferences.priority == pytest.approx(sg.Priority(2 / 3, 1 / 6, 1 / 6))
    assert seen.minimum == 1
    assert seen.away == {"Gen": [D], "Sam": [D + datetime.timedelta(1)]}
    assert seen.rivers == {"Salt": sg.Considered()}
    assert seen.applying == {"Salt": ["Gen", "Sam"]}
    assert seen.seed == 7


def test_for_team_has_the_rivers_its_applicants_apply_for_and_who_does():
    people = {
        "Gen": applicant(rivers={"Yampa": party.Own(), "Salt": party.Own()}),
        "Sam": applicant(rivers={"Salt": party.Own()}),
        "Ana": applicant(rivers={}),
    }
    seen = core.for_team(stored(applicants=people, rivers={"Salt": 4, "Selway": 5}))
    assert seen.rivers == {"Salt": sg.Considered(4), "Yampa": sg.Considered()}
    assert seen.applying == {"Salt": ["Gen", "Sam"], "Yampa": ["Gen"]}
    assert core.for_team(stored(applicants={"Ana": applicant(rivers={})})).rivers == {}


def test_history_is_each_years_readings(monkeypatch):
    monkeypatch.setattr(config, "FLOW_YEARS", range(2023, 2026))
    found = core.history(launch("Salt", 0, 0.2))
    assert found[2] == {
        "year": 2025,
        "flow_cfs": None,
        "flow": None,
        "high_f": 78.2,
        "low_f": 39.0,
        "temperature": "mild",
    }
    assert (found[0]["year"], found[0]["flow_cfs"], found[0]["flow"]) == (
        2023,
        1500.0,
        "normal",
    )


def test_a_party_made_before_seeds_is_given_one_for_its_plan(graph, monkeypatch):
    old = stored(applicants={"Gen": applicant()}, seed=None)
    monkeypatch.setattr(party, "read", lambda s, key: old)
    asked = []
    monkeypatch.setattr(party, "seeded", lambda s, key: asked.append(key) or 11)
    assert core.seeded(None, "good-key-for-tests", old).seed == 11
    assert core.seeded(None, "good-key-for-tests", stored()).seed == 7
    core.party_plan("good-key-for-tests")
    assert asked == ["good-key-for-tests"] * 2


def test_for_team_averages_a_rivers_own_preferences_with_the_others_general_ones():
    gen = applicant(rivers={"Salt": party.Own(flow=[0, 0, 0, 0, 0, 3, 0])})
    sam = applicant()
    seen = core.for_team(
        stored(applicants={"Gen": gen, "Sam": sam}, rivers={"Salt": 4})
    )
    assert seen.rivers["Salt"].days == 4
    assert seen.rivers["Salt"].flow == pytest.approx({2: 0.1, 3: 0.15, 4: 0.15, 5: 0.6})
    assert seen.rivers["Salt"].temperature is None
    assert seen.rivers["Salt"].priority is None


def test_for_team_minimum_is_one_unless_set_higher():
    people = {"Gen": applicant(), "Sam": applicant(), "Ana": applicant()}
    assert core.for_team(stored(applicants=people)).minimum == 1
    assert core.for_team(stored(applicants=people, minimum=2)).minimum == 2


def test_for_team_with_no_one_rated_plans_with_the_typical_preferences():
    seen = core.for_team(stored())
    assert seen.preferences.flow == sg.scale(config.TYPICAL_FLOW)
    assert seen.preferences.priority == sg.priority(config.TYPICAL_PRIORITY)
    assert (seen.minimum, seen.away) == (1, {})
    blank = applicant(flow=[None] * 7, priority=[3, 0, 0])
    unrated = core.for_team(stored(applicants={"Gen": blank}))
    assert unrated.preferences == seen.preferences
    assert unrated.applying == {"Salt": ["Gen"]}


def test_only_applicants_who_rated_every_row_count_in_the_teams_preferences():
    people = {
        "Gen": applicant(priority=[3, 0, 0]),
        "Sam": applicant(priority=[None, 0, 0]),
        "Kit": applicant(flow=[0] * 7),
    }
    seen = core.for_team(stored(applicants=people))
    assert seen.preferences.priority == pytest.approx(sg.Priority(1, 0, 0))
    assert [core.rated(person) for person in people.values()] == [True, False, False]


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
    monkeypatch.setattr(party, "locked_parties", lambda s, key: {"Salt": 2})
    monkeypatch.setattr(party, "locked_launches", lambda s, key: {})
    monkeypatch.setattr(
        party,
        "save_plan",
        lambda s, key, applications: saved.append((key, list(applications))),
    )
    return saved


def test_party_plan_reads_the_party_counts_others_and_saves_the_team_plan(graph):
    found = core.party_plan("good-key-for-tests")
    rows = found["launches"]
    assert len(rows) == 8
    assert {each["applicant"] for each in rows} == {"Gen", "Sam"}
    held = Counter(each["date"] for each in rows)
    assert sum(1 for count in held.values() if count == 2) >= 3
    assert all(each["date"] != D for each in rows if each["applicant"] == "Sam")
    assert Counter(each["applicant"] for each in rows) == {"Gen": 4, "Sam": 4}
    assert {each["lottery"] for each in rows} == {"Salt"}
    key, saved = graph[0]
    assert key == "good-key-for-tests"
    assert sorted(saved) == sorted(
        Application(each["applicant"], "Salt", each["date"], each["choice"])
        for each in rows
    )


def test_party_plan_for_one_applicant_is_their_launches_in_the_teams_plan(graph):
    team = core.party_plan("good-key-for-tests")
    found = core.party_plan("good-key-for-tests", "Gen")
    rows = found["launches"]
    assert rows == [each for each in team["launches"] if each["applicant"] == "Gen"]
    assert len(rows) == 4
    assert found["odds"][0]["launches"] == 4
    assert found["odds"][0]["recommended"] < team["odds"][0]["recommended"]
    assert len(graph) == 2
    with pytest.raises(KeyError):
        core.party_plan("good-key-for-tests", "Who")


def test_the_party_view_says_who_is_done(graph, monkeypatch):
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    done = stored(applicants={"Gen": applicant(done=when), "Sam": applicant()})
    monkeypatch.setattr(party, "read", lambda s, key: done)
    found = core.party_view("good-key-for-tests")
    assert found["applicants"]["Gen"]["done"] == when
    assert found["applicants"]["Sam"]["done"] is None


def test_party_plan_for_an_unknown_key_is_none(graph):
    assert core.party_plan("some-other-key-words") is None


def test_party_view_shows_the_party_with_its_preferences_averaged(graph):
    found = core.party_view("good-key-for-tests")
    assert found["key"] == "good-key-for-tests"
    assert list(found["applicants"]) == ["Gen", "Sam"]
    assert found["applicants"]["Sam"]["away"] == [D]
    assert found["applicants"]["Gen"]["priority"] == {
        "odds": 2,
        "flow": 2,
        "temperature": 2,
    }
    assert found["applicants"]["Gen"]["rated"] is True
    assert found["applicants"]["Gen"]["rivers"]["Salt"]["slots"] is None
    assert found["preferences"]["flow"] == [0, 0, 0.2, 0.3, 0.3, 0.2, 0]
    assert found["preferences"]["rivers"] == {
        "Salt": {"flow": None, "temperature": None, "priority": None}
    }
    assert found["locked"] is None
    assert core.party_view("some-other-key-words") is None


def test_party_view_has_no_team_preferences_until_someone_rates_them(
    graph, monkeypatch
):
    blank = stored(applicants={"Gen": applicant(temperature=[None] * 6)})
    monkeypatch.setattr(party, "read", lambda s, key: blank)
    found = core.party_view("good-key-for-tests")
    assert found["preferences"] is None
    assert found["applicants"]["Gen"]["rated"] is False
    assert found["applicants"]["Gen"]["temperature"] == [None] * 6


def test_create_party_makes_it_then_saves_the_team_and_its_first_applicant(
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
    done = {"Gen": applicant(done=when), "Sam": applicant(away=[D], done=when)}
    monkeypatch.setattr(party, "read", lambda s, key: stored(applicants=done))
    assert core.lock("good-key-for-tests") == when
    assert len(locked[0]) == 8
    assert graph == []
    monkeypatch.setattr(party, "read", lambda s, key: None)
    assert core.lock("some-other-key-words") is None
    nobody = stored(applicants={"Gen": applicant(rivers={}, done=when)})
    monkeypatch.setattr(party, "read", lambda s, key: nobody)
    with pytest.raises(core.NothingToLock):
        core.lock("good-key-for-tests")
    assert len(locked) == 1


def test_lock_waits_until_everyone_is_done(graph, monkeypatch):
    monkeypatch.setattr(party, "lock", lambda *_: pytest.fail("locked"))
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    people = {"Gen": applicant(done=when), "Sam": applicant(), "Kit": applicant()}
    monkeypatch.setattr(party, "read", lambda s, key: stored(applicants=people))
    with pytest.raises(core.NotDone) as waiting:
        core.lock("good-key-for-tests")
    assert waiting.value.args[0] == ["Sam", "Kit"]


def test_the_party_view_counts_other_parties_locked_in_by_river(graph):
    assert core.party_view("good-key-for-tests")["locked_parties"] == {"Salt": 2}


def test_a_locked_partys_plan_is_its_locked_dates_and_is_not_saved(monkeypatch):
    every = [launch("Salt", day, 0.3 - day / 100) for day in range(6)]
    monkeypatch.setattr(core, "launches", lambda: every)
    monkeypatch.setattr(core, "connected", Session)
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    kept = [party.Application("Gen", "Salt", D + datetime.timedelta(5), 1)]
    frozen = stored(applicants={"Gen": applicant()}, applications=kept, locked=when)
    monkeypatch.setattr(party, "read", lambda s, key: frozen)
    monkeypatch.setattr(party, "applied", lambda s, key: {})
    monkeypatch.setattr(party, "locked_launches", lambda s, key: {})
    monkeypatch.setattr(party, "save_plan", lambda *args: pytest.fail("saved"))
    found = core.party_plan("good-key-for-tests")
    assert core.party_plan("good-key-for-tests", "Gen") == found
    assert [each["date"] for each in found["launches"]] == [D + datetime.timedelta(5)]
    assert found["launches"][0]["applicant"] == "Gen"
    assert found["odds"][0]["recommended"] == pytest.approx(0.25)


def test_remove_applicant_only_while_the_party_is_unlocked(monkeypatch):
    monkeypatch.setattr(core, "connected", Session)
    removed = []
    monkeypatch.setattr(
        party, "remove_applicant", lambda s, key, name: removed.append(name) or True
    )
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    found = {
        "good-key-for-tests": stored(),
        "locked-key-for-tests": stored(locked=when),
    }
    monkeypatch.setattr(party, "read", lambda s, key: found.get(key))
    assert core.remove_applicant("good-key-for-tests", "Gen") is True
    assert core.remove_applicant("some-other-key-words", "Gen") is False
    with pytest.raises(core.Locked):
        core.remove_applicant("locked-key-for-tests", "Gen")
    assert removed == ["Gen"]


def test_mark_done_needs_rivers_and_an_unlocked_party(graph, monkeypatch):
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    marked = []

    def done(s, key, name):
        marked.append(name)
        return when

    monkeypatch.setattr(party, "done", done)
    people = {"Gen": applicant(rivers={}), "Sam": applicant()}
    found = {
        "good-key-for-tests": stored(applicants=people),
        "locked-key-for-tests": stored(applicants=people, locked=when),
    }
    monkeypatch.setattr(party, "read", lambda s, key: found.get(key))
    with pytest.raises(core.NoRivers):
        core.mark_done("good-key-for-tests", "Gen")
    assert core.mark_done("good-key-for-tests", "Sam") == when
    assert marked == ["Sam"]
    with pytest.raises(KeyError):
        core.mark_done("good-key-for-tests", "Who")
    with pytest.raises(core.Locked):
        core.mark_done("locked-key-for-tests", "Sam")
    assert core.mark_done("some-other-key-words", "Sam") is None
    monkeypatch.setattr(party, "done", lambda s, key, name: None)
    with pytest.raises(core.Locked):
        core.mark_done("good-key-for-tests", "Sam")


def test_planning_marks_no_one_done(graph, monkeypatch):
    monkeypatch.setattr(party, "done", lambda *_: pytest.fail("marked done"))
    nobody = stored(applicants={"Gen": applicant(rivers={}), "Sam": applicant()})
    monkeypatch.setattr(party, "read", lambda s, key: nobody)
    assert core.party_plan("good-key-for-tests", "Gen")["launches"] == []
    assert core.party_plan("good-key-for-tests", "Sam")["launches"]


def test_planning_needs_ratings_and_says_who_else_locked_in(graph, monkeypatch):
    people = {"Gen": applicant(), "Sam": applicant(flow=[None] * 7)}
    monkeypatch.setattr(party, "read", lambda s, key: stored(applicants=people))
    monkeypatch.setattr(party, "locked_launches", lambda s, key: {("Salt", D): 2})
    with pytest.raises(core.NotRated):
        core.party_plan("good-key-for-tests", "Sam")
    found = core.party_plan("good-key-for-tests")
    assert {each["applicant"] for each in found["launches"]} == {"Gen", "Sam"}
    assert {
        each["locked_parties"] for each in found["launches"] if each["date"] == D
    } == {2}
    assert {
        each["locked_parties"] for each in found["launches"] if each["date"] != D
    } == {0}
    nobody = {"Sam": applicant(flow=[None] * 7)}
    monkeypatch.setattr(party, "read", lambda s, key: stored(applicants=nobody))
    with pytest.raises(core.NotRated):
        core.party_plan("good-key-for-tests")


def test_rivers_sharing_a_lottery_need_each_choice_given_to_one_of_them():
    both = {"Yampa": party.Own(slots=[0, 1]), "Green - Gates of Lodore": party.Own()}
    assert core.shared(both) == [["Green - Gates of Lodore", "Yampa"]]
    assert core.shared({"Salt": None, "Yampa": None}) == []
    gen = applicant(rivers=both)
    assert not core.split(gen)
    assert core.split(applicant())
    done = {
        "Yampa": party.Own(slots=[0, 3, 1]),
        "Green - Gates of Lodore": party.Own(slots=[2]),
    }
    assert core.split(applicant(rivers=done))
    twice = done | {"Green - Gates of Lodore": party.Own(slots=[1, 2])}
    assert not core.split(applicant(rivers=twice))
    people = {"Gen": applicant(rivers=done), "Sam": gen}
    assert core.caps(stored(applicants=people)) == {
        "Yampa": {"Gen": 3},
        "Green - Gates of Lodore": {"Gen": 1},
    }


def test_mark_done_needs_each_shared_choice_given_to_a_river(graph, monkeypatch):
    when = datetime.datetime(2026, 11, 14, tzinfo=datetime.UTC)
    monkeypatch.setattr(party, "done", lambda s, key, name: when)
    both = {"Yampa": party.Own(slots=[0, 1]), "Green - Gates of Lodore": party.Own()}
    people = {"Gen": applicant(rivers=both)}
    monkeypatch.setattr(party, "read", lambda s, key: stored(applicants=people))
    with pytest.raises(core.NotSplit):
        core.mark_done("good-key-for-tests", "Gen")
