import datetime
from types import SimpleNamespace

import pytest

from max_float import config
from max_float.graph import party

D = datetime.date(2027, 6, 1)
KEY = "otter-canyon-cobble-ferry"
STATEMENTS = {
    value
    for name, value in vars(party).items()
    if name.isupper() and isinstance(value, str) and " " in value
}


class Result:
    def __init__(self, records, updates=True):
        self.records = records
        self.updates = updates

    def single(self):
        return self.records[0] if self.records else None

    def consume(self):
        return SimpleNamespace(counters=SimpleNamespace(contains_updates=self.updates))

    def __iter__(self):
        return iter(self.records)


class Session:
    """Records every statement with its parameters, and answers each from
    `answers`, keyed by statement. `updates` is whether writes find a party."""

    def __init__(self, answers=None, updates=True):
        self.calls = []
        self.answers = answers or {}
        self.updates = updates

    def run(self, statement, **params):
        self.calls.append((statement, params))
        return Result(self.answers.get(statement, []), self.updates)

    def execute_write(self, work):
        return work(self)

    def params(self, statement):
        return next(params for found, params in self.calls if found == statement)

    def ran(self):
        return [statement for statement, _ in self.calls]


class Date:
    def __init__(self, date):
        self.date = date

    def to_native(self):
        return self.date


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv(party.SECRET, "a server secret")


def applicant(**changes):
    return party.Applicant(
        [0, 0, 2, 3, 3, 2, 0], [0, 2, 3, 3, 2, 0], [4, 4, 4], {}, []
    )._replace(**changes)


def test_hashes_are_fixed_for_one_secret_and_differ_between_secrets(monkeypatch):
    first = party.hashed(KEY)
    assert first == party.hashed(KEY)
    assert first != party.hashed("otter-canyon-cobble-fern")
    assert len(first) == 64
    monkeypatch.setenv(party.SECRET, "another")
    assert party.hashed(KEY) != first


def test_a_missing_secret_is_an_error(monkeypatch):
    monkeypatch.delenv(party.SECRET)
    monkeypatch.setattr(config, "NEO4J_CREDENTIALS", None)
    with pytest.raises(RuntimeError):
        party.hashed(KEY)


def test_the_words_are_the_eff_words_without_the_hyphenated_four():
    found = party.words()
    assert len(found) == 7776 - 4
    assert len(set(found)) == len(found)
    assert all(word.isalpha() and word.islower() for word in found)
    assert "t-shirt" not in found


def test_a_new_key_is_four_words_from_the_list():
    key = party.new_key()
    parts = key.split("-")
    assert len(parts) == config.KEY_WORDS
    assert set(parts) <= set(party.words())
    assert party.is_key(key)


@pytest.mark.parametrize(
    "text",
    ["api", "otter-canyon-cobble", "Otter-canyon-cobble-ferry", "a-b-c-d/e", "a-b-c-"],
)
def test_other_paths_are_not_keys(text):
    assert not party.is_key(text)


def test_create_counts_the_weeks_parties_then_makes_one():
    session = Session({party.NEW_PARTIES: [{"n": 2}]})
    key = party.create(session, "203.0.113.9")
    assert session.ran() == [party.FORGET_IPS, party.NEW_PARTIES, party.CREATE]
    made = session.params(party.CREATE)
    assert made["key"] == party.hashed(key)
    assert made["ip"] == party.hashed("203.0.113.9")
    assert 0 <= made["seed"] < 2**31
    assert "203.0.113.9" not in str(session.calls)
    counted = session.params(party.NEW_PARTIES)
    week = made["now"] - counted["since"]
    assert week == datetime.timedelta(days=config.IP_HASH_DAYS)
    assert session.params(party.FORGET_IPS)["since"] == counted["since"]


def test_create_refuses_an_ip_at_its_limit():
    session = Session({party.NEW_PARTIES: [{"n": config.NEW_PARTIES_PER_WEEK}]})
    with pytest.raises(party.TooManyParties):
        party.create(session, "203.0.113.9")
    assert party.CREATE not in session.ran()


def test_seeded_gives_a_party_a_seed_only_if_it_has_none():
    session = Session({party.SEED: [{"seed": 42}]})
    assert party.seeded(session, KEY) == 42
    assert 0 <= session.params(party.SEED)["seed"] < 2**31
    assert "coalesce(p.seed, $seed)" in party.SEED
    assert party.seeded(Session(), KEY) is None


def test_done_marks_an_applicant_until_their_next_save():
    when = datetime.datetime(2026, 11, 17, tzinfo=datetime.UTC)
    session = Session({party.DONE: [{"done": Date(when)}]})
    assert party.done(session, KEY, "Gen") == when
    sent = session.params(party.DONE)
    assert (sent["key"], sent["name"]) == (party.hashed(KEY), "Gen")
    assert "p.locked IS NULL" in party.DONE
    assert "a.done = null" in party.SAVE_APPLICANT
    assert party.done(Session(), KEY, "Gen") is None


