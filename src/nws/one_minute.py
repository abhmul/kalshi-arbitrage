from datetime import datetime, date, time, timedelta

import pandas as pd

from ..params import *
from ..file_utils import glob, pathlike
from ..pd_utils import load_csv

from .utils import has_date_intersection, in_date_range
from .dataclasses import *


SCHEMA = {
    "station": StationID,
    "station_name": pd.StringDtype,
    "valid": datetime,
    "valid(UTC)": datetime,  # Deprecated, remove when all files have been fixed
    "tmpf": pd.Int64Dtype,
}


def one_minute_path(
    station: StationID | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    output_dir: Path = ONE_MINUTE_OBSERVATIONS,
) -> Path:
    """
    For arguments that are not provided, uses a wildcard instead.
    """
    return (
        output_dir
        / str(station)
        / (
            f"one_minute.{station if station is not None else '*'}."
            f"start-{start.strftime(PATH_DATETIME_FORMAT) if start is not None else '*'}"
            f".end-{end.strftime(PATH_DATETIME_FORMAT) if end is not None else '*'}"
            ".csv"
        )
    )


@pathlike("one_minute_path")
def parse_one_minute_path(one_minute_path: Path) -> OneMinutePathParse:
    """
    Parse a one-minute file path to extract the station, start time, and end time.
    """
    parts = one_minute_path.stem.split(".")
    station = StationID(parts[1])
    assert one_minute_path.parent.name == str(station)
    start = STATION_TZ[station].localize(
        datetime.strptime(parts[2].removeprefix("start-"), PATH_DATETIME_FORMAT)
    )
    end = STATION_TZ[station].localize(
        datetime.strptime(parts[3].removeprefix("end-"), PATH_DATETIME_FORMAT)
    )
    return OneMinutePathParse(
        station=station,
        start=start,
        end=end,
        output_dir=one_minute_path.parent.parent,
        path=one_minute_path,
    )


def load_one_minutes(
    station: StationID,
    start: datetime | None = None,
    end: datetime | None = None,
    output_dir: Path = ONE_MINUTE_OBSERVATIONS,
) -> pd.DataFrame:
    one_minute_station_dir = output_dir / str(station)
    if not one_minute_station_dir.exists():
        raise FileNotFoundError(f"No one-minute data for station {station}")

    one_minute_pattern = one_minute_path(station=station, output_dir=output_dir)
    one_minute_paths = glob(one_minute_pattern)
    print(one_minute_paths)

    parsed_paths = [parse_one_minute_path(path) for path in one_minute_paths]
    one_minute_paths = [
        path
        for path, parsed_path in zip(one_minute_paths, parsed_paths)
        if has_date_intersection(start, end, parsed_path.start, parsed_path.end)
    ]

    one_minute_dfs = [
        load_csv(path, schema=SCHEMA, na_values=["M"]) for path in one_minute_paths
    ]

    # Fix the valid(UTC) column if it is there - this is something I forgot to do
    # when I originally downloaded the data
    for path, df in zip(one_minute_paths, one_minute_dfs):
        if "valid(UTC)" in df.columns:
            df["valid"] = df["valid(UTC)"]
            df.drop(columns=["valid(UTC)"], inplace=True)
            df.to_csv(path, index=False)

    # Now filter on the requested range and concatenate
    one_minute_dfs = [
        df[df["valid"].apply(lambda x: in_date_range(x, start, end))]
        for df in one_minute_dfs
    ]
    one_minute_df = pd.concat(one_minute_dfs, ignore_index=True).sort_values(by="valid")

    return one_minute_df
