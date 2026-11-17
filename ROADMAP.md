# Roadmap

The beta opens December 1, the day applications typically open, for ten rivers. See [Scope](#scope).

## Product

One screen.

- Tabs: Team, one for each applicant by name, and + to join by typing a name. See [ui/README.md](src/max_float/ui/README.md).
- An applicant's tab: their votes for the ideal flow and temperature categories, their priority pie, for all rivers or for one, their unavailable dates, and their own best dates.
- The Team tab: rivers and trip lengths, how many applicants must be free, everyone's unavailable dates, the averaged preferences, the team's plan, and Lock in dates for team.
- Results, updated as anything changes: any rivers widened, the team's odds of at least one permit against the most common launches and random ones, and once locked in, each applicant's applications in choice order with their odds, to copy or download as a CSV.
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
2. The nightly export, replaced by an export run by hand.

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
- [x] Lottery-only permits: those ordered between applications closing and each lottery's release of unclaimed permits, `config.RELEASES`, leaving out first-come and rebooked permits.
- [ ] Confirm the choices per application with the agencies: the San Juan and Rio Chama have no source, and the rest are old or from secondary sources.
- [ ] Tests: schemas, units, plausible ranges.

American Whitewater has no API and its data is volunteer-contributed. Link to it; don't ingest it.

## 2. Model

- [x] `odds.group_odds`: 1 − ∏(1 − pᵢ).
- [x] `odds.py`: odds, applications and permits for each launch, from every past season of its river.
- [x] Each launch's categories by year in `graph/load.py`, and its typical flow and temperature and its flow and temperature matches in `graph/subgraph.py`.
- [x] `graph/subgraph.py`: each party's subgraph, built in memory for each plan: the launches its applicants and preferences leave, with their matches and priorities, and any rivers widened. The public graph never changes for a party.
- [x] `core.py`: `rivers`, `launches` and `plan`. A plan is the launches to apply for and who applies for each, from `plan.py`, with the odds of at least one permit with them, with as many of the most common launches, and with as many at random. `party_plan(key, applicant=None)` reads a party and other parties' locked-in applications, plans for the team with its applicants' preferences averaged, saves the plan, and with an applicant gives only the launches they apply for.
- [x] `plan.py`: min-cost flow over the party's subgraph, source → application → launch → river → sink, with an application for each applicant in each lottery. A launch has no edge when it isn't in the subgraph. The rest cost log(1 − p·f^a·t^b), where p is the launch's odds, f and t its flow and temperature matches, and a and b flow's and temperature's slices over odds'. At an even split the plan maximizes the team's chance of at least one permit with good conditions, 1 − ∏(1 − p·f·t). Changing one river's priority never changes how many applications any river gets. A river with no launches left is widened, with a warning. See [graph/README.md](src/max_float/graph/README.md).
- [ ] `backtest.py`: predict 2025 from earlier years only; check calibration.

Odds are never published as a table.

## 3. Graph

- [x] Public nodes: Lottery, River, Agency, Day, Launch, Gauge, WeatherStation.
- [x] Idempotent `MERGE` loads from `data/`, for the ten rivers: `max_float.graph.load`. The Rogue stays in `config.RIVERS` and the CSVs, and the load skips it because it has no odds.
- [x] Run the load against the live instance.
- [ ] `rivers()` and `launches()` query the graph.
- [x] Party nodes: Party and Applicant, read and written by key in `graph/party.py`, with the limit on new parties, the saved plan and the lock.
- [x] Locked-in applications count in other parties' odds, in `core.against`.
- [ ] Nightly export of the party half to S3.
- [ ] Keep the instance awake through the beta: AuraDB Free pauses after 72 hours idle.

## 4. Service

- [x] FastAPI app, v0.2: `/`, `/api/rivers`, `/api/plan`, for one applicant, with nothing saved.
- [x] FastAPI app: `/{key}`, `/api/party` to make a party, `/api/party/{key}` to read and save it, its applicants, its plan for the team or for one applicant, and its lock. Nothing in the service but validation and status codes.
- [ ] `/api/launches` and `/mcp`.
- [ ] MCP tools `rivers`, `launches` and `plan`, with schemas generated from the same type hints.
- [x] The page, v0.4: the flow and temperature votes and priority pie for all rivers and for one river, a dropdown of rivers and a calendar of unavailable dates, a Submit button, the red banner for rivers widened, recommended launches on the calendar by river code and color, with a key, in a list for each river and as a CSV, and a chart of their odds against the most common launches and random ones. See [ui/README.md](src/max_float/ui/README.md).
- [x] The page, v0.7: the tabs, each with its own colored sheet, the team's averaged preferences and combined calendar, `minimum`, autosave, the link notice, a Planning or Locked in bar, read-only while locked, each applicant's own rivers, the odds chart under the calendar, the list of launches and its download once locked in, each launch's past years, and Submit at the lower right. See [ui/README.md](src/max_float/ui/README.md).
- [ ] Footer: data credits and "Not safety or navigation advice."

## Page v0.8

From a first-use review on Nov 17. The page should need no explanation for anyone who has applied for a river permit. Two goals shape it:

- **Teams set their own preferences.** Distinct preferences spread teams across different launches, which is better for everyone.
- **Teams lock in.** It shows the team agrees, and only locked-in applications count in other teams' odds.

Each tab runs Rivers → Conditions → Dates → Done. Once everyone on the team is done, the team locks in.

### 1. Done replaces Submit

- [x] Remove Submit. Saving re-plans, and the draft updates within a couple of seconds of any change.
- [x] A Done button on each tab marks the applicant done, and drives the chips on the Team tab. Any change clears it. Vocabulary: **submitted** becomes **done**.
- [x] Every tab shows the latest draft, including after a reload.
- [x] Show a quiet "Saved" in the status bar.

### 2. What locking in gets you

- [x] Only once locked in: choice order, which applicant applies for which launch, each applicant's list and the CSV.
- [x] Locking in scrolls to **Your applications**, at the top of every tab and open. It lists each launch in choice order, the way it's entered on Recreation.gov, with Copy and CSV buttons. Each row opens that launch's history by year.
- [x] The odds section leads with the chance of at least one permit, against the chance with the most common dates, e.g. 23% against 3%. The comparison chart goes below it.
- [x] The draft shows one launch's full history as a sample. The rest open only once locked in.

### 3. Prompting the lock

- [x] When every applicant is done, the main button on every tab is **Lock in and get our applications**. A solo applicant gets it on their own tab. Locking needs no confirmation.
- [x] Facts, not hints:
  - Each river shows how many teams are locked in for it.
  - Once locked in: "Your dates now count in other teams' plans".
  - Unlocking takes the team's applications out of other teams' odds.
- [x] Coming back to a team where everyone is done opens on "Your team is ready to lock in".
- [x] Anyone arriving by a link sees a **who are you?** cover: each applicant's name, plus a new name. The answer is remembered for that team in localStorage, so the page opens on their own tab.
- [x] On a locked team, + Add your name gives way to the reason it can't be used.

### 4. Ratings replace votes and the pie

- [x] One control for flow, temperature and priority: a four-step rating for each row.
  - Each flow and temperature category is rated No, OK, Good or Ideal.
  - Odds, flow and temperature are each rated Not, Some, More or Most.
  - A row's share is its rating over the total, so changing one row never moves another.
- [x] No leaves out every launch typically in that category, as zero votes do now. Flow and temperature each need at least one row above No. If all three priorities are Not, they're weighted equally.
- [x] A thin bar beside each set shows its shares. The pie goes.
- [x] No defaults are shown, and every row starts blank.
  - The draft appears once every row in the all-rivers set is rated.
  - Done needs every row rated.
  - Each river's own ratings stay optional.
  - Noise is still measured from the hidden defaults.
- [x] Show cfs ranges when one river is in view. Beside each flow category, a strip shows when in the season that river is typically in it.
- [x] Next to the odds, show how many of the team's draft launches are among the most common.
- [x] Each draft date shows how many teams have locked in for it.
- [x] Vocabulary: **votes** become **ratings** in the page, the API, the MCP tools, the graph and AGENTS.md.
  - The core turns ratings into the shares it uses now.
  - A blank rating is stored as null.
  - Existing votes convert to the nearest rating. Nothing needed converting: the graph had no teams when ratings came in.

### 5. Calendar, rivers and cleanup

- [ ] Calendar shading:
  - Season days are plain and the rest are faded.
  - Days away are red and struck through.
  - A one-row key sits below the calendar.
  - Fix the Team tab's text saying shaded days are days away.
- [ ] Drag or shift-click to mark a range of days.
- [ ] Show only the months in the chosen rivers' seasons.
- [ ] Hovering or tapping a draft date shows its choice, odds and typical conditions.
- [ ] Each river button shows a dot for each teammate who chose it.
- [ ] Trip length goes on the river: set on the Team tab, shown on each applicant's tab.
- [ ] Minimum reads "Launch only when at least [N] of [M] can go".
- [ ] Cover:
  - It says it gives the 2027 lottery dates for these rivers.
  - The join field's placeholder is "team name or link".
  - Hide Change team behind the cover.
- [ ] Remove helper text:
  - "click dots to vote"
  - "pick one, then paint slices"
  - "Open a river to…" and "All rivers. Set conditions…"
  - The draft paragraph
  - The second team name and link in the notice
- [ ] Delete a tab from the × on the tab, not the red button by Copy link.
- [ ] Disabled controls, such as river buttons while locked, look disabled.

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
