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

# Each river's usual lottery section, from put-in to take-out.
SECTIONS = {
    "Middle Fork Salmon": "Boundary Creek to Cache Bar",
    "Main Salmon": "Corn Creek to Long Tom Bar (trips usually end at Vinegar/Carey Creek)",
    "Selway": "Paradise to Selway Falls (Race Creek)",
    "Snake - Hells Canyon": "Hells Canyon Dam to Pittsburg Landing (Wild section)",
    "Rogue": "Grave Creek to Watson Creek (Wild section; trips run to Foster Bar)",
    "Green - Gates of Lodore": "Gates of Lodore to Split Mountain",
    "Yampa": "Deerlodge Park to Split Mountain",
    "San Juan": "Sand Island to Clay Hills",
    "Green - Desolation/Gray": "Sand Wash to Swasey's",
    "Rio Chama": "El Vado Ranch to Big Eddy (Wild and Scenic)",
    "Salt": "Gleason Flat to Highway 288 (Salt River Canyon Wilderness)",
}

# Each river's USGS gauge, where its flow is measured, by site number. Each was
# matched to its river by the USGS site name in the comment.
GAUGES = {
    "Middle Fork Salmon": "13309220",  # MF Salmon River at MF Lodge nr Yellow Pine ID
    "Main Salmon": "13317000",  # Salmon River at White Bird ID
    "Selway": "13336500",  # Selway River nr Lowell ID
    "Snake - Hells Canyon": "13290450",  # Snake River at Hells Canyon Dam ID-OR
    "Rogue": "14372300",  # Rogue River near Agness, OR
    "Green - Gates of Lodore": "09234500",  # Green River near Greendale, UT
    "Yampa": "09260050",  # Yampa River at Deerlodge Park, CO
    "San Juan": "09379500",  # San Juan River near Bluff, UT
    "Green - Desolation/Gray": "09315000",  # Green River at Green River, UT
    "Rio Chama": "08286500",  # Rio Chama above Abiquiu Reservoir, NM
    "Salt": "09497500",  # Salt River near Chrysotile, AZ
}

# Daily flows: each gauge's mean daily discharge in cfs (USGS parameter 00060,
# statistic 00003) from USGS Water Services, over these calendar years.
USGS_DAILY = (
    "https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}"
    "&parameterCd=00060&statCd=00003&startDT={start}&endDT={end}"
)
FLOW_YEARS = range(2015, 2026)

# Flow categories, from lowest to highest.
FLOW_CATEGORIES = (
    "not running",
    "extra low",
    "low",
    "normal",
    "high",
    "spicy high",
    "extra spicy high",
)

# Flow at each river's gauge, in cfs, where each category after "not running"
# starts. Extra low and extra spicy high are below and above the published
# recommended range. Within it, low, normal and high are set so each happens on
# a share of lottery-season days in FLOW_YEARS. Not running starts below half the
# recommended minimum. Spicy high starts at the geometric mean of high's start
# and the recommended maximum, to two significant figures.
FLOWS = {
    "Middle Fork Salmon": (350, 700, 1_500, 5_000, 7_100, 10_000),
    "Main Salmon": (1_000, 2_000, 5_000, 12_000, 17_000, 23_000),
    "Selway": (350, 700, 2_000, 10_000, 19_000, 35_000),
    "Snake - Hells Canyon": (3_500, 7_000, 11_000, 20_000, 40_000, 80_000),
    "Rogue": (600, 1_200, 2_000, 4_000, 11_000, 30_000),
    "Green - Gates of Lodore": (550, 1_100, 1_900, 4_000, 8_900, 20_000),
    "Yampa": (650, 1_300, 3_000, 10_000, 16_000, 25_000),
    "San Juan": (250, 500, 1_000, 3_000, 4_900, 8_000),
    "Green - Desolation/Gray": (450, 900, 2_500, 10_000, 22_000, 50_000),
    "Rio Chama": (100, 200, 500, 1_500, 2_100, 3_000),
    "Salt": (200, 400, 1_000, 3_000, 5_500, 10_000),
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

# Odds, from 0 to 1, are rounded to this many decimal places wherever they are
# written or returned. 4 is a hundredth of a percent.
ODDS_DIGITS = 4

# Credentials come from the environment. Where one is missing, it is read from
# the file here, if set: a JSON object or KEY=VALUE lines, like the file Neo4j
# Aura downloads, with RIDB_API_KEY for RIDB and NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD
# for Neo4j. AWS_CREDENTIALS is an AWS shared credentials file. Keep these files
# outside the repository.
RIDB_CREDENTIALS: Path | None = None
NEO4J_CREDENTIALS: Path | None = Path("~/.ssh/neo4j_float_max_creds.json")
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
