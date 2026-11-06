# graph

What's known about each river's lottery, and each party's plan. Ingest and the service write it; `rivers`, `launches` and `plan` read it. How the page shows it is in [ui/README.md](../ui/README.md).

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
| River | `name` | trip length range, point, flow cutoffs |
| Agency | `name` | |
| Day | `date` | `weekday` |
| Launch | `river`, `date` | odds, expected applications and permits, interval, `flow_years`, `temperature_years`, `freezing_years` |
| Gauge, WeatherStation | source ID | |
| Party | key hash | preferences, `minimum`, `created`, `edited`, `ip_hash` for its first 7 days |
| Applicant | party, `name` | |

| Relationship | Means |
|---|---|
| `(River)-[:IN]->(Lottery)` | Gates of Lodore and the Yampa share lottery 250014 |
| `(Lottery)-[:RUN_BY]->(Agency)` | |
| `(Launch)-[:OF]->(River)`, `(Launch)-[:ON]->(Day)` | a launch is a river on a day |
| `(Party)-[:CONSIDERS {days, preferences}]->(River)` | a river the party is considering, its trip length, and any preferences that differ from the party's |
| `(Applicant)-[:IN]->(Party)` | |
| `(Applicant)-[:AWAY]->(Day)` | a day marked off |
| `(Applicant)-[:APPLIES {choice, applied}]->(Launch)` | the plan; `applied` once the applicant has submitted it |

Weekday is a property of Day, not a node: it's fixed by the date, and nothing attaches to a weekday that doesn't attach to its days. Days marked off are stored rather than free days, because there are fewer of them.

## Conditions

Flow and temperature are ordinal scales. Each launch stores its category for every past year, so a summary or a match can be computed for any preference without another query.

### Flow

| Step | Category |
|---|---|
| 0 | not running |
| 1 | extra low |
| 2 | low |
| 3 | normal |
| 4 | high |
| 5 | spicy high |
| 6 | extra spicy high |

- Each river's cutoffs are flows in cfs at its gauge, in `config.FLOWS`, and its gauge is in `config.GAUGES`. `rivers.csv` has each category's range and share of lottery-season days.
- A past launch's category comes from the gauge's flow on the launch day.
- `flow_years` lists the launch's category in each of `config.FLOW_YEARS`.

| Summary | Is |
|---|---|
| `flow_typical` | the median category over the years |
| `flow_runnable_frequency` | the share of years at low or above |
| `flow_good_frequency` | the share of years at normal or above |

### Temperature

| Step | Category | Daily high, °F |
|---|---|---|
| 0 | cold | under 60 |
| 1 | cool | 60–69 |
| 2 | mild | 70–79 |
| 3 | warm | 80–89 |
| 4 | hot | 90–99 |
| 5 | extra hot | 100 and over |

- A past trip's category comes from the mean of the daily highs over the trip, at the nearest station.
- `temperature_years` lists that category for each year. `freezing_years` lists whether the trip had a night under 32°F.

| Summary | Is |
|---|---|
| `temperature_typical` | the median category over the years |
| `cold_frequency` | the share of years with a night under 32°F |
| `heat_frequency` | the share of years with a high of 100°F or more |

### Matching preferences

Preferences are the checked categories on each scale, stored as their steps, and the priority.

A launch is dropped from the plan when its `flow_typical` or `temperature_typical` isn't checked. Typical is the test because a launch's categories vary by year: on the default checkboxes, requiring every past year to be checked would leave the Rio Chama 1 launch and the Salt none, while typical keeps all 30 and 49 of 76.

For a launch that's left, the chance m that it matches is the share of past years in which its flow category and its temperature category were both checked. A launch with an m of 0 is dropped too. Counting flow and temperature together, year by year, keeps their correlation: hot years melt out early.

The party sets one value for each preference, and flow's and temperature's values are their sets of checked steps. Any preference a river changes is stored on that river's CONSIDERS relationship and replaces the party's value for that river only. A launch uses its own river's values.

## Keys

- Four words from the EFF long wordlist, e.g. `otter-canyon-cobble-ferry`: 7,776⁴ ≈ 3.7 × 10¹⁵ keys.
- The page's URL is `/p/{key}`. Anyone with the link can edit the plan. No accounts, no passwords.
- The graph stores `HMAC-SHA256(key, server secret)`, never the key, so a copy of the database opens no party.
- One function reads and writes a party, and it takes the key. No other query matches Party or Applicant. No request carries Cypher.
- At most 3 new parties a week from one IP. A new Party holds `ip_hash`, `HMAC-SHA256(IP, server secret)`. The limit counts the parties with that hash created in the last 7 days, and `ip_hash` is removed once its party is 7 days old. A week is too long to count in memory, because a restart or deploy would reset the count.

## Odds

- `data/` isn't in git. Fitted odds reach the service only through the graph.
- The beta loads ten rivers. The Rogue stays in `config.RIVERS` and the CSVs, and the load skips it until it has permit data.
- A launch's permits are lottery-only: RIDB's permits, which include trips rebooked after cancellations, scaled to the lottery's published permits.
- `launches` and `plan` return odds, rounded to `config.ODDS_DIGITS` decimal places: 4 by default, a hundredth of a percent.
- Given no river, `launches` returns every river's launches, so the page needs one call.
- Expected applications, permits, intervals and weekday factors stay in the graph.

## Other parties

A launch's odds for a party count the other parties' applications for it:

p′ = permits / (applications + n)

