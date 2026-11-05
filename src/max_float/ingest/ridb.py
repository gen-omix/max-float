"""Read the Recreation.gov RIDB API and describe the shape of its records."""

import json
import os
import urllib.parse
import urllib.request

BASE_URL = "https://ridb.recreation.gov/api/v1"

RIVERS = {
    "Middle Fork Salmon": 234623,
    "Main Salmon": 234622,
    "Selway": 234624,
    "Snake - Hells Canyon": 234625,
    "Rogue": 251982,
    "Green - Gates of Lodore": 250014,
    "Yampa": 250014,
    "San Juan": 250986,
    "Green - Desolation/Gray": 233393,
    "Rio Chama": 621743,
    "Salt": 249275,
}


def get(path: str, **params: object) -> dict:
    """GET an RIDB path with the key from RIDB_API_KEY."""
    key = os.environ.get("RIDB_API_KEY")
    if not key:
        raise RuntimeError("Set RIDB_API_KEY to your Recreation.gov RIDB API key.")
    url = f"{BASE_URL}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"apikey": key, "accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def schema(value: object) -> object:
    """The type of each field in a JSON value, merged across list items."""
    if isinstance(value, dict):
        return {key: schema(item) for key, item in value.items()}
    if isinstance(value, list):
        merged: object = None
        for item in value:
            merged = merge(merged, schema(item))
        return [merged] if merged is not None else []
    return type(value).__name__


def merge(a: object, b: object) -> object:
    """Combine two schemas so every field seen in either is kept."""
    if a is None or a == "NoneType":
        return b
    if b is None or b == "NoneType":
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {key: merge(a.get(key), b.get(key)) for key in a | b}
    if isinstance(a, list) and isinstance(b, list):
        item = merge(a[0] if a else None, b[0] if b else None)
        return [item] if item is not None else []
    if isinstance(a, str) and isinstance(b, str):
        return " | ".join(sorted(set(a.split(" | ")) | set(b.split(" | "))))
    return merge(str(a), str(b))


def river_schema(rivers: dict[str, int] = RIVERS) -> dict[str, object]:
    """Schema of each river's RIDB permit facility, its entrances and rec areas."""
    found: dict[str, object] = {}
    for facility_id in sorted(set(rivers.values())):
        facility = get(f"facilities/{facility_id}", full="true")
        records = {
            "facilities/{id}": [facility],
            "facilities/{id}/permitentrances": get(
                f"facilities/{facility_id}/permitentrances", full="true", limit=50
            )["RECDATA"],
            "recareas/{id}": [
                get(f"recareas/{area['RecAreaID']}", full="true")
                for area in facility.get("RECAREA", [])
            ],
        }
        for path, values in records.items():
            found[path] = merge(found.get(path), schema(values))
    return found


if __name__ == "__main__":
    print(json.dumps(river_schema(), indent=2, sort_keys=True))
