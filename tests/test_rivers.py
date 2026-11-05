from datetime import date

from max_float.ingest import rivers

FACILITY = {
    "FacilityID": "250014",
    "FacilityName": "Dinosaur Green And Yampa River Permits ",
    "FacilityLatitude": 40.725,
    "FacilityLongitude": -108.89,
    "ORGANIZATION": [{"OrgName": "National Park Service"}],
}


def entrance(name, zone, latitude, longitude):
    return {
        "PermitEntranceName": name,
        "ZONES": [{"Zone": zone}] if zone else [],
        "Latitude": latitude,
        "Longitude": longitude,
    }


ENTRANCES = [
    entrance("Deerlodge Park, Yampa River", "Yampa River", 40.446, -108.512),
    entrance("Gates of Lodore, Green River", "Green River", 40.728, -108.888),
]


def test_point_is_the_rivers_entrance():
    assert rivers.point("Yampa", FACILITY, ENTRANCES) == (40.446, -108.512)
    assert rivers.point("Green - Gates of Lodore", FACILITY, ENTRANCES) == (
        40.728,
        -108.888,
    )


def test_point_skips_unlocated_entrances():
    entrances = [entrance("Yampa", "Yampa River", 0, 0)]
    assert rivers.point("Yampa", FACILITY, entrances) == (40.725, -108.89)


def test_permit():
    assert rivers.permit("Yampa", FACILITY, []) == {
        "river": "Yampa",
        "ridb_id": "250014",
        "ridb_name": "Dinosaur Green And Yampa River Permits",
        "agency": "National Park Service",
        "section": "Deerlodge Park to Split Mountain",
        "latitude": 40.725,
        "longitude": -108.89,
    }


def test_lottery():
    assert rivers.lottery("Salt", 2027) == {
        "year": 2027,
        "applications_open": date(2026, 12, 1),
        "application_deadline": date(2027, 1, 31),
        "season_start": date(2027, 3, 1),
        "season_end": date(2027, 5, 15),
    }


def test_category():
    assert rivers.category("Salt", 199) == 0
    assert rivers.category("Salt", 200) == 1
    assert rivers.category("Salt", 999) == 2
    assert rivers.category("Salt", 10_000) == 6


def test_flow_ranges_and_shares_of_season_days():
    flows = {
        date(2025, 3, 1): 150.0,
        date(2025, 3, 2): 1_500.0,
        date(2025, 3, 3): 1_600.0,
        date(2025, 3, 4): 12_000.0,
        date(2025, 6, 1): 150.0,
    }
    row = rivers.flow("Salt", "SALT RIVER NEAR CHRYSOTILE, AZ", flows)
    assert row["gauge_id"] == "09497500"
    assert row["gauge_name"] == "SALT RIVER NEAR CHRYSOTILE, AZ"
    assert row["not_running_cfs"] == "0-200"
    assert row["normal_cfs"] == "1000-3000"
    assert row["extra_spicy_high_cfs"] == "10000+"
    assert row["not_running_share"] == 0.25
    assert row["normal_share"] == 0.5
    assert row["extra_spicy_high_share"] == 0.25
    assert row["low_share"] == 0


def test_columns_are_written():
    assert set(rivers.COLUMNS) >= {"section", "gauge_name", "spicy_high_share"}
