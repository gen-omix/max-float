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