def test_read_gives_none_for_an_unknown_key():
    assert party.read(Session(), KEY) is None


def test_read_builds_the_party_from_the_graph():
    when = datetime.datetime(2026, 11, 14, 12, tzinfo=datetime.UTC)
    none = {"river": None, "flow": None, "temperature": None, "priority": None}
    salt = {
        "river": "Salt",
        "flow": [1, 0, 0, 0, 0, 0, 0],
        "temperature": None,
        "priority": None,
    }
    session = Session(
        {
            party.READ_PARTY: [
                {
                    "minimum": None,
                    "locked": None,
                    "created": Date(when),
                    "edited": Date(when),
                    "seed": 42,
                    "rivers": [
                        {"river": "Salt", "days": 4},
                        {"river": "Yampa", "days": None},
                    ],
                }
            ],
            party.READ_APPLICANTS: [
                {
                    "name": "Gen",
                    "done": Date(when),
                    "flow": [0, 0, 2, 3, 3, 2, 0],
                    "temperature": [0, 2, 3, 3, 2, 0],
                    "priority": [4, 4, 4],
                    "rivers": [none],
                    "away": [Date(D + datetime.timedelta(1)), Date(D)],
                },
                {
                    "name": "Sam",
                    "done": None,
                    "flow": [0, 0, 0, 5, 5, 0, 0],
                    "temperature": [0, 0, 5, 5, 0, 0],
                    "priority": [12, 0, 0],
                    "rivers": [salt],
                    "away": [],
                },
            ],
            party.READ_APPLICATIONS: [
                {"applicant": "Gen", "river": "Salt", "date": Date(D), "choice": 1},
            ],
        }
    )
    found = party.read(session, KEY)
    assert found.minimum is None
    assert found.rivers == {"Salt": 4, "Yampa": None}
    assert list(found.applicants) == ["Gen", "Sam"]
    assert found.applicants["Gen"].away == [D, D + datetime.timedelta(1)]
    assert found.applicants["Gen"].rivers == {}
    assert found.applicants["Gen"].done == when
    assert found.applicants["Sam"].done is None
    assert found.applicants["Sam"].rivers == {
        "Salt": party.Own([1, 0, 0, 0, 0, 0, 0], None, None)
    }
    assert found.applications == [party.Application("Gen", "Salt", D, 1)]
    assert found.locked is None
    assert found.created == when
    assert found.seed == 42
    for _, params in session.calls:
        assert params["key"] == party.hashed(KEY)


def test_save_party_replaces_the_minimum_and_rivers():
    session = Session()
    assert party.save_party(session, KEY, 2, {"Salt": 4, "Yampa": None})
    params = session.params(party.SAVE_PARTY)
    assert params["minimum"] == 2
    assert params["rivers"] == [
        {"river": "Salt", "days": 4},
        {"river": "Yampa", "days": None},
    ]


def test_save_applicant_writes_their_votes_rivers_and_days():
    session = Session()
    own = {"Salt": party.Own(flow=[1, 0, 0, 0, 0, 0, 0])}
    gen = applicant(rivers=own, away=[D, D + datetime.timedelta(5)])
    assert party.save_applicant(session, KEY, "Gen", gen)
    assert session.ran() == [party.SAVE_APPLICANT, party.SAVE_PREFERS, party.SAVE_AWAY]
    saved = session.params(party.SAVE_APPLICANT)
    assert saved["name"] == "Gen"
    assert saved["flow"] == [0, 0, 2, 3, 3, 2, 0]
    assert session.params(party.SAVE_PREFERS)["rivers"] == [
        {
            "river": "Salt",
            "flow": [1, 0, 0, 0, 0, 0, 0],
            "temperature": None,
            "priority": None,
        }
    ]
    assert session.params(party.SAVE_AWAY)["days"] == [
        {"date": D, "weekday": "Tuesday"},
        {"date": D + datetime.timedelta(5), "weekday": "Sunday"},
    ]


def test_remove_applicant():
    session = Session()
    assert party.remove_applicant(session, KEY, "Gen")
    assert session.params(party.REMOVE_APPLICANT)["name"] == "Gen"
    assert "WHERE p.locked IS NULL" in party.REMOVE_APPLICANT


def test_saves_to_a_key_that_opens_no_party_say_so():
    session = Session(updates=False)
    assert party.save_party(session, KEY, None, {}) is False
    assert party.save_applicant(session, KEY, "Gen", applicant()) is False
    assert party.remove_applicant(session, KEY, "Gen") is False
    assert party.unlock(session, KEY) is False


