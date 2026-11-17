"""The party half of the graph: each party, its applicants with their preferences
and days away, and its applications, read and written by key.

A party is matched only by its key's hash, every value reaches Cypher as a
parameter, and the public half is only read, except that a day away adds its Day
when the graph has none.
"""

import datetime
import hashlib
import hmac
import re
import secrets
from collections.abc import Iterable
from functools import cache
from typing import NamedTuple

from neo4j import Session, Transaction

from max_float import config, credentials

# The environment variable, or line in `config.NEO4J_CREDENTIALS`, that holds the
# server secret keys and IPs are hashed with.
SECRET = "MAX_FLOAT_SECRET"

KEY = re.compile(rf"[a-z]+(-[a-z]+){{{config.KEY_WORDS - 1}}}")


# A row not rated yet, as the graph stores it: a list can't hold null.
BLANK = -1


class Own(NamedTuple):
    """An applicant's ratings for one river they apply for, where they differ
    from their own. None follows their own."""

    flow: list[int] | None = None
    temperature: list[int] | None = None
    priority: list[int] | None = None


class Applicant(NamedTuple):
    """A person in a party: their ratings for each category on each scale in step
    order, and for odds, flow and temperature, None for a row not rated yet; the
    rivers they apply for with any ratings of their own for each; the days they
    marked off; and when they said they were done, None if they've changed
    anything since or never did."""

    flow: list[int | None]
    temperature: list[int | None]
    priority: list[int | None]
    rivers: dict[str, Own]
    away: list[datetime.date]
    done: datetime.datetime | None = None


class Application(NamedTuple):
    """One of a party's applications: who applies for which launch, as which
    choice on their application."""

    applicant: str
    river: str
    date: datetime.date
    choice: int


class Party(NamedTuple):
    """A party as stored: its `minimum`, None for one; the trip length
    it set for each river, None for the river's longest;
    its applicants in the order they joined; its applications; when they were
    locked in, if they are; when it was created and last edited; and the seed of
    its noise, None for a party made before it had one."""

    minimum: int | None
    rivers: dict[str, int | None]
    applicants: dict[str, Applicant]
    applications: list[Application]
    locked: datetime.datetime | None
    created: datetime.datetime
    edited: datetime.datetime
    seed: int | None = None


class Made(NamedTuple):
    """A party as its maintainer sees it: the hash of the IP that made it, None
    once that's forgotten, when it was made, when it was locked in, if it is, and
    its applicants' names in the order they joined. Never its key."""

    ip_hash: str | None
    created: datetime.datetime
    locked: datetime.datetime | None
    applicants: list[str]


class TooManyParties(Exception):
    """An IP has created its week's parties."""


