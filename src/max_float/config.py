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

# Sources for each river's choices_per_application in LOTTERY_RULES. Four Rivers':
# a 2009 Forest Service notice, https://fs.usda.gov/media/45334, as no newer agency
# page states the number. The Dinosaur rivers': Colorado Whitewater,
# https://coloradowhitewater.org/river-trip-permits. The Desolation's: River
# Management Society,
# https://rms.memberclicks.net/assets/Permits/2021/green%20river%20-%20desolation%20gray%202021.pdf.
# The Salt's: https://discovergilacounty.com/salt-river-canyon-wilderness/.
RECREATION_GOV_PERMIT = "https://www.recreation.gov/permits/{ridb_id}"

# Each river's rules for non-commercial trips. None means no source we found
# states it.
# choices_per_application: launch dates one application can list. Where a source
#   says how they are drawn, each drawn application takes its first choice with
#   room, so its choices share one place in the draw.
# applications_per_person: per year. The Rio Chama draws its early season and its
#   release season separately, with one application for each.
# on_trip: who must be on the trip. "holder or alternate" is an alternate named on
#   the application.
# permits_per_person: per lottery season.
# launches_per_day: the Middle Fork's and Main Salmon's include commercial trips.
#   The Snake's are private launches only.
# max_trip_days: for the smallest groups, where the limit depends on group size.
#   The Gates of Lodore's and Yampa's are extended trips, which depend on
#   campsites: their normal trips are up to 4 and 5 days. DEFAULT_MAX_TRIP_DAYS is
#   for rivers with no stated limit. It is a default, not a rule: the Salt's permit
#   says it has no limit.
DEFAULT_MAX_TRIP_DAYS = 7
LOTTERY_RULES = {
    "Middle Fork Salmon": {
        "choices_per_application": 4,
        "applications_per_person": 1,
        "on_trip": "holder",
        "permits_per_person": 1,
        "launches_per_day": 7,
        "max_group": 24,
        "max_trip_days": 8,
    },
    "Main Salmon": {
        "choices_per_application": 4,
        "applications_per_person": 1,
        "on_trip": "holder",
        "permits_per_person": 1,
        "launches_per_day": 8,
        "max_group": 30,
        "max_trip_days": 8,
    },
    "Selway": {
        "choices_per_application": 4,
        "applications_per_person": 1,
        "on_trip": "holder",
        "permits_per_person": None,
        "launches_per_day": 1,
        "max_group": 16,
        "max_trip_days": DEFAULT_MAX_TRIP_DAYS,
    },
    "Snake - Hells Canyon": {
        "choices_per_application": 4,
        "applications_per_person": 1,
        "on_trip": None,
        "permits_per_person": None,
        "launches_per_day": 3,
        "max_group": 24,
        "max_trip_days": DEFAULT_MAX_TRIP_DAYS,
    },
    "Rogue": {
        "choices_per_application": None,
        "applications_per_person": 1,
        "on_trip": None,
        "permits_per_person": None,
        "launches_per_day": None,
        "max_group": None,
        "max_trip_days": DEFAULT_MAX_TRIP_DAYS,
    },
    "Green - Gates of Lodore": {
        "choices_per_application": 4,
        "applications_per_person": 1,
        "on_trip": "holder",
        "permits_per_person": 1,
        "launches_per_day": None,
        "max_group": 25,
        "max_trip_days": 5,
    },
    "Yampa": {
        "choices_per_application": 4,
        "applications_per_person": 1,
        "on_trip": "holder",
        "permits_per_person": 1,
        "launches_per_day": None,
        "max_group": 25,
        "max_trip_days": 6,
    },
    "San Juan": {
        "choices_per_application": None,
        "applications_per_person": None,
        "on_trip": "holder or alternate",
        "permits_per_person": None,
        "launches_per_day": None,
        "max_group": 25,
        "max_trip_days": DEFAULT_MAX_TRIP_DAYS,
    },
    "Green - Desolation/Gray": {
        "choices_per_application": 4,
        "applications_per_person": 1,
        "on_trip": "holder or alternate",
        "permits_per_person": None,
        "launches_per_day": 6,
        "max_group": 25,
        "max_trip_days": 9,
    },
    "Rio Chama": {
        "choices_per_application": None,
        "applications_per_person": 2,
        "on_trip": "holder",
        "permits_per_person": 1,
        "launches_per_day": None,
        "max_group": 16,
        "max_trip_days": DEFAULT_MAX_TRIP_DAYS,
    },
    "Salt": {
        "choices_per_application": 3,
        "applications_per_person": 1,
        "on_trip": "holder",
        "permits_per_person": None,
        "launches_per_day": 4,
        "max_group": 15,
        "max_trip_days": DEFAULT_MAX_TRIP_DAYS,
    },
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

# (latitude, longitude) for rivers whose RIDB point is not on their section. Every
# other river uses RIDB's. The Selway's is its Paradise put-in, as RIDB's is at a ranger station about 400 m above it.
# The San Juan's is its Sand Island put-in, from RIDB facility 251941, as RIDB's
# permit point is about 115 km west of it.
POINTS = {
    "Selway": (45.8606, -114.7440),
    "San Juan": (37.2630556, -109.6122222),
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
# statistic 00003) from USGS Water Services, over these calendar years. Daily
# highs and lows cover the same years.
USGS_DAILY = (
    "https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}"
    "&parameterCd=00060&statCd=00003&startDT={start}&endDT={end}"
)
FLOW_YEARS = range(2015, 2026)

# Daily highs and lows in degrees F from NOAA GHCN-Daily, including its quality
# flags. A river's station is the closest to its point in rivers.csv that is
# within STATION_ELEVATION meters of the point's USGS elevation and has a high and
# a low on at least STATION_COVERAGE of its lottery-season days in every year.
# Each temperature category is 10 degrees F, and a kilometer of elevation is about
# 12, so the closest station alone can be a mountain site a category colder. Any
# coverage from 0.56 to 0.75 picks the same stations.
NOAA_STATIONS = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
NOAA_INVENTORY = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt"
NOAA_DAILY = (
    "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries"
    "&stations={station}&startDate={start}&endDate={end}&dataTypes=TMAX,TMIN"
    "&format=json&units=standard&includeAttributes=true"
)
USGS_ELEVATION = (
    "https://epqs.nationalmap.gov/v1/json?x={longitude}&y={latitude}"
    "&units=Meters&wkid=4326"
)
STATION_ELEVATION = 200
STATION_COVERAGE = 0.7

# Temperature categories, from coldest to hottest, and the daily high in degrees F
# where each category after "cold" starts.
TEMPERATURE_CATEGORIES = ("cold", "cool", "mild", "warm", "hot", "extra hot")
TEMPERATURE_STARTS = (60, 70, 80, 90, 100)

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
CONDITIONS_CSV = Path("data/conditions.csv")
