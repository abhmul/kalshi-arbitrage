from dataclasses import dataclass, replace
from pathlib import Path
from datetime import datetime, date
from enum import Enum
from urlpath import URL  # type: ignore[import-untyped]

from ..params import StationID


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
    station: StationID
    issuance_time: datetime
    issuing_office: str
    summary_date: date
    raw_text: str
    is_afternoon_report: bool
    max_temp: int | None
    max_temp_time: datetime | None
    min_temp: int | None
    min_temp_time: datetime | None
    avg_temp: int | None
    valid_time: datetime | None = None
    is_correction: bool = False

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


@dataclass
class CLIPathParse:
    station: StationID
    issuance_time: datetime
    summary_date: date
    output_dir: Path
    path: Path


@dataclass
class DownloadCLIsResult:
    written_filepaths: list[Path]
    downloaded_filepaths: list[Path]


@dataclass
class OneMinutePathParse:
    station: StationID
    start: datetime
    end: datetime
    output_dir: Path
    path: Path


@dataclass
class DownloadOneMinuteResult:
    num_rows: int
    requested_start: datetime
    requested_end: datetime
    true_start: datetime | None
    true_end: datetime | None


@dataclass
class DownloadTimeseriesResult:
    requested_start: datetime
    requested_end: datetime
    written_filepaths: list[Path]
    downloaded_filepaths: list[Path]
