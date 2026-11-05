# graph

What's known about each river's lottery, and each party's plan. Ingest and the service write it; `rivers`, `launches` and `plan` read it.

## Two halves

| | Public | Party |
|---|---|---|
| Written by | ingest | the service, as a party edits |
| Traces to | a `source_url` on every node | the party's key |
| Read by | `rivers`, `launches`, `plan` | requests carrying the key |

## Nodes

```mermaid
graph LR
  Agency --- Lottery --- River
  River --- Launch --- Day
  River --- Gauge
  River --- WeatherStation
  Party --- Applicant
  Applicant -- AWAY --> Day
  Applicant -- APPLIES --> Launch
  Party -- CONSIDERS --> River
```

| Node | Key | Holds |
|---|---|---|
| Lottery | `ridb_id`, `year` | choices per application, whether the holder must be on the trip, per-person limits |
| River | `name` | trip length range, point |
| Agency | `name` | |
| Day | `date` | `weekday` |
| Launch | `river`, `date` | odds, expected applications and permits, interval |
| Gauge, WeatherStation | source ID | |
| Party | key hash | preferences, `created`, `edited`, `ip_hash` for its first 7 days |
| Applicant | party, `name` | |

| Relationship | Means |
|---|---|
| `(River)-[:IN]->(Lottery)` | Gates of Lodore and the Yampa share lottery 250014 |
| `(Lottery)-[:RUN_BY]->(Agency)` | |
| `(Launch)-[:OF]->(River)`, `(Launch)-[:ON]->(Day)` | a launch is a river on a day |
| `(Party)-[:CONSIDERS {days}]->(River)` | the rivers at the top of the page, with trip length |
| `(Applicant)-[:IN]->(Party)` | |
| `(Applicant)-[:AWAY]->(Day)` | a day marked off |
| `(Applicant)-[:APPLIES {choice, applied}]->(Launch)` | the plan; `applied` once the applicant has submitted it |

Weekday is a property of Day, not a node: it's fixed by the date, and nothing attaches to a weekday that doesn't attach to its days. Days marked off are stored rather than free days, because there are fewer of them.

## Keys

- Four words from the EFF long wordlist, e.g. `otter-canyon-cobble-ferry`: 7,776⁴ ≈ 3.7 × 10¹⁵ keys.
- The page's URL is `/p/{key}`. Anyone with the link can edit the plan. No accounts, no passwords.
- The graph stores `HMAC-SHA256(key, server secret)`, never the key, so a copy of the database opens no party.
- One function reads and writes a party, and it takes the key. No other query matches Party or Applicant. No request carries Cypher.
- At most 3 new parties a week from one IP. A new Party holds `ip_hash`, `HMAC-SHA256(IP, server secret)`. The limit counts the parties with that hash created in the last 7 days, and `ip_hash` is removed once its party is 7 days old. A week is too long to count in memory, because a restart or deploy would reset the count.

## Odds stay in

- `data/` isn't in git. Fitted odds reach the service only through the graph.
- Launch odds, applications, permits and intervals live in the graph. No function returns them as they're stored.
- `plan` returns the party's odds of at least one permit and each application's odds, to the whole percent.
- `launches` returns dates and conditions, not odds.
- 60 `plan` calls a minute per key.

A party can still estimate a launch's odds by planning only that launch. These rules stop someone copying the whole table, not one curious party.

## Other parties

A launch's odds for a party count the other parties' applications for it:

p′ = permits / (applications + n)

where n is the number of other parties' applications for that launch marked applied. An application counts from the moment it's marked applied, so a plan that's still being edited doesn't move anyone else's odds, and abandoned plans count for nothing. A party's own applications are never in n. Other parties' applications aren't in the forecast, because it was fitted on years before max-float existed. On the Middle Fork, May 29, 2027 is expected to draw 54 applications for 12.74 permits, so 23.6%. With 10 applications from other parties it's 19.9%. Popular launches barely change. Launches with few applications, which is where the planner sends people, change the most.

Only counts reach a party. Nothing shows which party applied.

## Plan as a flow

`plan` builds a flow network in memory from the graph for each call. The network isn't stored.

```
source → application → launch → sink
```

| Edge | Exists when | Capacity | Cost |
|---|---|---|---|
| source → application | an application is one applicant in one lottery | lottery's choices per application | 0 |
| application → launch | the applicant has no AWAY day in the trip | 1 | −log(1 − p′·m) |
| launch → sink | | applications the party may make for one launch | 0 |

m is the chance conditions match the preferences. Costs are scaled to integers for `networkx.max_flow_min_cost`. Every cost is zero or less, so the cheapest maximum flow gives the highest group odds. Days and weekdays decide which edges exist. They don't appear in the flow. A node joins the flow only when it carries a capacity or a cost.

Neo4j runs no algorithms: AuraDB Free has no Graph Data Science, and the flow is small enough to solve in Python.

## Storage

AuraDB Free allows 200,000 nodes and 400,000 relationships, pauses after 72 hours idle, deletes a database paused for 30 days, and keeps no backups.

| | Nodes | Relationships |
|---|---|---|
| Public, 11 rivers | ~1,500 | ~3,000 |
| One party of 6, 30 days away each | ~7 | ~200 |

That leaves room for about 2,000 parties.

Every night the party half is exported to S3. If the instance is ever deleted, the public half is rebuilt by ingest and the party half is restored from the latest export. Parties are kept until the 2027 results are scored, then deleted.

## Checks

Tests run offline against a fake driver, as in `test_graph.py`. `plan` is tested on plain data without the graph.

## Open questions

- Must the whole party be free for a launch, or only some minimum?
- What are each lottery's choices per application and limits per launch? These set the flow's capacities.
- Should an applicant be able to mark an application won, so plans can be scored after the draw?
