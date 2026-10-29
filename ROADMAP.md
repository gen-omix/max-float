# max-float roadmap

**max-float** is a river permit planner: a knowledge graph, an MCP server, and a chatbot that help boaters choose permit lottery dates based on their constraints and preferences, with probability-of-success estimates from past data.

It is also a portfolio demo of knowledge graphs + LLMs + agents + MCP, built entirely on public data.

> Dates below are a proposal, assuming part-time effort. The schedule is anchored to the permit application window, which typically runs **Dec 1 – Jan 31** for the lotteries in scope. Confirm the 2027-season dates once agencies publish them.

---

## Timeline at a glance

| Phase | Name | Dates (2026–27) | Milestone |
|---|---|---|---|
| 0 | Put-in: setup | Oct 29 – Nov 1 | Repo, tooling, accounts, river list |
| 1 | Data | Nov 2 – Nov 15 | Clean, sourced datasets for every river in scope |
| 2 | Statistical model | Nov 9 – Nov 29 | Calibrated odds model with a backtest |
| ★ | **v0.1: odds table** | **Dec 1** | Static odds table published as the application window opens |
| 3 | Knowledge graph | Nov 23 – Dec 13 | Graph loaded in Neo4j AuraDB |
| 4 | MCP server + chatbot | Dec 7 – Jan 3 | Public Streamlit demo |
| ★ | **v0.2: public demo** | **~Jan 4** | Chatbot live with ~4 weeks of the window left |
| 5 | Write-up and launch | Jan 4 – Jan 24 | Blog post + website integration |
| 6 | After the draw | Feb – May 2027 | Score predictions against real results; trip-prep features |

Build order follows the plan: **data → statistical model → graph → MCP server + chatbot → write-up.** Phases overlap so the Dec 1 odds table doesn't wait on the graph.

---

## Phase 0: Put-in (setup) · Oct 29 – Nov 1

- [x] Name the project (`max-float`)
- [x] Initialize the repo with `uv` as a Python package (`src/` layout)
- [x] Create the GitHub repo and push
- [x] Choose a license
- [ ] Add CI (GitHub Actions: `ruff` + `pytest`)
- [ ] Request a Recreation.gov RIDB API key
- [ ] Create a Neo4j AuraDB Free instance (200,000 nodes / 400,000 relationships)
- [ ] **Decide the starting rivers** (see open questions)

## Phase 1: Data · Nov 2 – Nov 15

Goal: every number in the model traces back to a source URL.

- [ ] **USGS stream gauges**: identify gauges per river section; pull daily flow history (public domain). Cache raw pulls in `data/raw/`.
- [ ] **Recreation.gov RIDB**: permit entrances and launch points (free with credit to Recreation.gov).
- [ ] **Lottery statistics**: hand-compile applicants and permits by launch date and year from agency PDFs and permit pages into `data/manual/lottery_stats.csv`, with a `source_url` column on every row.
- [ ] **Climatology**: daily flow (and temperature, if a source is available) by day of year per river section.
- [ ] Write a data dictionary (`data/README.md`) covering fields, units, sources, and licenses.
- [ ] Tests for loaders (schema checks, no silent NaNs, sane flow ranges).

**Not used:** American Whitewater data. There is no public API, and the data is volunteer-contributed. Link to AW pages instead.

**Deferred:** live weather. 7-day forecasts don't help at application time; it belongs in Phase 6 trip prep.

## Phase 2: Statistical model · Nov 9 – Nov 29

Each layer lives in `src/max_float/models/`.

1. **Chance of winning each launch date** (`demand.py`): forecast applicants by date with a trend term and uncertainty, since demand is rising and past averages understate it. Candidate approach: a count model (e.g., negative binomial) with year trend and day-of-season effects, partially pooled across rivers.
2. **Chance conditions match preferences** (`conditions.py`): probability that flow lands in the user's preferred range (and heat stays tolerable) on a date, from historical data by day of year.
3. **Combined score** (`scoring.py`): rank dates by P(win) × P(good conditions), optimized over the user's constraints (available dates, trip length, rivers considered).
4. **Permit-party math** (`parties.py`): 1 − (1 − p)ⁿ for *n* party members applying, which assumes independent draws. Check that against each lottery's actual rules (one application per person, preference ranking, group limits).
5. **Backtest** (`backtest.py`): predict 2025 odds from earlier years only, then check calibration. A model that is honest about its uncertainty is the point.
6. **Rule-change scenario**: in Oct 2026 the Forest Service said it is looking at Four Rivers lottery changes expected to roughly double odds on the Main and Middle Fork. Support a "rule change" parameter so the model can show before/after odds.

