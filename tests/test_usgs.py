from datetime import date

from max_float.ingest import usgs

RESPONSE = {
    "value": {
        "timeSeries": [
            {
                "sourceInfo": {"siteName": "SALT RIVER NEAR CHRYSOTILE, AZ"},
                "values": [
                    {
                        "value": [
                            {"dateTime": "2025-03-01T00:00:00.000", "value": "812"},
                            {"dateTime": "2025-03-02T00:00:00.000", "value": "-999999"},
                            {"dateTime": "2025-03-03T00:00:00.000", "value": "790.5"},
                        ]
                    }
                ],
            }
        ]
    }
}


def test_parse_skips_missing_days():
    assert usgs.parse(RESPONSE) == (
        "SALT RIVER NEAR CHRYSOTILE, AZ",
        {date(2025, 3, 1): 812.0, date(2025, 3, 3): 790.5},
    )
