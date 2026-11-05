"""Daily flows at USGS gauges, from USGS Water Services."""

import datetime
import json
import urllib.request

from max_float import config


def parse(data: dict) -> tuple[str, dict[datetime.date, float]]:
    """A gauge's name and its daily flows in cfs from a Water Services response,
    skipping missing days."""
    series = data["value"]["timeSeries"][0]
    flows = {
        datetime.date.fromisoformat(day["dateTime"][:10]): float(day["value"])
        for day in series["values"][0]["value"]
        if float(day["value"]) >= 0
    }
    return series["sourceInfo"]["siteName"], flows


def daily(site: str, years: range) -> tuple[str, dict[datetime.date, float]]:
    """A gauge's name and its mean daily flow in cfs on each day of `years`."""
    start, end = f"{years[0]}-01-01", f"{years[-1]}-12-31"
    url = config.USGS_DAILY.format(site=site, start=start, end=end)
    with urllib.request.urlopen(url, timeout=120) as response:
        return parse(json.load(response))
