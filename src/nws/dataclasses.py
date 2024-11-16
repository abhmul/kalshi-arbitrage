from dataclasses import dataclass, replace
from datetime import datetime, date
from enum import Enum
from urlpath import URL  # type: ignore[import-untyped]


class TemperatureType(Enum):
    HIGH = "high"
    LOW = "low"

    def str(self):
        return self.value


@dataclass
class Forecast:
    lat: float
    lon: float
    polygon: list[list[float]]
    generated_at: datetime
    update_time: datetime
    start_time: datetime
    end_time: datetime
    date: date
    temperature: float
    temperature_type: TemperatureType


@dataclass
class CLIInfo:
    url: URL
    id: str
    wmo_collective_id: str
    issuing_office: str
    issuance_time: datetime


@dataclass
class CLI:
    issuance_time: datetime
    issuing_office: str
    summary_date: date
    raw_text: str
    max_temp: int
    max_temp_time: datetime
    min_temp: int
    min_temp_time: datetime
    avg_temp: int
    valid_time: datetime | None = None

    # precipitation: float | None = None
    # precipitation_month_to_date: float | None = None
    # precipitation_since_sep_1: float | None = None
    # precipitation_since_jan_1: float | None = None
    # highest_wind_speed: int | None = None
    # highest_wind_direction: str | None = None
    # highest_gust_speed: int | None = None
    # highest_gust_direction: str | None = None
    # average_wind_speed: float | None = None
    # average_sky_cover: float | None = None
    # highest_humidity: int | None = None
    # lowest_humidity: int | None = None
    # average_humidity: int | None = None

    def without_raw_text(self):
        return replace(self, raw_text="...")
