# Roadmap

## Product

One screen.

- Top: rivers and trip length.
- Middle: one row per applicant, one column per day. Drag across days to mark them off.
- Preferences: flow (any, low, medium, high); avoid cold, heat or bugs.
- Results, updated as you edit: the group's odds of at least one permit, then one row per application with date, river, applicant and odds.
- The URL holds the plan. Share the link to share the plan. No accounts, no save button.

## Architecture

```
ingest → graph → rivers · launches · plan → page · JSON API · MCP
```

| Function | Returns |
|---|---|
| `rivers()` | Each river's agency, gauges, put-ins and lottery rules |
| `launches(river, start, end)` | Odds and conditions for each launch date |
| `plan(party, preferences)` | Which applicant applies for which launch |

One FastAPI service serves the page at `/`, the same three functions as JSON at `/api/*`, and as MCP tools at `/mcp`. The page is plain HTML, CSS and JavaScript with no build step. Only ingest and the live service need credentials.

## Timeline

| Phase | Dates | Done when |
|---|---|---|
| 0. Setup | Oct 29 – Nov 1 | Repo on GitHub, keys and database ready, rivers chosen |
| 1. Data | Nov 2 – Nov 15 | Sourced datasets for every river in scope |
| 2. Model | Nov 9 – Nov 29 | `plan` works on fixtures; backtest calibrated |
| **v0.1** | **Dec 1** | Odds table published as applications open |
| 3. Graph | Nov 23 – Dec 13 | `rivers` and `launches` read from Neo4j |
| 4. Service | Dec 7 – Jan 3 | Page and MCP live |
| **v0.2** | **~Jan 4** | Planner live with four weeks of applications left |
| 5. Write-up | Jan 4 – Jan 24 | Posts published and on the website |
| 6. After the draw | Feb – May 2027 | Predictions scored against 2027 results |

Applications typically open Dec 1 and close Jan 31. Confirm 2027 dates when agencies publish them.

## 0. Setup

- [x] Name: `max-float`
- [x] uv package, `src/` layout
- [x] License: PolyForm Strict 1.0.0
- [x] CI workflow: ruff and pytest
- [x] Push to GitHub
- [x] Recreation.gov RIDB API key
- [x] Neo4j AuraDB Free instance
- [x] Choose rivers: [ingest/README.md](src/max_float/ingest/README.md)

## 1. Data

Every number traces to a source URL.

- [ ] USGS: daily flow for each river's gauges.
- [ ] NOAA: daily highs and lows from stations near each river.
- [ ] RIDB: launch points.
- [ ] Lottery results by launch date and year, compiled by hand from agency PDFs into `data/manual/lottery_results.csv` with a `source_url` on every row.
- [ ] Lottery rules per river: choices per application, whether the applicant must be on the trip, per-person limits.
- [ ] Bug seasons: hand-curated, sourced windows per river.
- [ ] Tests: schemas, units, plausible ranges.

American Whitewater has no API and its data is volunteer-contributed. Link to it; don't ingest it.

## 2. Model

- [x] `odds.group_odds`: 1 − ∏(1 − pᵢ).
- [ ] `odds.py`: forecast applicants per launch date with a trend and uncertainty, e.g. negative binomial, partially pooled across rivers. Include a rule-change parameter: in Oct 2026 the Forest Service said Four Rivers changes could roughly double Main and Middle Fork odds.
- [ ] `conditions.py`: the chance flow, temperature and bugs match the preferences for the whole trip, from history by day of year.
- [ ] `plan.py`: min-cost flow. Source → applicant (capacity: choices per application) → each launch the applicant is free for → sink (capacity: lottery limits). Edge cost −log(1 − p·m), where p is the launch's odds and m the chance conditions match, so the plan maximizes the group's chance of at least one permit with good conditions. Assumes independent draws; check that against each lottery's rules. With no constraints, the result must equal picking the top launches.
- [ ] `backtest.py`: predict 2025 from earlier years only; check calibration.

**v0.1, Dec 1:** an odds table for the Middle Fork and the San Juan.

## 3. Graph

- [ ] Nodes: River, Agency, Gauge, WeatherStation, PutIn, TakeOut, LotteryYear, Launch.
- [ ] Idempotent `MERGE` loads from `data/processed/`.
- [ ] `rivers()` and `launches()` query the graph.

## 4. Service

- [ ] FastAPI app: `/`, `/api/rivers`, `/api/launches`, `/api/plan`, `/mcp`.
- [ ] MCP tools `rivers`, `launches` and `plan`, with schemas generated from the same type hints.
- [ ] The page described under Product. Footer: data credits and "Not safety or navigation advice."
- [ ] Evals: 20 trip-planning requests run by an agent against `/mcp`, checked for correct calls and answers.
- [ ] Deploy.

## 5. Write-up

- [ ] "How I estimated river permit odds": the model, the backtest, the Four Rivers scenario.
- [ ] Architecture: three functions, three surfaces.
- [ ] Flagship project on the website.

## 6. After the draw

- [ ] Score predictions against 2027 results.
- [ ] Refit with 2027 data.
- [ ] Update conditions as spring snowpack comes in.
- [ ] Add rivers.

## Scope

Eleven rivers: Middle Fork Salmon, Main Salmon, Selway, Snake – Hells Canyon, Rogue, Green – Gates of Lodore, Yampa, San Juan, Green – Desolation/Gray, Rio Chama and Salt. See [ingest/README.md](src/max_float/ingest/README.md).

| River | Reference figure, to verify in phase 1 |
|---|---|
| Middle Fork Salmon | ~1.8% in 2025; applicants 11,611 (2016) → 21,098 (2026) |

## Open questions

- Where to host the service?
- Must the whole party be free for a launch, or only a minimum number?
- Are hand-curated bug seasons good enough for v0.2?
- Will the 2027 Four Rivers rules be final before Dec 1?

## Credits

USGS and NOAA (public domain); Recreation.gov RIDB; managing-agency lottery publications, cited per row.
