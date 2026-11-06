# Roadmap

The beta opens December 1, the day applications typically open, for ten rivers. See [Scope](#scope).

## Product

One screen.

- Top: rivers and trip length.
- Middle: one row per applicant, one column per day. Drag across days to mark them off.
- Preferences: which flow and temperature categories are checked, a priority slider, and how many applicants must be free, for the party or for one river. See [ui/README.md](src/max_float/ui/README.md).
- Results, updated as you edit: any rivers widened, the group's odds of at least one permit, then one row per application with date, river, applicant and odds.
- The URL holds the party's key. Share the link to share the plan. No accounts, no save button. See [graph/README.md](src/max_float/graph/README.md).

## Architecture

```
ingest → graph → rivers · launches · plan → page · JSON API · MCP
```

| Function | Returns |
|---|---|
| `rivers()` | Each river's agency, gauges, put-ins and lottery rules |
| `launches(river, start, end)` | Odds and conditions for each launch date |
| `plan(party, applicant=None)` | Which applicant applies for which launch, and any rivers widened |

One FastAPI service serves the page at `/`, the same three functions as JSON at `/api/*`, and as MCP tools at `/mcp`. The page is plain HTML, CSS and JavaScript with no build step. Only ingest and the live service need credentials.

The service runs on Render's Starter web service, $7 a month for 512 MB, at `maxfloat.gen-omix.com`. The website stays on Squarespace and links to it.

## Timeline

| Phase | Dates | Done when |
|---|---|---|
| 0. Setup | Oct 29 – Nov 1 | Repo on GitHub, keys and database ready, rivers chosen |
| 1. Data | Nov 2 – Nov 13 | Rules sourced for all nine lotteries |
| 2. Model | Nov 9 – Nov 19 | `plan` works on fixtures; backtest run |
| 3. Graph | Nov 13 – Nov 20 | `rivers` and `launches` read from Neo4j; parties saved by key |
| 4. Service | Nov 16 – Nov 25 | Page, JSON API and MCP work against the graph |
| 5. Beta prep | Nov 23 – Nov 30 | Deployed; a test party planned on every river |
| **Beta** | **Dec 1** | **Planner live for all ten rivers** |
| 6. Beta window | Dec 1 – Jan 31 | Fixes shipped while applications are open |
| 7. Write-up | Jan 4 – Jan 24 | Posts published and on the website |
| 8. After the draw | Feb – May 2027 | Predictions scored against 2027 results |

Applications typically open Dec 1 and close Jan 31. Confirm 2027 dates when agencies publish them.

If time runs short, cut in this order and bring each back during the beta window:

1. Evals.
2. Applicant plans below the whole party. The party's plan still ships.
3. The nightly export, replaced by an export run by hand.

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

- [x] RIDB: applications and permits per launch.
- [x] RIDB: launch points, with `config.POINTS` where RIDB's isn't on the section.
- [x] USGS: daily flow for each river's gauge.
- [x] NOAA: daily highs and lows from a station near each river.
- [x] Lottery rules for each of the nine lotteries, as far as sources state them: `config.LOTTERY_RULES`.
- [ ] Confirm the choices per application with the agencies: the San Juan and Rio Chama have no source, and the rest are old or from secondary sources.
- [ ] Tests: schemas, units, plausible ranges.

American Whitewater has no API and its data is volunteer-contributed. Link to it; don't ingest it.

## 2. Model

- [x] `odds.group_odds`: 1 − ∏(1 − pᵢ).
- [x] `odds.py`: odds, applications and permits for each launch, from every past season of its river.
- [ ] `conditions.py`: each launch's categories by year, its typical flow and temperature, and the chance m it matches the preferences, for the whole trip.
- [ ] `plan.py`: min-cost flow, source → application → launch → river → sink. A launch has no edge when its typical flow or temperature is unchecked. The rest have edge cost log(1 − p·m^w), where p is the launch's odds, m the chance conditions match and w comes from the priority slider. At w = 1 the plan maximizes the group's chance of at least one permit with good conditions, 1 − ∏(1 − p·m), and that chance is what's reported at every priority. Assumes independent draws; check that against each lottery's rules. With no constraints, the result must equal picking the top launches by p·m^w. Changing one river's priority must never change how many applications any river gets. A river with no launches left is widened, with a warning. See [graph/README.md](src/max_float/graph/README.md).
- [ ] `backtest.py`: predict 2025 from earlier years only; check calibration.

Odds are never published as a table.

## 3. Graph

- [x] Public nodes: Lottery, River, Agency, Day, Launch, Gauge, WeatherStation.
- [x] Idempotent `MERGE` loads from `data/`, for the ten rivers: `max_float.graph.load`. The Rogue stays in `config.RIVERS` and the CSVs, and the load skips it because it has no odds.
- [ ] Run the load against the live instance.
- [ ] `rivers()` and `launches()` query the graph.
- [ ] Party nodes: Party and Applicant, read and written by key, with the limit on new parties.
- [ ] Applications marked applied count in other parties' odds.
- [ ] Nightly export of the party half to S3.
- [ ] Keep the instance awake through the beta: AuraDB Free pauses after 72 hours idle.

## 4. Service

- [ ] FastAPI app: `/`, `/p/{key}`, `/api/rivers`, `/api/launches`, `/api/plan`, `/mcp`.
- [ ] MCP tools `rivers`, `launches` and `plan`, with schemas generated from the same type hints.
- [ ] The page described under Product: the checkboxes and priority slider for the party and for one river, and the red banner for rivers widened. Footer: data credits and "Not safety or navigation advice."

## 5. Beta prep

- [ ] Deploy to a Render Starter web service from GitHub, with credentials in its environment.
- [ ] Add `maxfloat.gen-omix.com` as a custom domain in Render, and its CNAME record in the domain's DNS, leaving `www` and the root as they are. Do this by Nov 24, as DNS changes can take 48 hours.
- [ ] Link to the planner from the website.
- [ ] Evals: 20 trip-planning requests run by an agent against `/mcp`, checked for correct calls and answers.
- [ ] Plan a test party from start to finish on every river, and check its launches and rules against Recreation.gov.
- [ ] Recheck each lottery's published 2027 rules and dates on Nov 30.

## 6. Beta window

- [ ] Fix what beta parties find.
- [ ] Update rules and dates as agencies publish them.
- [ ] Bring back anything cut from the beta.

## 7. Write-up

- [ ] "How I estimated river permit odds": the model, the backtest, the Four Rivers scenario.
- [ ] Architecture: three functions, three surfaces.
- [ ] Flagship project on the website.

## 8. After the draw

- [ ] Score predictions against 2027 results.
- [ ] Refit with 2027 data.
- [ ] Update conditions as spring snowpack comes in.
- [ ] Add rivers.

## After beta

- [ ] Lottery-only odds: RIDB's permits include trips rebooked after cancellations, so `odds.csv` runs above lottery-only odds, about three times on the Middle Fork. Find how many permits each lottery awarded in its latest season, with a link to the source, and scale each river's permits to match.
- [ ] The Rogue: find a source for its permits, as RIDB has almost none, then add it to the graph and the page.
- [ ] Lottery results by launch date and year, compiled by hand from agency PDFs into `data/manual/lottery_results.csv` with a `source_url` on every row.
- [ ] Forecast applicants per launch date with a trend and uncertainty, e.g. negative binomial, partially pooled across rivers. Include a rule-change parameter: in Oct 2026 the Forest Service said Four Rivers changes could roughly double Main and Middle Fork odds.
- [ ] Bug seasons: hand-curated, sourced windows per river.
- [ ] `bugs` on each Launch: true when the trip overlaps the river's bug season.
- [ ] Bugs preference: avoid or don't, starting at don't, for the party or for one river. Avoiding them drops launches in bug season from the plan.
- [ ] Decide whether hand-curated bug seasons are good enough, and whether bugs get a scale or stay in season and out of season.

## Scope

Ten rivers in nine lotteries for the beta: Middle Fork Salmon, Main Salmon, Selway, Snake - Hells Canyon, Green - Gates of Lodore, Yampa, San Juan, Green - Desolation/Gray, Rio Chama and Salt. See [ingest/README.md](src/max_float/ingest/README.md).

The Rogue waits until it has permit data.

| River | Reference figure, to verify in phase 1 |
|---|---|
| Middle Fork Salmon | ~1.8% in 2025; applicants 11,611 (2016) → 21,098 (2026) |

## Open questions

- Will the 2027 Four Rivers rules be final before Dec 1? If not, the beta opens on the latest published rules and updates when they change.

## Credits

USGS and NOAA (public domain); Recreation.gov RIDB; managing-agency lottery publications, cited per row.
