import datetime

import pytest
from fastapi.testclient import TestClient

from max_float import config, core, service
from max_float.graph import subgraph as sg

D = datetime.date(2027, 6, 1)


def launch(day=0, flow=(3, 3, 3), river="Salt"):
    return {
        "river": river,
        "code": "SLT",
        "lottery": 1,
        "choices": 3,
        "date": D + datetime.timedelta(day),
        "odds": 0.2,
        "applications": 50,
        "trip_days": 3,
        "flow_years": list(flow),
        "temperature_years": [2, 2, 2],
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        core,
        "rivers",
        lambda: [
            {
                "name": "Salt",
                "code": "SLT",
                "max_trip_days": 3,
                "flow_starts": [200, 400, 1000, 3000, 5500, 10000],
                "season_start": datetime.date(2027, 3, 1),
                "season_end": datetime.date(2027, 5, 15),
            }
        ],
    )
    monkeypatch.setattr(core, "launches", lambda: [launch(), launch(1)])
    return TestClient(service.app)


def flow(**votes):
    """Flow votes by step, e.g. flow(s3=2)."""
    counts = [0] * len(config.FLOW_CATEGORIES)
    for name, count in votes.items():
        counts[int(name[1:])] = count
    return counts


def temperature(**votes):
    counts = [0] * len(config.TEMPERATURE_CATEGORIES)
    for name, count in votes.items():
        counts[int(name[1:])] = count
    return counts


def body(**changes):
    return {
        "flow": flow(s3=1),
        "temperature": temperature(s2=1),
        "priority": {"odds": 4, "flow": 4, "temperature": 4},
        "rivers": {"Salt": {}},
        "away": [],
    } | changes


def test_page_is_served_at_the_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<h1>max-float</h1>" in response.text


def test_rivers_gives_the_scales_and_where_preferences_start(client):
    found = client.get("/api/rivers").json()
    assert found["rivers"][0]["season_start"] == "2027-03-01"
    assert found["flow"] == list(config.FLOW_CATEGORIES)
    assert found["temperature"] == list(config.TEMPERATURE_CATEGORIES)
    assert found["preferences"]["flow"] == list(config.START_FLOW)
    assert found["votes"] == config.VOTES
    assert found["temperature_starts"] == list(config.TEMPERATURE_STARTS)
    assert found["rivers"][0]["flow_starts"][0] == 200
    assert found["preferences"]["priority"] == {"odds": 4, "flow": 4, "temperature": 4}


def test_plan_lists_only_the_launches_to_apply_for(client, monkeypatch):
    many = [launch(day) for day in range(20)]
    monkeypatch.setattr(core, "launches", lambda: many)
    found = client.post("/api/plan", json=body()).json()["launches"]
    assert len(found) == 3
    assert found[0]["flow_typical"] == "normal"
    assert found[0]["code"] == "SLT"


def test_plan_compares_the_odds_for_all_rivers_then_each(client):
    found = client.post("/api/plan", json=body()).json()["odds"]
    assert [row["river"] for row in found] == [None, "Salt"]
    assert found[0]["recommended"] == pytest.approx(0.36)
    assert found[0]["common"] == found[0]["random"] == pytest.approx(0.36)


def test_the_page_gets_each_rivers_launch_dates(client):
    river = client.get("/api/rivers").json()["rivers"][0]
    assert river["launches"] == ["2027-06-01", "2027-06-02"]


def test_the_page_gets_each_rivers_code(client):
    assert client.get("/api/rivers").json()["rivers"][0]["code"] == "SLT"


def test_days_away_remove_the_launches_they_touch(client):
    away = {"away": ["2027-06-01"]}
    found = client.post("/api/plan", json=body(**away)).json()
    assert [row["date"] for row in found["launches"]] == ["2027-06-02"]


def test_a_rivers_own_priority_is_used(client, monkeypatch):
    better = launch(1) | {"flow_years": [3, 3, 1], "odds": 0.3}
    monkeypatch.setattr(core, "launches", lambda: [launch(), better, launch(2)])
    slices = {"odds": 0, "flow": 12, "temperature": 0}
    own = {"rivers": {"Salt": {"priority": slices}}}
    dates = [
        row["date"]
        for row in client.post("/api/plan", json=body(**own)).json()["launches"]
    ]
    assert dates == ["2027-06-01", "2027-06-03", "2027-06-02"]


def test_a_rivers_own_days_are_used_for_days_away(client):
    away = {"away": ["2027-06-03"], "rivers": {"Salt": {"days": 1}}}
    assert len(client.post("/api/plan", json=body(**away)).json()["launches"]) == 2
    away["rivers"] = {"Salt": {}}
    assert client.post("/api/plan", json=body(**away)).json()["unavailable"] == ["Salt"]


def test_a_rivers_own_categories_replace_the_partys(client):
    own = {"rivers": {"Salt": {"flow": flow(s1=1)}}}
    found = client.post("/api/plan", json=body(**own)).json()
    assert found["widened"]["Salt"]["flow"] == [2, 3]


def test_a_river_with_no_matching_launch_is_widened_and_marked(client):
    found = client.post("/api/plan", json=body(flow=flow(s1=1))).json()
    assert found["widened"] == {"Salt": {"flow": [2, 3], "temperature": []}}
    assert found["launches"][0]["widened"] is True


@pytest.mark.parametrize(
    "changes",
    [
        {"flow": flow()},
        {"flow": [1]},
        {"flow": flow(s2=6, s3=5)},
        {"flow": flow(s2=-1, s3=2)},
        {"temperature": [0, 0, 1, 0, 0, 0, 0]},
        {"priority": {"odds": 4, "flow": 4, "temperature": 5}},
        {"priority": {"odds": -1, "flow": 9, "temperature": 4}},
        {"priority": 5},
        {"rivers": {"Salt": {"days": 0}}},
        {"rivers": {"Salt": {"flow": flow()}}},
        {"away": ["not a date"]},
    ],
)
def test_bad_requests_are_refused(client, changes):
    assert client.post("/api/plan", json=body(**changes)).status_code == 422


def test_core_plan_uses_the_cached_launches(monkeypatch):
    monkeypatch.setattr(core, "launches", lambda: [launch()])
    party = sg.Party(
        sg.Preferences({3: 1}, {2: 1}),
        {"Salt": sg.Considered()},
        1,
        {"applicant": []},
    )
    assert len(core.plan(party)["launches"]) == 1
