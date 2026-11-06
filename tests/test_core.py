import datetime

from max_float import core

D = datetime.date(2027, 6, 1)


def launch(river, day, odds, m=1.0, w=1.0, party_w=1.0, lottery=None, choices=None):
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


def dates(chosen):
    return [launch["date"].day - D.day for launch in chosen]


def test_score_is_odds_times_m_to_the_w():
    assert core.score(launch("Salt", 0, 0.2, m=0.5, w=2), 2) == 0.05


def test_with_no_limits_it_picks_the_best_launches_by_odds_first():
    found = [launch("Salt", day, odds) for day, odds in enumerate([0.1, 0.3, 0.2])]
    assert dates(core.recommend(found, 2)) == [1, 2]


def test_a_lottery_stops_at_its_choices_per_application():
    found = [
        launch("Salt", day, 0.5 - day / 100, choices=3, lottery=1) for day in range(5)
    ] + [launch("Yampa", 9, 0.01, lottery=2)]
    assert core.shares(found, 4) == {"Salt": 3, "Yampa": 1}


def test_rivers_sharing_a_lottery_share_its_choices():
    found = [
        launch("Yampa", 0, 0.5, lottery=1, choices=1),
        launch("Lodore", 0, 0.4, lottery=1, choices=1),
    ]
    assert core.shares(found, 2) == {"Yampa": 1}


def test_a_river_priority_changes_its_launches_but_never_its_share():
    def world(w):
        return [
            launch("Salt", 0, 0.5, m=0.6, w=w),
            launch("Salt", 1, 0.25, m=1.0, w=w),
            launch("Yampa", 2, 0.28),
            launch("Yampa", 3, 0.2),
        ]

    middle = core.recommend(world(1.0), 2)
    conditions = core.recommend(world(4.0), 2)
    assert core.shares(world(1.0), 2) == core.shares(world(4.0), 2)
    assert {row["river"] for row in middle} == {"Salt", "Yampa"}
    assert {row["river"] for row in conditions} == {"Salt", "Yampa"}
    assert dates(row for row in middle if row["river"] == "Salt") == [0]
    assert dates(row for row in conditions if row["river"] == "Salt") == [1]


def test_the_partys_priority_can_change_the_shares():
    def world(w):
        return [
            launch("Salt", 0, 0.5, m=0.2, w=w, party_w=w),
            launch("Yampa", 1, 0.3, m=1.0, w=w, party_w=w),
        ]

    assert core.shares(world(0.25), 1) == {"Salt": 1}
    assert core.shares(world(4.0), 1) == {"Yampa": 1}


def test_row_names_the_typical_categories():
    row = core.row(launch("Salt", 0, 0.2), widened=True)
    assert row["flow_typical"] == "normal"
    assert row["temperature_typical"] == "mild"
    assert row["weekday"] == "Tuesday"
    assert row["widened"] is True
