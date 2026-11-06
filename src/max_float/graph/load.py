"""Load the public half of the graph from rivers.csv, odds.csv and conditions.csv.

Every statement merges on a node's key, so loading again updates what's there, and
nothing is deleted: a launch no longer in the files is marked inactive, keeping any
party's applications for it. A river is loaded only if it has odds, which leaves out
the Rogue. Build the files
with `max_float.ingest` and `max_float.odds` first.
"""

import csv
import datetime
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from neo4j import Session, Transaction

from max_float import config
from max_float.graph import driver
from max_float.ingest.conditions import temperature_step
from max_float.ingest.rivers import CATEGORIES

# A year with no reading in `flow_years` or `temperature_years`, as Neo4j lists
# can't hold nulls.
NO_READING = -1

# A night under this low, in degrees F, is freezing.
FREEZING_F = 32

CONSTRAINTS = [
    f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE {key} IS UNIQUE"
    for name, label, key in (
        ("lottery_key", "Lottery", "(n.ridb_id, n.year)"),
        ("river_key", "River", "n.name"),
        ("agency_key", "Agency", "n.name"),
        ("gauge_key", "Gauge", "n.id"),
        ("station_key", "WeatherStation", "n.id"),
        ("day_key", "Day", "n.date"),
        ("launch_key", "Launch", "(n.river, n.date)"),
    )
]

# In the order they run: nodes, then the relationships between them.
STATEMENTS = {
    "Lottery": "UNWIND $rows AS row "
    "MERGE (n:Lottery {ridb_id: row.ridb_id, year: row.year}) SET n += row",
    "River": "UNWIND $rows AS row MERGE (n:River {name: row.name}) SET n += row",
    "Agency": "UNWIND $rows AS row MERGE (n:Agency {name: row.name}) SET n += row",
    "Gauge": "UNWIND $rows AS row MERGE (n:Gauge {id: row.id}) SET n += row",
    "WeatherStation": "UNWIND $rows AS row "
    "MERGE (n:WeatherStation {id: row.id}) SET n += row",
    "Day": "UNWIND $rows AS row MERGE (n:Day {date: row.date}) SET n += row",
    "Launch": "UNWIND $rows AS row "
    "MERGE (n:Launch {river: row.river, date: row.date}) SET n += row",
    "RETIRE": "WITH [row IN $rows | [row.river, row.date]] AS current "
    "MATCH (n:Launch) WHERE NOT [n.river, n.date] IN current "
    "SET n.active = false",
    "IN": "UNWIND $rows AS row "
    "MATCH (r:River {name: row.river}) "
    "MATCH (l:Lottery {ridb_id: row.ridb_id, year: row.year}) "
    "MERGE (r)-[e:IN]->(l) "
    "SET e.season_start = row.season_start, e.season_end = row.season_end",
    "RUN_BY": "UNWIND $rows AS row "
    "MATCH (l:Lottery {ridb_id: row.ridb_id, year: row.year}) "
    "MATCH (a:Agency {name: row.agency}) "
    "MERGE (l)-[:RUN_BY]->(a)",
    "MEASURED_AT": "UNWIND $rows AS row "
    "MATCH (r:River {name: row.river}) MATCH (g:Gauge {id: row.gauge}) "
    "MERGE (r)-[:MEASURED_AT]->(g)",
    "NEAR": "UNWIND $rows AS row "
    "MATCH (r:River {name: row.river}) MATCH (s:WeatherStation {id: row.station}) "
    "MERGE (r)-[:NEAR]->(s)",
    "OF": "UNWIND $rows AS row "
    "MATCH (l:Launch {river: row.river, date: row.date}) "
    "MATCH (r:River {name: row.river}) "
    "MERGE (l)-[:OF]->(r)",
    "ON": "UNWIND $rows AS row "
    "MATCH (l:Launch {river: row.river, date: row.date}) "
    "MATCH (d:Day {date: row.date}) "
    "MERGE (l)-[:ON]->(d)",
}


def read(path: Path) -> list[dict[str, str]]:
    """A data file's rows."""
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def decimal(text: str) -> float | None:
    """A number from a CSV cell, or None if it's blank."""
    return float(text) if text else None


def whole(text: str) -> int | None:
    """A whole number from a CSV cell, or None if it's blank."""
    return int(float(text)) if text else None


def day(text: str) -> datetime.date:
    """A date from a CSV cell."""
    return datetime.date.fromisoformat(text)


def past_trips(
    launch: datetime.date, days: dict[datetime.date, dict[str, str]], trip_days: int
) -> dict[str, list]:
    """A launch's conditions in each of `config.FLOW_YEARS`: its flow step on the
    launch day, the temperature step of the mean high over the trip, and whether
    the trip had a freezing night."""
    flows, temperatures, freezing = [], [], []
    for year in config.FLOW_YEARS:
        start = launch.replace(year=year)
        trip = [
            days.get(start + datetime.timedelta(offset), {})
            for offset in range(trip_days)
        ]
        highs = [float(row["high_f"]) for row in trip if row.get("high_f")]
        lows = [float(row["low_f"]) for row in trip if row.get("low_f")]
        flow = whole(trip[0].get("flow_step", ""))
        flows.append(NO_READING if flow is None else flow)
        temperatures.append(temperature_step(fmean(highs)) if highs else NO_READING)
        freezing.append(any(low < FREEZING_F for low in lows))
    return {
        "flow_years": flows,
        "temperature_years": temperatures,
        "freezing_years": freezing,
    }


