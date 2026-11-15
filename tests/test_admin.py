import datetime

import pytest

from max_float.graph import admin, party

WHEN = datetime.datetime(2026, 11, 14, 12, tzinfo=datetime.UTC)
ROWS = [
    party.Made("a" * 64, WHEN, None, ["Gen", "Sam"]),
    party.Made(None, WHEN, WHEN, []),
]


class Connection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def session(self):
        return self


@pytest.fixture
def calls(monkeypatch):
    found = []

    def record(name, result):
        def call(session, value):
            found.append((name, value))
            return result

        return call

    monkeypatch.setattr(admin, "driver", Connection)
    monkeypatch.setattr(party, "named", record("named", ROWS))
    monkeypatch.setattr(party, "made_by", record("made_by", ROWS[:1]))
    monkeypatch.setattr(party, "forget_ip", record("forget", 1))
    monkeypatch.setattr(party, "remove_ip", record("remove", 1))
    return found


def test_find_lists_parties_with_their_addresses_hash_and_applicants(calls):
    out = admin.run(["find", "gen"])
    assert calls == [("named", "gen")]
    assert out[0] == f"2026-11-14 12:00  {'a' * 64}  planning   Gen, Sam"
    assert "address forgotten" in out[1]
    assert out[1].endswith("locked in  no applicants")


def test_show_lists_what_an_address_made(calls):
    assert len(admin.run(["show", "203.0.113.9"])) == 1
    assert calls == [("made_by", "203.0.113.9")]


def test_reset_forgets_the_address_and_keeps_its_parties(calls):
    out = admin.run(["reset", "203.0.113.9"])
    assert calls == [("made_by", "203.0.113.9"), ("forget", "203.0.113.9")]
    assert out == ["1 parties kept. The address can make parties again."]


def test_clear_deletes_only_once_confirmed(calls):
    asked = []
    out = admin.run(["clear", "203.0.113.9"], lambda text: asked.append(text) or "n")
    assert out == ["Nothing deleted."]
    assert "Delete these 1? [y/N]" in asked[0]
    assert ("remove", "203.0.113.9") not in calls
    assert admin.run(["clear", "203.0.113.9"], lambda text: "y") == [
        "1 parties deleted."
    ]
    assert calls[-1] == ("remove", "203.0.113.9")


def test_an_address_with_no_parties_changes_nothing(calls, monkeypatch):
    monkeypatch.setattr(party, "made_by", lambda session, address: [])
    assert admin.run(["clear", "203.0.113.9"], pytest.fail) == ["No parties."]
    assert admin.run(["reset", "203.0.113.9"]) == ["No parties."]
    assert calls == []