NEW_PARTIES = (
    "MATCH (p:Party {ip_hash: $ip}) WHERE p.created > $since RETURN count(p) AS n"
)
FORGET_IPS = (
    "MATCH (p:Party) WHERE p.ip_hash IS NOT NULL AND p.created <= $since "
    "REMOVE p.ip_hash"
)
CREATE = (
    "CREATE (:Party {key_hash: $key, ip_hash: $ip, minimum: null, seed: $seed, "
    "created: $now, edited: $now})"
)
READ_PARTY = (
    "MATCH (p:Party {key_hash: $key}) "
    "OPTIONAL MATCH (p)-[c:CONSIDERS]->(r:River) "
    "RETURN p.minimum AS minimum, p.locked AS locked, p.created AS created, "
    "p.edited AS edited, p.seed AS seed, "
    "collect({river: r.name, days: c.days}) AS rivers"
)
SEED = (
    "MATCH (p:Party {key_hash: $key}) SET p.seed = coalesce(p.seed, $seed) "
    "RETURN p.seed AS seed"
)
READ_APPLICANTS = (
    "MATCH (a:Applicant {party: $key}) "
    "OPTIONAL MATCH (a)-[o:PREFERS]->(r:River) "
    "WITH a, collect({river: r.name, flow: o.flow, temperature: o.temperature, "
    "priority: o.priority}) AS rivers "
    "OPTIONAL MATCH (a)-[:AWAY]->(d:Day) "
    "RETURN a.name AS name, a.flow AS flow, a.temperature AS temperature, "
    "a.priority AS priority, a.created AS created, a.done AS done, rivers, "
    "collect(d.date) AS away ORDER BY created"
)
READ_APPLICATIONS = (
    "MATCH (a:Applicant {party: $key})-[x:APPLIES]->(n:Launch) "
    "RETURN a.name AS applicant, n.river AS river, n.date AS date, "
    "x.choice AS choice ORDER BY applicant, choice"
)
SAVE_PARTY = (
    "MATCH (p:Party {key_hash: $key}) SET p.minimum = $minimum, p.edited = $now "
    "WITH p OPTIONAL MATCH (p)-[c:CONSIDERS]->() DELETE c "
    "WITH DISTINCT p UNWIND $rivers AS row "
    "MATCH (r:River {name: row.river}) "
    "MERGE (p)-[c:CONSIDERS]->(r) SET c.days = row.days"
)
SAVE_APPLICANT = (
    "MATCH (p:Party {key_hash: $key}) SET p.edited = $now "
    "MERGE (a:Applicant {party: $key, name: $name}) ON CREATE SET a.created = $now "
    "MERGE (a)-[:IN]->(p) "
    "SET a.flow = $flow, a.temperature = $temperature, a.priority = $priority, "
    "a.done = null "
    "WITH a OPTIONAL MATCH (a)-[o:PREFERS]->() DELETE o "
    "WITH DISTINCT a OPTIONAL MATCH (a)-[w:AWAY]->() DELETE w"
)
SAVE_PREFERS = (
    "MATCH (a:Applicant {party: $key, name: $name}) UNWIND $rivers AS row "
    "MATCH (r:River {name: row.river}) MERGE (a)-[o:PREFERS]->(r) "
    "SET o.flow = row.flow, o.temperature = row.temperature, o.priority = row.priority"
)
SAVE_AWAY = (
    "MATCH (a:Applicant {party: $key, name: $name}) UNWIND $days AS row "
    "MERGE (d:Day {date: row.date}) ON CREATE SET d.weekday = row.weekday "
    "MERGE (a)-[:AWAY]->(d)"
)
DONE = (
    "MATCH (p:Party {key_hash: $key}) WHERE p.locked IS NULL "
    "MATCH (a:Applicant {party: $key, name: $name}) SET a.done = $now "
    "RETURN a.done AS done"
)
REMOVE_APPLICANT = (
    "MATCH (p:Party {key_hash: $key}) WHERE p.locked IS NULL SET p.edited = $now "
    "WITH p MATCH (a:Applicant {party: $key, name: $name}) DETACH DELETE a"
)
MADE = (
    "OPTIONAL MATCH (b:Applicant)-[:IN]->(p) WITH p, b ORDER BY b.created "
    "RETURN p.ip_hash AS ip, p.created AS created, p.locked AS locked, "
    "collect(b.name) AS applicants ORDER BY created"
)
NAMED = (
    "MATCH (a:Applicant)-[:IN]->(p:Party) "
    "WHERE toLower(a.name) CONTAINS toLower($name) WITH DISTINCT p " + MADE
)
MADE_BY = "MATCH (p:Party {ip_hash: $ip}) " + MADE
FORGET_IP = "MATCH (p:Party {ip_hash: $ip}) REMOVE p.ip_hash RETURN count(p) AS n"
REMOVE_IP = (
    "MATCH (p:Party {ip_hash: $ip}) "
    "OPTIONAL MATCH (a:Applicant {party: p.key_hash}) "
    "WITH p, collect(a) AS people "
    "FOREACH (a IN people | DETACH DELETE a) DETACH DELETE p RETURN count(*) AS n"
)
UNLOCKED = (
    "MATCH (p:Party {key_hash: $key}) WHERE p.locked IS NULL RETURN count(p) AS n"
)
CLEAR_APPLICATIONS = (
    "MATCH (p:Party {key_hash: $key}) SET p.edited = $now "
    "WITH p MATCH (:Applicant {party: $key})-[x:APPLIES]->() DELETE x"
)
SAVE_APPLICATIONS = (
    "UNWIND $rows AS row "
    "MATCH (a:Applicant {party: $key, name: row.applicant}) "
    "MATCH (n:Launch {river: row.river, date: row.date}) "
    "MERGE (a)-[x:APPLIES]->(n) SET x.choice = row.choice, x.applied = $applied"
)
LOCK = (
    "MATCH (p:Party {key_hash: $key}) SET p.locked = $now, p.edited = $now "
    "WITH p OPTIONAL MATCH (:Applicant {party: $key})-[x:APPLIES]->() "
    "SET x.applied = true"
)
UNLOCK = (
    "MATCH (p:Party {key_hash: $key}) SET p.locked = null, p.edited = $now "
    "WITH p OPTIONAL MATCH (:Applicant {party: $key})-[x:APPLIES]->() "
    "SET x.applied = false"
)
LOCKED_PARTIES = (
    "MATCH (p:Party) WHERE p.locked IS NOT NULL AND p.key_hash <> $key "
    "MATCH (:Applicant {party: p.key_hash})-[:APPLIES {applied: true}]->(n:Launch) "
    "RETURN n.river AS river, count(DISTINCT p) AS n"
)
LOCKED_LAUNCHES = (
    "MATCH (p:Party) WHERE p.locked IS NOT NULL AND p.key_hash <> $key "
    "MATCH (:Applicant {party: p.key_hash})-[:APPLIES {applied: true}]->(n:Launch) "
    "RETURN n.river AS river, n.date AS date, count(DISTINCT p) AS n"
)
APPLIED = (
    "MATCH (a:Applicant)-[x:APPLIES {applied: true}]->(n:Launch) "
    "WHERE a.party <> $key "
    "RETURN n.river AS river, n.date AS date, count(x) AS n"
)