def test_save_plan_replaces_unlocked_applications():
    session = Session({party.UNLOCKED: [{"n": 1}]})
    plan = [
        party.Application("Gen", "Salt", D, 1),
        party.Application("Sam", "Salt", D + datetime.timedelta(1), 1),
    ]
    assert party.save_plan(session, KEY, plan) is True
    assert session.ran() == [
        party.UNLOCKED,
        party.CLEAR_APPLICATIONS,
        party.SAVE_APPLICATIONS,
    ]
    saved = session.params(party.SAVE_APPLICATIONS)
    assert saved["applied"] is False
    assert saved["rows"][1] == {
        "applicant": "Sam",
        "river": "Salt",
        "date": D + datetime.timedelta(1),
        "choice": 1,
    }


def test_save_plan_leaves_locked_applications_alone():
    session = Session({party.UNLOCKED: [{"n": 0}]})
    assert party.save_plan(session, KEY, []) is False
    assert session.ran() == [party.UNLOCKED]


def test_lock_writes_the_plan_as_applied_and_says_when():
    session = Session()
    when = party.lock(session, KEY, [party.Application("Gen", "Salt", D, 1)])
    assert session.ran() == [
        party.CLEAR_APPLICATIONS,
        party.SAVE_APPLICATIONS,
        party.LOCK,
    ]
    assert session.params(party.SAVE_APPLICATIONS)["applied"] is True
    assert session.params(party.LOCK)["now"] == when
    assert when.tzinfo is datetime.UTC


def test_unlock():
    session = Session()
    assert party.unlock(session, KEY)
    assert session.ran() == [party.UNLOCK]


def test_applied_counts_other_parties_locked_applications():
    session = Session({party.APPLIED: [{"river": "Salt", "date": Date(D), "n": 3}]})
    assert party.applied(session, KEY) == {("Salt", D): 3}
    assert session.params(party.APPLIED)["key"] == party.hashed(KEY)
    party.applied(session)
    assert session.calls[-1][1]["key"] == ""


def test_every_statement_run_is_a_fixed_one_and_never_carries_a_key():
    session = Session({party.NEW_PARTIES: [{"n": 0}], party.UNLOCKED: [{"n": 1}]})
    key = party.create(session, "203.0.113.9")
    party.read(session, key)
    party.save_party(session, key, None, {"Salt": None})
    party.save_applicant(session, key, "Gen", applicant())
    party.save_plan(session, key, [party.Application("Gen", "Salt", D, 1)])
    party.lock(session, key, [])
    party.unlock(session, key)
    party.remove_applicant(session, key, "Gen")
    party.applied(session, key)
    party.locked_parties(session, key)
    party.seeded(session, key)
    party.done(session, key, "Gen")
    for statement, params in session.calls:
        assert statement in STATEMENTS
        assert key not in statement
        assert key not in str(params)


def test_an_address_is_hashed_unless_it_already_is():
    assert party.ip_hash("203.0.113.9") == party.hashed("203.0.113.9")
    assert party.ip_hash(party.hashed("203.0.113.9")) == party.hashed("203.0.113.9")


def test_named_finds_parties_by_an_applicants_name_and_never_their_keys():
    when = datetime.datetime(2026, 11, 14, 12, tzinfo=datetime.UTC)
    rows = [
        {"ip": "a" * 64, "created": Date(when), "locked": None, "applicants": ["Gen"]},
        {"ip": None, "created": Date(when), "locked": Date(when), "applicants": []},
    ]
    session = Session({party.NAMED: rows})
    found = party.named(session, "gen")
    assert found == [
        party.Made("a" * 64, when, None, ["Gen"]),
        party.Made(None, when, when, []),
    ]
    assert session.params(party.NAMED) == {"name": "gen"}
    assert "toLower(a.name) CONTAINS toLower($name)" in party.NAMED
    assert "key_hash" not in party.NAMED


def test_made_by_forget_and_remove_take_an_address_as_its_hash():
    session = Session(
        {party.FORGET_IP: [{"n": 2}], party.REMOVE_IP: [{"n": 3}], party.MADE_BY: []}
    )
    assert party.made_by(session, "203.0.113.9") == []
    assert party.forget_ip(session, "203.0.113.9") == 2
    assert party.remove_ip(session, party.hashed("203.0.113.9")) == 3
    assert session.ran() == [party.MADE_BY, party.FORGET_IP, party.REMOVE_IP]
    for _, params in session.calls:
        assert params == {"ip": party.hashed("203.0.113.9")}
    assert "REMOVE p.ip_hash" in party.FORGET_IP
    assert "DETACH DELETE p" in party.REMOVE_IP


def test_locked_parties_counts_other_locked_parties_by_river():
    session = Session({party.LOCKED_PARTIES: [{"river": "Salt", "n": 3}]})
    assert party.locked_parties(session, KEY) == {"Salt": 3}
    assert session.params(party.LOCKED_PARTIES)["key"] == party.hashed(KEY)
    assert "p.locked IS NOT NULL" in party.LOCKED_PARTIES
    assert "p.key_hash <> $key" in party.LOCKED_PARTIES