**★ Dec 1 milestone (v0.1):** a static odds table (notebook or markdown) for at least Middle Fork + one Utah river, published when the application window opens. Early, timely content even before the chatbot exists.

## Phase 3: Knowledge graph · Nov 23 – Dec 13

- [ ] Schema (`graph/schema.py`): River, Section, Agency, Permit, LotteryYear, LaunchDateDemand, Gauge, PutIn, TakeOut, plus relationships (e.g., `(:Section)-[:MEASURED_BY]->(:Gauge)`, `(:Permit)-[:MANAGED_BY]->(:Agency)`).
- [ ] Loaders (`graph/load.py`): idempotent `MERGE`-based loads from `data/processed/`.
- [ ] Constraints and indexes; stay well inside the free-tier limits.
- [ ] A handful of saved Cypher queries that answer real questions ("Which sections share a gauge?", "Which launches had < 3% odds last year?").

## Phase 4: MCP server + chatbot · Dec 7 – Jan 3

- [ ] **MCP server** (`mcp_server/server.py`) exposing tools:
  - `query_graph`: run a parameterized graph query
  - `get_flow_history`: flows for a section and date range
  - `get_odds`: model output for a launch date
  - `rank_dates`: combined score for a user's constraints
- [ ] **Streamlit chatbot** (`app/streamlit_app.py`): asks about constraints (dates, trip length, rivers, preferred flows), returns ranked dates with probabilities and the reasoning behind them.
- [ ] Disclaimer on every result: **not safety or navigation advice.**
- [ ] Small eval set: ~20 realistic questions with expected tool calls and sanity-checked answers.
- [ ] Deploy to Streamlit Community Cloud (free for public apps; apps sleep after 12 hours without traffic, so note the wake-up delay on the page).

**★ ~Jan 4 milestone (v0.2):** public demo live while applications are still open.

## Phase 5: Write-up and launch · Jan 4 – Jan 24

- [ ] Blog post: **"How I estimated river permit odds"** (the statistics showcase), including the backtest and the rule-change scenario.
- [ ] Architecture post or section: why a graph, and what MCP adds.
- [ ] README polish: demo GIF, architecture diagram, data credits.
- [ ] Feature it as the flagship project in the website revamp.

## Phase 6: After the draw · Feb – May 2027

- [ ] When 2027 results are published, score the predictions: a true out-of-sample test and a natural follow-up post.
- [ ] Refresh the demand model with 2027 data.
- [ ] Trip-prep mode: update condition odds as spring snowpack data comes in; add live weather near launch.
- [ ] Consider expanding beyond the starting rivers.

---

## Scope

Start with **4–6 rivers**, for example:

- Desolation/Gray (Green River, UT)
- Westwater (Colorado River, UT)
- Gates of Lodore / Yampa (Dinosaur National Monument)
- **Middle Fork Salmon** (ID): the marquee river

### Reference odds (from planning notes; re-verify against sources in Phase 1)

| River | Figure |
|---|---|
| Desolation/Gray | ~11,000 applications for ~674 permits (~6%) |
| Smith River (MT), 2026 | ~8.6% overall; June 15 at 1.87% |
| Middle Fork Salmon | ~1.8% in 2025; applicants 11,611 (2016) → 21,098 (2026) |

## Open questions

- Which rivers to start with? Firsthand experience on any of them is worth weaving into the write-up.
- Is the Dec 1 odds-table milestone realistic, or should v0.1 slip to mid-December?
- Which license?
- Will the 2027-season lottery rules (especially Four Rivers) be final before Dec 1?

## Data credits

- Flow data: U.S. Geological Survey (public domain)
- Permit and facility data: Recreation.gov RIDB
- Lottery statistics: compiled from managing-agency publications (sources listed per row)
