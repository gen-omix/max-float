import pytest

from max_float import config
from max_float.ingest import ridb


def test_schema_of_scalars():
    assert ridb.schema({"FacilityID": "234623", "Reservable": True}) == {
        "FacilityID": "str",
        "Reservable": "bool",
    }


def test_schema_merges_list_items():
    records = [{"Latitude": 0}, {"Latitude": 45.1, "Town": "Stanley"}]
    assert ridb.schema(records) == [{"Latitude": "float | int", "Town": "str"}]


def test_union_lists_each_type_once():
    records = [{"Latitude": value} for value in (0, 45.1, 1, 44.2)]
    assert ridb.schema(records) == [{"Latitude": "float | int"}]


def test_null_takes_the_other_type():
    assert ridb.schema([{"Zone": None}, {"Zone": "A"}]) == [{"Zone": "str"}]


def test_empty_list():
    assert ridb.schema({"ZONES": []}) == {"ZONES": []}
    assert ridb.merge([], []) == []


def test_get_needs_key(monkeypatch):
    monkeypatch.delenv("RIDB_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        ridb.get("facilities")


def test_river_names_are_ascii():
    assert all(river.isascii() for river in config.RIVERS)