def secret() -> bytes:
    """The server secret, from the environment or the Neo4j credentials file."""
    found = credentials.get(SECRET, config.NEO4J_CREDENTIALS)
    if not found:
        raise RuntimeError(f"{SECRET} is not set")
    return found.encode()


def hashed(text: str) -> str:
    """HMAC-SHA256 of a key or an IP with the server secret."""
    return hmac.new(secret(), text.encode(), hashlib.sha256).hexdigest()


@cache
def words() -> tuple[str, ...]:
    """The words a key is made of: those in `config.WORDLIST` that are letters
    only, as a hyphen inside a word would break a key's shape."""
    lines = config.WORDLIST.read_text().splitlines()
    found = (line.split()[1] for line in lines if line.strip())
    return tuple(word for word in found if word.isalpha())


def new_key() -> str:
    """A key: `config.KEY_WORDS` random words joined by hyphens."""
    return "-".join(secrets.choice(words()) for _ in range(config.KEY_WORDS))


def is_key(text: str) -> bool:
    """Whether text has the shape of a key, so the page's route can tell a key
    from any other path."""
    return KEY.fullmatch(text) is not None


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def native(value: object) -> object:
    """A Neo4j date or time as Python's, and anything else as it is."""
    return value.to_native() if hasattr(value, "to_native") else value


def new_seed() -> int:
    """A seed for a party's noise."""
    return secrets.randbelow(2**31)


def seeded(session: Session, key: str) -> int | None:
    """A party's seed, giving it one first if it was made before parties had them.
    None when the key opens no party."""
    found = session.execute_write(
        lambda tx: tx.run(SEED, key=hashed(key), seed=new_seed()).single()
    )
    return None if found is None else found["seed"]