where n is the number of other parties' applications for that launch marked applied. An application counts from the moment it's marked applied, so a plan that's still being edited doesn't move anyone else's odds, and abandoned plans count for nothing. A party's own applications are never in n. Other parties' applications aren't in the forecast, because it was fitted on years before max-float existed. On the Middle Fork, May 29, 2027 is expected to draw 54 applications. RIDB's 12.74 permits scale to about 4.2 lottery-only permits, using the 361 lottery permits [OARS reports for 2024](https://www.oars.com/blog/how-to-get-most-popular-private-river-permits) against RIDB's 1,099, so about 7.7%. With 10 applications from other parties it's about 6.5%. Popular launches barely change. Launches with few applications, which is where the planner sends people, change the most.

Only counts reach a party. Nothing shows which party applied.

## Plan as a flow

`plan` builds a flow network in memory from the graph for each call. The network isn't stored.

```
source → application → launch → river → sink
```

| Edge | Exists when | Capacity | Cost |
|---|---|---|---|
| source → application | an application is one applicant in one lottery | lottery's choices per application | 0 |
| application → launch | the applicant and at least `minimum` applicants have no AWAY day in the trip, and the launch isn't dropped by the preferences | 1 | log(1 − p′·m^w) |
| launch → river | | applications the party may make for one launch | 0 |
| river → sink | | the river's share of the plan: unlimited in the first solve, fixed in the second | 0 |

m is the chance conditions match the preferences, and w comes from the priority. Costs are scaled to integers for `networkx.max_flow_min_cost`. Every cost is zero or less, so the cheapest maximum flow gives the highest odds at that priority. Dropped launches have no edge rather than a high cost, because a maximum flow would still use a costly edge to fill spare choices. Days and weekdays decide which edges exist. They don't appear in the flow. A node joins the flow only when it carries a capacity or a cost.

Neo4j runs no algorithms: AuraDB Free has no Graph Data Science, and the flow is small enough to solve in Python.

### Priority

`priority` is how much conditions count against odds among the launches left after the checks. It runs from 0 to 10 in whole steps, and starts at 5. A launch's w is 4^((priority − 5) / 5), using its own river's priority:

| Priority | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| w | 0.25 | 0.33 | 0.44 | 0.57 | 0.76 | 1 | 1.32 | 1.74 | 2.3 | 3.03 | 4 |

Only a priority of 5 on every river maximizes the chance of at least one permit in matching conditions, 1 − ∏(1 − p′·m). Other settings give up some of that chance to lean toward odds or conditions. `plan` reports that same chance at every priority, so plans can be compared.

On the Middle Fork, with normal and high flow and mild and warm temperature checked, 33 of 99 launches are left. The best six at a priority of 0 or 5 are May 29, May 30 and June 2 to 5. At 10, June 8 replaces June 2.

### A river's share

A river's own priority changes which launches it gets, never how many. Weighting one river's launches differently would otherwise move applications to other rivers, so `plan` solves the flow twice:

1. Every river at the party's priority. The number of applications each river gets is its share.
2. Each river at its own priority, with river → sink capped at its share.

The first solve's flow fits inside the second's capacities, so the second places the same total and fills every share exactly. The party's priority and a river's checkboxes can still change the shares, because they change the launches every river competes with.

### Widened rivers

A river is widened when it has launches the party is free for, but its checked categories drop them all. Each of those launches is scored by the steps from its `flow_typical` and `temperature_typical` to the nearest checked categories, added together. The launches with the lowest score decide: their typical categories, and any between those and the checked ones, are added for that river. If m is 0 for all of them, the next lowest score decides.

This happens before the first solve, so a widened river competes for its share like any other. The added categories count in m. They aren't stored: `plan` works them out on each call and returns each widened river with the categories added, so the page, the API and the MCP tools all report the same warning. A river with no free launches isn't widened, and `plan` returns the reason instead. A river that keeps its launches but gets no applications isn't widened.

With normal or better flow and mild or warmer temperature checked, the Salt has no launches left. Widening adds low flow, which leaves 31.

### Minimum

`minimum` is how many applicants must be free for a launch. It starts at the whole party, which gives one plan. Below the whole party, `plan` also gives one plan for each applicant:

| Plan | Maximizes at a priority of 5 | Cost on a launch |
|---|---|---|
| party | the chance of at least one permit | log(1 − p′·m^w) |
| an applicant's | the chance that applicant gets on a trip | log(1 − p′·m^w) if the applicant is free for it, else 0 |

Each plan is the same network with different costs. `plan(party, applicant=None)` gives the party's plan, and `plan(party, applicant)` gives that applicant's. The page and the MCP tool both pass the same argument.

## Storage

AuraDB Free allows 200,000 nodes and 400,000 relationships, pauses after 72 hours idle, deletes a database paused for 30 days, and keeps no backups.

| | Nodes | Relationships |
|---|---|---|
| Public, 10 rivers | ~1,500 | ~3,000 |
| One party of 6, 30 days away each | ~7 | ~200 |

That leaves room for about 2,000 parties. Daily flows and temperatures stay in `data/conditions.csv`. They'd fill the graph as nodes, and only each launch's categories by year are needed.

Every night the party half is exported to S3. If the instance is ever deleted, the public half is rebuilt by ingest and the party half is restored from the latest export. Parties are kept until the 2027 results are scored, then deleted. The instance has to stay awake through the beta, as a pause would take every party's plan offline.

## Checks

Tests run offline against a fake driver, as in `test_graph.py`. `plan` is tested on plain data without the graph, including that changing one river's priority never changes any river's share, and that widening adds only the nearest categories.

## Open questions

- What are each lottery's choices per application and limits per launch? These set the flow's capacities.
- Which years go in `config.FLOW_YEARS`? Dam operations changed on some rivers, so older years may not count.
- Should temperature follow each party's trip length, or the river's usual trip?
- Are weather stations near a river close enough to the canyon floor, or do they need correcting for elevation?
- Should an applicant be able to mark an application won, so plans can be scored after the draw?
