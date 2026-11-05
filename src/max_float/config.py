"""Fixed inputs: the rivers, their lottery rules, the years, the model's settings,
the sources and the data files."""

from calendar import FRIDAY, MONDAY, SATURDAY
from pathlib import Path

# The lottery to predict.
YEAR = 2027

# RIDB reservation files to read, by fiscal year (October to September). Files
# before FY2019 have no lottery applications.
FISCAL_YEARS = range(2019, 2026)

# Each river's RIDB permit ID. Gates of Lodore and the Yampa share one lottery.
RIVERS = {
    "Middle Fork Salmon": 234623,
    "Main Salmon": 234622,
    "Selway": 234624,
    "Snake - Hells Canyon": 234625,
    "Rogue": 251982,
    "Green - Gates of Lodore": 250014,
    "Yampa": 250014,
    "San Juan": 250986,
    "Green - Desolation/Gray": 233393,
    "Rio Chama": 621743,
    "Salt": 249275,
}

# Dates are (month, day), or (month, weekday, n) for the nth weekday of the month.
# Applications open the year before the lottery and close in its year.
OPENS = (12, 1)
DEADLINE = (1, 31)

# Each river's first and last lottery launch dates. They are the first and last
# launches with applications in RIDB, 2019-2025, except the Rio Chama's end,
# which is from the 2027 Recreation.gov calendar.
SEASONS = {
    "Middle Fork Salmon": ((5, 28), (9, 3)),
    "Main Salmon": ((6, 20), (9, 7)),
    "Selway": ((5, 15), (7, 31)),
    "Snake - Hells Canyon": ((5, FRIDAY, 4), (9, 10)),
    "Rogue": ((5, 15), (10, 15)),
    "Green - Gates of Lodore": ((5, MONDAY, 2), (9, FRIDAY, 2)),
    "Yampa": ((5, MONDAY, 2), (7, SATURDAY, 2)),
    "San Juan": ((4, 15), (7, 15)),
    "Green - Desolation/Gray": ((5, 1), (9, 30)),
    "Rio Chama": ((4, FRIDAY, 3), (9, 15)),
    "Salt": ((3, 1), (5, 15)),
}

# Keep only launches in their river's lottery season in applications_cleaned.csv,
# leaving out permits for the rest of the year.
SEASON_ONLY = True

# Dinosaur permits for trips of this many nights or more are for the Yampa.
YAMPA_NIGHTS = 5

# A permit's fiscal year was recorded twice if every launch with permits has an
# even count, over at least this many launches.
DOUBLED_LAUNCHES = 20

# A day is a lottery launch if it was one in at least this share of past seasons.
LAUNCH_SHARE = 0.5

# The odds' interval, in percent, and how many resamples estimate it.
INTERVAL = 90
DRAWS = 1000

# Credentials come from the environment. Where one is missing, it is read from
# the file here, if set: KEY=VALUE lines, like the file Neo4j Aura downloads,
# with RIDB_API_KEY for RIDB and NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD
# for Neo4j. AWS_CREDENTIALS is an AWS shared credentials file. Keep these files
# outside the repository.
RIDB_CREDENTIALS: Path | None = None
NEO4J_CREDENTIALS: Path | None = None
AWS_CREDENTIALS: Path | None = None

# The AWS Secrets Manager secret Neo4j's credentials come from when neither the
# environment nor NEO4J_CREDENTIALS has them.
NEO4J_SECRET = "maxfloat/neo4j-kg"

RIDB_API = "https://ridb.recreation.gov/api/v1"
RESERVATIONS = "https://ridb.recreation.gov/downloads/reservations{year}.zip"

APPLICATIONS_CSV = Path("data/applications.csv")
CLEANED_CSV = Path("data/applications_cleaned.csv")
RIVERS_CSV = Path("data/rivers.csv")
ODDS_CSV = Path("data/odds.csv")
