# ingest

Loads sourced data for each river into the graph. Every number traces to a source URL.

## Rivers

Every river in [Permit Lottery for Rafting Western Rivers](https://www.mountainzone.com/whitewater/permit-lottery-run-down-for-rivers-of-the-west/), except the Grand Canyon, the Smith and the Salt.

| River | Odds in the article |
|---|---|
| Middle Fork Salmon | 3.33% |
| Main Salmon | 3.88% |
| Selway | 1.56% |
| Snake – Hells Canyon | 12.91% |
| Rogue | 30% |
| Green – Gates of Lodore | 4.28% |
| Yampa | 4.28% |
| San Juan | 8% |
| Green – Desolation/Gray | N/A |
| Rio Chama | N/A |

Out of scope:

- Colorado – Grand Canyon: excluded.
- Smith: excluded.
- Salt: excluded.

The article was published in January 2017 and updated in December 2023. Its odds are averages, not odds for a launch, so they are reference figures to check against agency results, not inputs.

## RIDB

| River | RIDB name | RIDB ID |
|---|---|---|
| Middle Fork Salmon | [Middle Fork Of The Salmon (4 Rivers)](https://www.recreation.gov/permits/234623) | 234623 |
| Main Salmon | [Salmon River (4 Rivers)](https://www.recreation.gov/permits/234622) | 234622 |
| Selway | [Selway River (4 Rivers)](https://www.recreation.gov/permits/234624) | 234624 |
| Snake – Hells Canyon | [Hells Canyon - Snake River (4 Rivers)](https://www.recreation.gov/permits/234625) | 234625 |
| Rogue | [Rogue River Wild Section](https://www.recreation.gov/permits/251982) | 251982 |
| Green – Gates of Lodore | [Dinosaur Green And Yampa River Permits](https://www.recreation.gov/permits/250014) | 250014 |
| Yampa | [Dinosaur Green And Yampa River Permits](https://www.recreation.gov/permits/250014) | 250014 |
| San Juan | [San Juan River Permit Lottery And Reservations](https://www.recreation.gov/permits/250986) | 250986 |
| Green – Desolation/Gray | [Desolation Gray - Green River Permit](https://www.recreation.gov/permits/233393) | 233393 |
| Rio Chama | [Rio Chama Wild and Scenic River Permits](https://www.recreation.gov/permits/621743) | 621743 |

## Data

| File | Built by | Rows |
|---|---|---|
| `data/applications.csv` | `uv run python -m max_float.ingest.reservations 7` | Lottery applications and permits per launch as RIDB records them, FY2019–FY2025 |
| `data/applications_cleaned.csv` | `uv run python -m max_float.ingest.clean` | `applications.csv`, cleaned |

Every row comes from `https://ridb.recreation.gov/downloads/reservations{FY}.zip`, where FY is the fiscal year (October to September) that holds the launch date: a launch on 2021-06-01 comes from `reservations2021.zip`, one on 2021-10-05 from `reservations2022.zip`. `applications.csv` keeps this URL in `source_url`; `applications_cleaned.csv` drops it. Files before FY2019 record issued permits only, not lottery applications, so the data starts there. The argument to `reservations` is the number of fiscal years, counting back from the latest published; it defaults to 5.

Cleaning:

- Gates of Lodore and the Yampa share one lottery, 250014. Applications are split with a mixture model, permits by trip length: 5 nights or more is the Yampa. See [dinosaur.py](dinosaur.py).
- When every launch date with permits in a permit's fiscal year has an even count, RIDB recorded each permit twice, and permits are halved. See [clean.py](clean.py).

## Odds compared with the article

Overall odds for a season are its permits on lottery dates, those with at least one application, over its applications: `odds.season_odds` on `applications_cleaned.csv`. The article gives no year for its figures; 2019 is the earliest season RIDB has lottery applications for.

| River | Article | 2019 | 2025 | 2019–2025 mean |
|---|---|---|---|---|
| Middle Fork Salmon | 3.33% | 5.65% | 5.06% | 4.99% |
| Main Salmon | 3.88% | 6.77% | 4.71% | 5.01% |
| Selway | 1.56% | 1.56% | 1.03% | 1.04% |
| Snake – Hells Canyon | 12.91% | 11.80% | 6.82% | 7.45% |
| Rogue | 30% | N/A | N/A | N/A |
| Green – Gates of Lodore | 4.28% | 6.11% | 5.62% | 6.16% |
| Yampa | 4.28% | 1.11% | 1.12% | 0.99% |
| Gates of Lodore and Yampa combined | 4.28% | 3.69% | 3.94% | 4.07% |
| San Juan | 8% | 12.94% | 9.09% | 9.17% |
| Green – Desolation/Gray | N/A | 15.90% | 7.40% | 9.34% |
| Rio Chama | N/A | N/A | 3.53% | 3.41% (2020–2025) |

- Permits include trips rebooked after cancellations, so these odds run above lottery-only odds.
- Rogue permits are almost absent from RIDB, so its odds are N/A.
- The article gives one figure for Gates of Lodore and the Yampa, which share a lottery; compare it with the combined row. The per-river odds rest on the mixture-model split.
- Rio Chama has no lottery applications in RIDB before 2020.
- Dinosaur's FY2019–FY2021 permits were recorded twice and are halved. FY2019's halved total is about half a normal year, so its 2019 odds may be low.

## Credits

Applications and permits: [Recreation.gov RIDB historical reservations](https://ridb.recreation.gov/download).

River list and reference odds: Matthew Bean, [Permit Lottery for Rafting Western Rivers](https://www.mountainzone.com/whitewater/permit-lottery-run-down-for-rivers-of-the-west/), Mountain Zone.
