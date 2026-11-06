import datetime

from max_float import config, core

D = datetime.date(2027, 6, 1)


def launch(river, day, odds, m=1.0, w=1.0, party_w=1.0, lottery=None, choices=4):
    return {
        "river": river,
        "code": river[:3].upper(),
        "lottery": lottery or river,
        "choices": choices,
        "date": D + datetime.timedelta(day),
        "odds": odds,
        "m": m,
        "w": w,
        "party_w": party_w,
        "flow_years": [3, 3, 3],
        "temperature_years": [2, 2, 2],
    }


def days(chosen):
    return [launch["date"].day - D.day for launch in chosen]


def test_score_is_odds_times_m_to_the_w():
    assert core.score(launch("Salt", 0, 0.2, m=0.5, w=2)) == 0.05


def test_ranked_keeps_every_launch_of_every_river():
    found = [launch("Salt", day, 0.1) for day in range(40)]
    found += [launch("Yampa", day, 0.2) for day in range(40)]
    assert len(core.ranked(found)) == 80


def test_ranked_groups_rivers_with_each_rivers_best_first():
    found = [
        launch("Yampa", 0, 0.1),
        launch("Salt", 1, 0.1),
        launch("Salt", 2, 0.3),
        launch("Yampa", 3, 0.5),
    ]
    chosen = core.ranked(found)
    assert [row["river"] for row in chosen] == ["Salt", "Salt", "Yampa", "Yampa"]
    assert days(chosen) == [2, 1, 3, 0]


def test_a_rivers_priority_only_changes_its_own_order():
    def world(w):
        return [
            launch("Salt", 0, 0.5, m=0.6, w=w),
            launch("Salt", 1, 0.25, m=1.0, w=w),
            launch("Yampa", 2, 0.28),
            launch("Yampa", 3, 0.2),
        ]

    middle, conditions = core.ranked(world(1.0)), core.ranked(world(4.0))
    assert days(middle) == [0, 1, 2, 3]
    assert days(conditions) == [1, 0, 2, 3]


def test_row_names_the_typical_categories():
    row = core.row(launch("Salt", 0, 0.2, m=0.5), widened=True, chosen=True)
    assert row["flow_typical"] == "normal"
    assert row["temperature_typical"] == "mild"
    assert row["weekday"] == "Tuesday"
    assert row["m"] == 0.5
    assert row["widened"] is True
    assert row["recommended"] is True
    assert row["code"] == "SAL"


def test_a_lottery_recommends_up_to_its_choices():
    found = [launch("Salt", day, 0.5 - day / 100, choices=3) for day in range(6)]
    assert core.shares(found) == {"Salt": 3}
    assert sorted(day for _, day in core.recommended(found)) == [
        D + datetime.timedelta(day) for day in range(3)
    ]


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
    def world(w):
        return [
            launch("Yampa", 0, 0.5, m=0.6, w=w, lottery=1, choices=2),
            launch("Yampa", 1, 0.25, w=w, lottery=1, choices=2),
            launch("Lodore", 2, 0.28, lottery=1, choices=2),
            launch("Lodore", 3, 0.2, lottery=1, choices=2),
        ]

    assert core.shares(world(1.0)) == core.shares(world(4.0))
    assert ("Yampa", D) in core.recommended(world(1.0))
    assert ("Yampa", D + datetime.timedelta(1)) in core.recommended(world(4.0))
