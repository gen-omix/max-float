# ingest

Loads sourced data for each river into the graph. Every number traces to a source URL.

## Rivers

Every river with lottery odds in [Permit Lottery for Rafting Western Rivers](https://www.mountainzone.com/whitewater/permit-lottery-run-down-for-rivers-of-the-west/), except the Grand Canyon and the Smith.

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

Out of scope:

- Colorado – Grand Canyon: excluded.
- Smith: excluded.
- Green – Desolation/Gray, Rio Chama, Salt: no data in the article.

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

## Data

| File | Built by | Rows |
|---|---|---|
| `data/applications.csv` | `uv run python -m max_float.ingest.reservations` | Lottery applications and permits per launch as RIDB records them, for the last five published fiscal years |
| `data/applications_cleaned.csv` | `uv run python -m max_float.ingest.clean` | `applications.csv`, cleaned |

Every row comes from `https://ridb.recreation.gov/downloads/reservations{FY}.zip`, where FY is the fiscal year (October to September) that holds the launch date: a launch on 2021-06-01 comes from `reservations2021.zip`, one on 2021-10-05 from `reservations2022.zip`. `applications.csv` keeps this URL in `source_url`; `applications_cleaned.csv` drops it.

Cleaning:

- Gates of Lodore and the Yampa share one lottery, 250014. Applications are split with a mixture model, permits by trip length: 5 nights or more is the Yampa. See [dinosaur.py](dinosaur.py).
- When every launch date with permits in a permit's fiscal year has an even count, RIDB recorded each permit twice, and permits are halved. See [clean.py](clean.py).

## Credits

Applications and permits: [Recreation.gov RIDB historical reservations](https://ridb.recreation.gov/download).

River list and reference odds: Matthew Bean, [Permit Lottery for Rafting Western Rivers](https://www.mountainzone.com/whitewater/permit-lottery-run-down-for-rivers-of-the-west/), Mountain Zone.
