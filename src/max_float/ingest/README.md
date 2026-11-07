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

The December 1 beta covers the ten rivers with odds. The Rogue stays in the data files, but it isn't in the beta until it has permit data. See [ROADMAP.md](../../../ROADMAP.md).

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
| `data/applications.csv` | `uv run python -m max_float.ingest.reservations` | Lottery applications and lottery permits per launch from RIDB, FY2019–FY2025 |
| `data/applications_cleaned.csv` | `uv run python -m max_float.ingest.clean` | `applications.csv`, cleaned |
| `data/rivers.csv` | `uv run python -m max_float.ingest.rivers` | One per river: RIDB permit, agency, section, point, the `config.YEAR` lottery's application window and season, USGS gauge, and flow categories |
| `data/conditions.csv` | `uv run python -m max_float.ingest.conditions` | One per river and day of `config.FLOW_YEARS`: flow at the river's USGS gauge, high and low at its NOAA station, and their categories. Needs `rivers.csv` |
| `data/odds.csv` | `uv run python -m max_float.odds` | Expected applications, permits and odds for each launch in the `config.YEAR` lottery |

Every row comes from `https://ridb.recreation.gov/downloads/reservations{FY}.zip`, where FY is the fiscal year (October to September) that holds the launch date: a launch on 2021-06-01 comes from `reservations2021.zip`, one on 2021-10-05 from `reservations2022.zip`. `applications.csv` keeps this URL in `source_url`; `applications_cleaned.csv` drops it. Files before FY2019 record issued permits only, not lottery applications, so the data starts there. The fiscal years read are `config.FISCAL_YEARS`.

The years, rivers, lottery rules, model settings, sources and file paths are in [config.py](../config.py).

Lottery permits:

- RIDB's permits include those taken first-come after the lottery and those rebooked after cancellations, about two in three on the Middle Fork. Only permits ordered after applications close and before the lottery's unclaimed permits are released count, on the lottery's clock: `seasons.lottery_permit`. Later permits went to people who didn't win, and none ordered before applications close are from the lottery.
- Each lottery's release day and clock are in `config.RELEASES`, from its agency or Recreation.gov, and the years it differed are in `config.RELEASED_ON`. Every year 2019–2025 has a rush of orders in RIDB on its release day, mostly at 8 or 9 AM: in 2025, 53 Middle Fork permits in the hour after 8 AM on March 16, and 236 Rio Chama permits on April 1. The Salt's winners pay by February 20 and the rest open at 8 AM on February 21.
- RIDB order times are UTC. A few are in year 1 and don't count.
- On the Middle Fork in 2025 that leaves 330 permits of 1,023, close to the 361 lottery permits [OARS](https://www.oars.com/blog/how-to-get-most-popular-private-river-permits) gives. The share left in 2025 runs from 21% on the Rio Chama to 71% on the Salt, and it's lower late in the season on most rivers, where more launches are rebooked.
- The Rogue has no release day, so it has no lottery permits.

Cleaning:

- Gates of Lodore and the Yampa share one lottery, 250014. Applications (numerator) are split with a mixture model, permits (denominator) by trip length: 5 nights or more is the Yampa. See [dinosaur.py](dinosaur.py).
- When every launch date with permits in a permit's fiscal year has an even count there was a glitch that resulted in RIDB recording each permit twice. In this situation, permits are halved to account for this data problem. See [clean.py](clean.py).
- With `config.SEASON_ONLY`, on by default, only launches in their river's lottery season are kept. That drops the permits issued first-come for the rest of the year. No launch outside the seasons had lottery applications.

`rivers.csv`:

- `ridb_name`, `agency`, `latitude` and `longitude` come from `https://ridb.recreation.gov/api/v1/facilities/{ridb_id}` and its `permitentrances`. The point is the river's own permit entrance where RIDB locates one, Gates of Lodore and Deerlodge Park for the Yampa, and otherwise the permit's point, which RIDB does not define. RIDB has no put-in or take-out fields. `config.POINTS` replaces RIDB's point where it isn't on the river's section: the Selway's and San Juan's put-ins.
- `year` is `config.YEAR`. `uv run python -m max_float.ingest.rivers 2028` writes another year.
- The window and season are projected from calendar rules in [config.py](../config.py). The seasons are the first and last launch dates with lottery applications in `applications_cleaned.csv`, 2019–2025, and the window is when those applications were submitted in FY2024 and FY2025, in Pacific time. The exception is the Rio Chama's season end, which is from the [2027 Recreation.gov calendar](https://www.recreation.gov/permits/621743). Its launches with applications ended between September 9 and 15 every year.
- The data departs from the rules only on the Rogue's 2019 end (October 12), its 2021 start (May 22), and the Selway's 2021 and 2022 starts (May 29 and May 16).
- `code` is the river's three-letter code, from `config.RIVER_CODES`.
- `section` is the usual lottery section, from `config.SECTIONS`.
- The lottery rules are from `config.LOTTERY_RULES`, for non-commercial trips, and its comments say what each one means. A blank means no source we found states it, except `max_trip_days`, which uses `config.DEFAULT_MAX_TRIP_DAYS` where no limit is stated. `rules_source` is the river's Recreation.gov permit page, which has most of them. Others come from its agency: launches per day from RIDB's permit description or the Forest Service, and the Rio Chama's two applications from the BLM. Recreation.gov doesn't state `choices_per_application` for any river, so the sources for those are in the comments in [config.py](../config.py).
- Only the Four Rivers' choices come from an agency, in a 2009 notice. The Dinosaur rivers', the Desolation's and the Salt's come from river and county sites, the Desolation's launches per day from a permit site, and the Salt's from the county site.
- `gauge_id` is the river's USGS gauge, from `config.GAUGES`, and `gauge_name` is its USGS site name.
- Each flow category in `config.FLOW_CATEGORIES` has a `_cfs` range at the gauge, from `config.FLOWS`, and a `_share`: the share of lottery-season days in `config.FLOW_YEARS` with a mean daily flow in that range. Daily flows come from `https://waterservices.usgs.gov/nwis/dv/`, parameter 00060 (discharge), statistic 00003 (daily mean). Days USGS has no value for are left out.

`conditions.csv`:

- `flow_cfs` is the gauge's mean daily flow, from the same USGS source as `rivers.csv`. `flow_step` and `flow_category` are its place on the flow scale in `config.FLOW_CATEGORIES`, using `config.FLOWS`. All three are blank on days USGS has no reading.
- `high_f` and `low_f` are the daily high and low at `station_id`, from [NOAA GHCN-Daily](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily). Readings that failed NOAA's quality checks are left blank, as are days with no reading. `temperature_step` and `temperature_category` place the day's high on the scale in `config.TEMPERATURE_CATEGORIES`.
- A river's station is the closest to its `latitude` and `longitude` in `rivers.csv` that is within `config.STATION_ELEVATION` meters of that point's USGS elevation and has a high and a low on at least `config.STATION_COVERAGE` of the river's lottery-season days in every year. The nearest station alone is often a mountain site: the Rogue's is 930 m above its point. The Snake's is 127 km from its point, as Riggins, the closest, is missing whole seasons.
- Join `rivers.csv` on `river`, and `applications_cleaned.csv` on `date` and `river`.
- Join `applications.csv` on `date` and `ridb_id`. It has one row a day for the lottery Gates of Lodore and the Yampa share, so each of those days joins to two rows here, one per river.

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
| Middle Fork Salmon | 3.33% | 2.36% | 1.67% | 1.73% |
| Main Salmon | 3.88% | 2.51% | 1.67% | 1.72% |
| Selway | 1.56% | 1.07% | 0.53% | 0.57% |
| Snake - Hells Canyon | 12.91% | 7.01% | 3.15% | 3.90% |
| Rogue | 30% | N/A | N/A | N/A |
| Green - Gates of Lodore | 4.28% | 3.68% | 1.85% | 2.31% |
| Yampa | 4.28% | 0.88% | 0.77% | 0.66% |
| Gates of Lodore and Yampa combined | 4.28% | 2.33% | 1.45% | 1.63% |
| San Juan | 8% | 5.10% | 2.87% | 3.49% |
| Green - Desolation/Gray | N/A | 4.60% | 2.59% | 3.11% |
| Rio Chama | N/A | N/A | 1.80% | 1.81% (2020–2025) |
| Salt | N/A | 10.55% | 3.35% | 6.45% (no 2021) |

- Permits are lottery permits, as above.
- Rogue permits are almost absent from RIDB, so its odds are N/A.
- The article gives one figure for Gates of Lodore and the Yampa, which share a lottery; compare it with the combined row. The per-river odds rest on the mixture-model split.
- Rio Chama has no lottery applications in RIDB before 2020, and the Salt none for 2021.
- Dinosaur's FY2019–FY2021 permits were recorded twice and are halved. FY2019's halved total is about half a normal year, so its 2019 odds may be low.

## Credits

Applications and permits: [Recreation.gov RIDB historical reservations](https://ridb.recreation.gov/download).

River list and reference odds: Matthew Bean, [Permit Lottery for Rafting Western Rivers](https://www.mountainzone.com/whitewater/permit-lottery-run-down-for-rivers-of-the-west/), Mountain Zone.