def create(session: Session, ip: str) -> str:
    """A new party, and its key. Raises `TooManyParties` once an IP has created
    `config.NEW_PARTIES_PER_WEEK` in the last week. Parties older than
    `config.IP_HASH_DAYS` days forget their IP."""
    key = new_key()

    def work(tx: Transaction) -> None:
        moment = now()
        since = moment - datetime.timedelta(days=config.IP_HASH_DAYS)
        tx.run(FORGET_IPS, since=since).consume()
        count = tx.run(NEW_PARTIES, ip=hashed(ip), since=since).single()["n"]
        if count >= config.NEW_PARTIES_PER_WEEK:
            raise TooManyParties
        tx.run(
            CREATE, key=hashed(key), ip=hashed(ip), now=moment, seed=new_seed()
        ).consume()

    session.execute_write(work)
    return key


def read(session: Session, key: str) -> Party | None:
    """The party a key opens, or None if there is none."""
    found = session.run(READ_PARTY, key=hashed(key)).single()
    if found is None:
        return None
    applicants = {}
    for record in session.run(READ_APPLICANTS, key=hashed(key)):
        applicants[record["name"]] = Applicant(
            unblank(record["flow"]),
            unblank(record["temperature"]),
            unblank(record["priority"]),
            {
                row["river"]: Own(row["flow"], row["temperature"], row["priority"])
                for row in record["rivers"]
                if row["river"] is not None
            },
            sorted(native(day) for day in record["away"]),
            native(record["done"]),
        )
    applications = [
        Application(
            record["applicant"],
            record["river"],
            native(record["date"]),
            record["choice"],
        )
        for record in session.run(READ_APPLICATIONS, key=hashed(key))
    ]
    return Party(
        found["minimum"],
        {
            row["river"]: row["days"]
            for row in found["rivers"]
            if row["river"] is not None
        },
        applicants,
        applications,
        native(found["locked"]),
        native(found["created"]),
        native(found["edited"]),
        found["seed"],
    )


def blank(ratings: list[int | None] | None) -> list[int] | None:
    """Ratings as the graph stores them, with `BLANK` for a row not rated."""
    return None if ratings is None else [BLANK if r is None else r for r in ratings]


def unblank(ratings: list[int] | None) -> list[int | None] | None:
    """Ratings as the graph gives them, with None for a row not rated."""
    return None if ratings is None else [None if r == BLANK else r for r in ratings]


def changed(result: object) -> bool:
    """Whether a statement wrote anything, which a statement on a party does only
    when the key opens one."""
    return result.consume().counters.contains_updates


def save_party(
    session: Session, key: str, minimum: int | None, rivers: dict[str, int | None]
) -> bool:
    """Replace the party's minimum and the rivers it's considering. False when the
    key opens no party."""
    rows = [{"river": river, "days": days} for river, days in rivers.items()]
    return session.execute_write(
        lambda tx: changed(
            tx.run(SAVE_PARTY, key=hashed(key), minimum=minimum, now=now(), rivers=rows)
        )
    )


def save_applicant(session: Session, key: str, name: str, applicant: Applicant) -> bool:
    """Add an applicant to the party, or replace their preferences and days away.
    False when the key opens no party."""
    rivers = [
        {"river": river} | own._asdict() for river, own in applicant.rivers.items()
    ]
    days = [{"date": day, "weekday": day.strftime("%A")} for day in applicant.away]

    def work(tx: Transaction) -> bool:
        who = {"key": hashed(key), "name": name}
        found = changed(
            tx.run(
                SAVE_APPLICANT,
                **who,
                now=now(),
                flow=blank(applicant.flow),
                temperature=blank(applicant.temperature),
                priority=blank(applicant.priority),
            )
        )
        tx.run(SAVE_PREFERS, **who, rivers=rivers).consume()
        tx.run(SAVE_AWAY, **who, days=days).consume()
        return found

    return session.execute_write(work)


def done(session: Session, key: str, name: str) -> datetime.datetime | None:
    """Mark an applicant done, until they next change anything, and return when.
    None, with nothing marked, when the party is locked."""

    def work(tx: Transaction) -> object:
        record = tx.run(DONE, key=hashed(key), name=name, now=now()).single()
        return None if record is None else native(record["done"])

    return session.execute_write(work)


def remove_applicant(session: Session, key: str, name: str) -> bool:
    """Remove an applicant, with their days away and applications. False when the
    key opens no party, or one whose dates are locked in."""
    return session.execute_write(
        lambda tx: changed(
            tx.run(REMOVE_APPLICANT, key=hashed(key), name=name, now=now())
        )
    )