def overall_odds(launch: dict[str, str]) -> tuple[float, int]:
    """A river's overall odds and their season, from the `scale_{season}` column
    of one of its odds.csv rows."""
    name = max(column for column in launch if column.startswith("scale_"))
    return float(launch[name]), int(name.removeprefix("scale_"))


def tables(
    rivers: list[dict[str, str]],
    odds: list[dict[str, str]],
    conditions: list[dict[str, str]],
) -> dict[str, list[dict[str, object]]]:
    """The rows for each of `STATEMENTS`, from the data files' rows."""
    launches: dict[str, list[dict[str, str]]] = defaultdict(list)
    for launch in odds:
        if launch["odds"]:
            launches[launch["river"]].append(launch)
    days: dict[str, dict[datetime.date, dict[str, str]]] = defaultdict(dict)
    for row in conditions:
        if row["river"] in launches:
            days[row["river"]][day(row["date"])] = row
    rows: dict[str, list[dict[str, object]]] = {name: [] for name in STATEMENTS}
    lotteries, agencies, gauges, stations, dates = {}, {}, {}, {}, {}
    for river in rivers:
        name = river["river"]
        if name not in launches:
            continue
        lottery = {"ridb_id": int(river["ridb_id"]), "year": int(river["year"])}
        lotteries[river["ridb_id"]] = lottery | {
            "name": river["ridb_name"],
            "applications_open": day(river["applications_open"]),
            "application_deadline": day(river["application_deadline"]),
            "choices_per_application": whole(river["choices_per_application"]),
            "applications_per_person": whole(river["applications_per_person"]),
            "on_trip": river["on_trip"] or None,
            "permits_per_person": whole(river["permits_per_person"]),
            "source_url": river["rules_source"],
        }
        agencies[river["agency"]] = {
            "name": river["agency"],
            "source_url": config.RIDB_DOWNLOAD,
        }
        gauges[river["gauge_id"]] = {
            "id": river["gauge_id"],
            "name": river["gauge_name"],
            "source_url": config.USGS_SITE.format(site=river["gauge_id"]),
        }
        station = next(iter(days[name].values()))["station_id"]
        stations[station] = {
            "id": station,
            "source_url": config.NOAA_STATION.format(station=station),
        }
        odds_overall, season = overall_odds(launches[name][0])
        trip_days = int(river["max_trip_days"])
        rows["River"].append(
            {
                "name": name,
                "section": river["section"],
                "latitude": float(river["latitude"]),
                "longitude": float(river["longitude"]),
                "launches_per_day": whole(river["launches_per_day"]),
                "max_group": whole(river["max_group"]),
                "max_trip_days": trip_days,
                "flow_starts": list(config.FLOWS[name]),
                "flow_shares": [
                    float(river[f"{category}_share"]) for category in CATEGORIES
                ],
                "overall_odds": odds_overall,
                "overall_odds_season": season,
                "source_url": river["rules_source"],
            }
        )
        rows["IN"].append(
            lottery
            | {
                "river": name,
                "season_start": day(river["season_start"]),
                "season_end": day(river["season_end"]),
            }
        )
        rows["RUN_BY"].append(lottery | {"agency": river["agency"]})
        rows["MEASURED_AT"].append({"river": name, "gauge": river["gauge_id"]})
        rows["NEAR"].append({"river": name, "station": station})
        for launch in launches[name]:
            date = day(launch["date"])
            dates[date] = {"date": date, "weekday": launch["weekday"]}
            key = {"river": name, "date": date}
            rows["Launch"].append(
                key
                | {
                    "applications": decimal(launch["applications"]),
                    "permits": decimal(launch["permits"]),
                    "odds": decimal(launch["odds"]),
                    "odds_low": decimal(launch["odds_low"]),
                    "odds_high": decimal(launch["odds_high"]),
                    "trip_days": trip_days,
                    "active": True,
                    "source_url": config.RIDB_DOWNLOAD,
                }
                | past_trips(date, days[name], trip_days)
            )
            rows["RETIRE"].append(key)
            rows["OF"].append(key)
            rows["ON"].append(key)
    rows["Lottery"] = list(lotteries.values())
    rows["Agency"] = list(agencies.values())
    rows["Gauge"] = list(gauges.values())
    rows["WeatherStation"] = list(stations.values())
    rows["Day"] = list(dates.values())
    return rows


def write(tx: Transaction, rows: dict[str, list[dict[str, object]]]) -> None:
    """Run every statement in `STATEMENTS` with its rows."""
    for name, statement in STATEMENTS.items():
        tx.run(statement, rows=rows[name]).consume()


def counts(session: Session) -> dict[str, int]:
    """How many of each node and relationship are in the graph."""
    found = {}
    for record in session.run("MATCH (n) RETURN labels(n)[0] AS name, count(*) AS n"):
        found[record["name"]] = record["n"]
    for record in session.run("MATCH ()-[e]->() RETURN type(e) AS name, count(*) AS n"):
        found[record["name"]] = record["n"]
    return found


def load() -> dict[str, int]:
    """Load the data files into the graph in one transaction, so a failure leaves
    it as it was, and return `counts`."""
    rows = tables(
        read(config.RIVERS_CSV), read(config.ODDS_CSV), read(config.CONDITIONS_CSV)
    )
    with driver() as connection, connection.session() as session:
        for constraint in CONSTRAINTS:
            session.run(constraint).consume()
        session.execute_write(write, rows)
        return counts(session)


if __name__ == "__main__":
    for name, count in sorted(load().items()):
        print(f"{name}: {count}")
