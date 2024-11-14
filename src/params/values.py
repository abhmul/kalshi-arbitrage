from urlpath import URL  # type: ignore[import-untyped]
from enum import Enum
import pytz

EP = 1e-5
PROD_API_BASE = URL("https://api.elections.kalshi.com/trade-api/v2")

# API IDs
DEMO_LEGACY_API_ID = "e8af6f9c-981e-4037-9b8f-2971b9dd4943"
DEMO_API_ID = "e4b4f20b-7100-4744-918d-adee3b1e44f2"
API_ID = "18b939a7-3413-4ec5-b942-5792c0f5b285"

# NWS API
NWS_API_BASE = URL("https://api.weather.gov")
NWS_POINTS = NWS_API_BASE / "points"
CLI_API_BASE = URL("https://api.weather.gov/products/types/CLI")
TIME_SERIES_BASE = URL("https://api.synopticdata.com/v2/stations/timeseries")

PUBLIC_TOKEN = "b950a4463c7e4053a4fcd1f1457fff17"

NYC = (40.7833546, -73.9649732)

# ACIS API
ACIS_API_BASE = URL("https://data.rcc-acis.org/")


class StationID(Enum):
    NYC = "NYC"  # New York, NY
    AUS = "AUS"  # Austin, TX
    MIA = "MIA"  # Miami, FL
    MDW = "MDW"  # Chicago, IL
    PIR = "PIR"  # Pierre, SD
    AW254 = "AW254"

    def __str__(self):
        return self.value


STATION_TZ = {
    StationID.NYC: pytz.timezone("America/New_York"),
    StationID.AUS: pytz.timezone("America/Chicago"),
    StationID.MIA: pytz.timezone("America/New_York"),
    StationID.MDW: pytz.timezone("America/Chicago"),
    StationID.PIR: pytz.timezone("America/Chicago"),
}

BASE_TZ = pytz.timezone("America/Chicago")