def replace_applications(
    tx: Transaction, key: str, applications: Iterable[Application], applied: bool
) -> None:
    rows = [application._asdict() for application in applications]
    tx.run(CLEAR_APPLICATIONS, key=hashed(key), now=now()).consume()
    tx.run(SAVE_APPLICATIONS, key=hashed(key), rows=rows, applied=applied).consume()


def save_plan(session: Session, key: str, applications: Iterable[Application]) -> bool:
    """Replace the party's applications with its latest plan, unless they're locked
    in. Returns whether they were replaced."""

    def work(tx: Transaction) -> bool:
        if not tx.run(UNLOCKED, key=hashed(key)).single()["n"]:
            return False
        replace_applications(tx, key, applications, applied=False)
        return True

    return session.execute_write(work)


def lock(
    session: Session, key: str, applications: Iterable[Application]
) -> datetime.datetime:
    """Lock in the party's applications: replace them with the plan given and mark
    them applied, which counts them in other parties' odds. Returns when."""
    moment = now()

    def work(tx: Transaction) -> None:
        replace_applications(tx, key, applications, applied=True)
        tx.run(LOCK, key=hashed(key), now=moment).consume()

    session.execute_write(work)
    return moment


def unlock(session: Session, key: str) -> bool:
    """Unlock the party's applications, so saves replace them again. False when
    the key opens no party."""
    return session.execute_write(
        lambda tx: changed(tx.run(UNLOCK, key=hashed(key), now=now()))
    )


def applied(session: Session, key: str | None = None) -> dict[tuple[str, object], int]:
    """How many applications other parties have locked in for each launch, by
    (river, date). With a key, that party's own aren't counted."""
    return {
        (record["river"], native(record["date"])): record["n"]
        for record in session.run(APPLIED, key="" if key is None else hashed(key))
    }


def locked_parties(session: Session, key: str) -> dict[str, int]:
    """How many other parties have locked in applications for each river."""
    return {
        record["river"]: record["n"]
        for record in session.run(LOCKED_PARTIES, key=hashed(key))
    }


def locked_launches(session: Session, key: str) -> dict[tuple[str, object], int]:
    """How many other parties have locked in applications for each launch, by
    (river, date)."""
    return {
        (record["river"], native(record["date"])): record["n"]
        for record in session.run(LOCKED_LAUNCHES, key=hashed(key))
    }


def ip_hash(address: str) -> str:
    """The hash an IP is stored as. An address that's already a hash, as `named`
    and `made_by` give them, is returned as it is."""
    return address if re.fullmatch(r"[0-9a-f]{64}", address) else hashed(address)


def made(records: Iterable[object]) -> list[Made]:
    return [
        Made(
            record["ip"],
            native(record["created"]),
            native(record["locked"]),
            list(record["applicants"]),
        )
        for record in records
    ]


def named(session: Session, name: str) -> list[Made]:
    """The parties with an applicant whose name contains `name`, in any case."""
    return made(session.run(NAMED, name=name))


def made_by(session: Session, address: str) -> list[Made]:
    """The parties an IP, or its hash, made in the last `config.IP_HASH_DAYS`
    days. Older ones have forgotten it."""
    return made(session.run(MADE_BY, ip=ip_hash(address)))


def forget_ip(session: Session, address: str) -> int:
    """Take an IP, or its hash, off the parties it made, so it can make its
    week's parties again. The parties stay. Returns how many."""
    return session.execute_write(
        lambda tx: tx.run(FORGET_IP, ip=ip_hash(address)).single()["n"]
    )


def remove_ip(session: Session, address: str) -> int:
    """Delete the parties an IP, or its hash, made in the last
    `config.IP_HASH_DAYS` days, with their applicants, days away and
    applications. Returns how many."""
    return session.execute_write(
        lambda tx: tx.run(REMOVE_IP, ip=ip_hash(address)).single()["n"]
    )
