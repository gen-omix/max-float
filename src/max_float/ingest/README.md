# ingest

Loads sourced data for each river into the graph. Every number traces to a source URL.

## Rivers

Every river in [Permit Lottery for Rafting Western Rivers](https://www.mountainzone.com/whitewater/permit-lottery-run-down-for-rivers-of-the-west/), except the Grand Canyon and the Smith.

| River | Odds in the article |
|---|---|
| Middle Fork Salmon | 3.33% |
| Main Salmon | 3.88% |
| Selway | 1.56% |
| Snake - Hells Canyon | 12.91% |
| Rogue | 30% |
| Green - Gates of Lodore | 4.28% |
| Yampa | 4.28% |
| San Juan | 8% |
| Green - Desolation/Gray | N/A |
| Rio Chama | N/A |
| Salt | N/A |

Out of scope:

- Colorado - Grand Canyon: excluded.
- Smith: excluded.

The article was published in January 2017 and updated in December 2023. Its odds are averages, not odds for a launch, so they are reference figures to check against agency results, not inputs.

## RIDB

| River | RIDB name | RIDB ID |
|---|---|---|
| Middle Fork Salmon | [Middle Fork Of The Salmon (4 Rivers)](https://www.recreation.gov/permits/234623) | 234623 |
| Main Salmon | [Salmon River (4 Rivers)](https://www.recreation.gov/permits/234622) | 234622 |
| Selway | [Selway River (4 Rivers)](https://www.recreation.gov/permits/234624) | 234624 |
| Snake - Hells Canyon | [Hells Canyon - Snake River (4 Rivers)](https://www.recreation.gov/permits/234625) | 234625 |
| Rogue | [Rogue River Wild Section](https://www.recreation.gov/permits/251982) | 251982 |
| Green - Gates of Lodore | [Dinosaur Green And Yampa River Permits](https://www.recreation.gov/permits/250014) | 250014 |
| Yampa | [Dinosaur Green And Yampa River Permits](https://www.recreation.gov/permits/250014) | 250014 |
| San Juan | [San Juan River Permit Lottery And Reservations](https://www.recreation.gov/permits/250986) | 250986 |
| Green - Desolation/Gray | [Desolation Gray - Green River Permit](https://www.recreation.gov/permits/233393) | 233393 |
| Rio Chama | [Rio Chama Wild and Scenic River Permits](https://www.recreation.gov/permits/621743) | 621743 |
| Salt | [Salt River Canyon Wilderness Permit](https://www.recreation.gov/permits/249275) | 249275 |

## Data

| File | Built by | Rows |
|---|---|---|
| `data/applications.csv` | `uv run python -m max_float.ingest.reservations` | Lottery applications and permits per launch as RIDB records them, FY2019–FY2025 |
| `data/applications_cleaned.csv` | `uv run python -m max_float.ingest.clean` | `applications.csv`, cleaned |
| `data/rivers.csv` | `uv run python -m max_float.ingest.rivers` | One per river: RIDB permit, agency, section, point, the `config.YEAR` lottery's application window and season, USGS gauge, and flow categories |
| `data/odds.csv` | `uv run python -m max_float.odds` | Expected applications, permits and odds for each launch in the `config.YEAR` lottery |

Every row comes from `https://ridb.recreation.gov/downloads/reservations{FY}.zip`, where FY is the fiscal year (October to September) that holds the launch date: a launch on 2021-06-01 comes from `reservations2021.zip`, one on 2021-10-05 from `reservations2022.zip`. `applications.csv` keeps this URL in `source_url`; `applications_cleaned.csv` drops it. Files before FY2019 record issued permits only, not lottery applications, so the data starts there. The fiscal years read are `config.FISCAL_YEARS`.

The years, rivers, lottery rules, model settings, sources and file paths are in [config.py](../config.py).

Cleaning:

- Gates of Lodore and the Yampa share one lottery, 250014. Applications (numerator) are split with a mixture model, permits (denominator) by trip length: 5 nights or more is the Yampa. See [dinosaur.py](dinosaur.py).
- When every launch date with permits in a permit's fiscal year has an even count there was a glitch that resulted in RIDB recording each permit twice. In this situation, permits are halved to account for this data problem. See [clean.py](clean.py).
- With `config.SEASON_ONLY`, on by default, only launches in their river's lottery season are kept. That drops the permits issued first-come for the rest of the year. No launch outside the seasons had lottery applications.

`rivers.csv`:

- `ridb_name`, `agency`, `latitude` and `longitude` come from `https://ridb.recreation.gov/api/v1/facilities/{ridb_id}` and its `permitentrances`. The point is the river's own permit entrance where RIDB locates one, Gates of Lodore and Deerlodge Park for the Yampa, and otherwise the permit's point, which RIDB does not define. RIDB has no put-in or take-out fields.
- `year` is `config.YEAR`. `uv run python -m max_float.ingest.rivers 2028` writes another year.
- The window and season are projected from calendar rules in [config.py](../config.py). The seasons are the first and last launch dates with lottery applications in `applications_cleaned.csv`, 2019–2025, and the window is when those applications were submitted in FY2024 and FY2025, in Pacific time. The exception is the Rio Chama's season end, which is from the [2027 Recreation.gov calendar](https://www.recreation.gov/permits/621743). Its launches with applications ended between September 9 and 15 every year.
- The data departs from the rules only on the Rogue's 2019 end (October 12), its 2021 start (May 22), and the Selway's 2021 and 2022 starts (May 29 and May 16).
- `section` is the usual lottery section, from `config.SECTIONS`.
- `gauge_id` is the river's USGS gauge, from `config.GAUGES`, and `gauge_name` is its USGS site name.
- Each flow category in `config.FLOW_CATEGORIES` has a `_cfs` range at the gauge, from `config.FLOWS`, and a `_share`: the share of lottery-season days in `config.FLOW_YEARS` with a mean daily flow in that range. Daily flows come from `https://waterservices.usgs.gov/nwis/dv/`, parameter 00060 (discharge), statistic 00003 (daily mean). Days USGS has no value for are left out.

`odds.csv`, after `applications_cleaned.csv`:

- `applications` and `permits` are what each launch can expect at the most recent season's level, and `odds` is permits over applications. See [odds.py](../odds.py).
- Each weekday's factor on applications is fitted with a level for each week of each season. Past launches are matched by day of the season with the weekday factor removed, then each season is scaled so its mean applications and permits per launch match the most recent season's. The launch's own weekday factor is applied last.
- `odds_low` and `odds_high` are a 90% interval from 1,000 resamples of the day's past seasons. With seven or fewer seasons a day, the interval understates the uncertainty, and it leaves out the uncertainty in the weekday factors and in the scaling.
- `scale_2025`, named for the most recent season, is that season's overall odds: its permits over its applications on its lottery launches. It is the level every launch's odds are scaled to, so it is the same for every launch of a river.
- A day is a launch only if it was a lottery launch in at least half of the river's past seasons. That leaves out the Selway's recurring non-lottery dates and the Rio Chama's rarer Saturdays.
- Rogue permits, odds, interval and scale are blank, as RIDB has almost no Rogue permits.
- `uv run python -m max_float.odds 2028` writes another year.

## Odds compared with the article

Overall odds for a season are its permits on lottery dates, those with at least one application, over its applications: `odds.season_odds` on `applications_cleaned.csv`. The article gives no year for its figures; 2019 is the earliest season RIDB has lottery applications for.

| River | Article | 2019 | 2025 | 2019–2025 mean |
|---|---|---|---|---|
| Middle Fork Salmon | 3.33% | 5.65% | 5.06% | 4.99% |
| Main Salmon | 3.88% | 6.77% | 4.71% | 5.01% |
| Selway | 1.56% | 1.56% | 1.03% | 1.04% |
| Snake - Hells Canyon | 12.91% | 11.80% | 6.82% | 7.45% |
| Rogue | 30% | N/A | N/A | N/A |
| Green - Gates of Lodore | 4.28% | 6.11% | 5.62% | 6.16% |
| Yampa | 4.28% | 1.11% | 1.12% | 0.99% |
| Gates of Lodore and Yampa combined | 4.28% | 3.69% | 3.94% | 4.07% |
| San Juan | 8% | 12.94% | 9.09% | 9.17% |
| Green - Desolation/Gray | N/A | 15.90% | 7.40% | 9.34% |
| Rio Chama | N/A | N/A | 3.53% | 3.41% (2020–2025) |
| Salt | N/A | 18.25% | 4.68% | 11.61% (no 2021) |

- Permits include trips rebooked after cancellations, so these odds run above lottery-only odds.
- Rogue permits are almost absent from RIDB, so its odds are N/A.
- The article gives one figure for Gates of Lodore and the Yampa, which share a lottery; compare it with the combined row. The per-river odds rest on the mixture-model split.
- Rio Chama has no lottery applications in RIDB before 2020, and the Salt none for 2021.
- Dinosaur's FY2019–FY2021 permits were recorded twice and are halved. FY2019's halved total is about half a normal year, so its 2019 odds may be low.

## Credits

Applications and permits: [Recreation.gov RIDB historical reservations](https://ridb.recreation.gov/download).

River list and reference odds: Matthew Bean, [Permit Lottery for Rafting Western Rivers](https://www.mountainzone.com/whitewater/permit-lottery-run-down-for-rivers-of-the-west/), Mountain Zone.
