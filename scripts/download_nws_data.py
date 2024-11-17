import argparse
from enum import Enum
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pprint import pprint

from tqdm import tqdm  # type: ignore[import-untyped]
import pandas as pd

from src.nws import NWSClient
from src.params import *
from src.file_utils import safe_open_dir


class DownloadMode(Enum):
    CLI = "cli"
    TEMP = "temp"
    ONE_MINUTE = "one_minute"


parser = argparse.ArgumentParser(description="Download data from the internet")

parser.add_argument(
    "mode",
    type=DownloadMode,
    choices=list(DownloadMode),
    help="What kind of data to download",
)
parser.add_argument(
    "station_ids",
    nargs="+",
    type=StationID,
    choices=list(StationID),
)
parser.add_argument(
    "-o",
    "--output_dir",
    type=Path,
    help="Directory to save downloaded data",
)

# For temp data
parser.add_argument(
    "-r",
    "--radius",
    type=int,
    default=25,
    help="Radius in miles from the center of the area of interest",
)

# For CLI data

# For 1 minute data and Temp data
parser.add_argument(
    "-s",
    "--start_month",
    type=str,
    help="First month to download for 1 minute data and temperature timeseries data. Written as 'YYYY-MM'",
)
parser.add_argument(
    "-e",
    "--end_month",
    type=str,
    help="Last month to download for 1 minute data and temperature timeseries data. Written as 'YYYY-MM'",
)


DEFAULT_OUTPUT_DIRS = {
    DownloadMode.CLI: CLI_OBSERVATIONS,
    DownloadMode.TEMP: TEMP_OBSERVATIONS,
    DownloadMode.ONE_MINUTE: ONE_MINUTE_OBSERVATIONS,
}


if __name__ == "__main__":
    args = parser.parse_args()
    pprint(args)

    nws = NWSClient()

    # What are we downloading
    # - All temp observing station data within a fixed radius
    # - All past CLI data that we can get
    # - All past 1 minute data we can get
    # Need to check what we have downloaded so far
    # Also keep track of the station specs when we add a new station

    if args.output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIRS[args.mode]
    else:
        output_dir = args.output_dir

    # Download all past CLI data for our specified station
    if args.mode == DownloadMode.CLI:
        for station_id in args.station_ids:
            print(f"Downloading CLI data for station {station_id}")
            res = nws.download_cli_data(station_id, safe_open_dir(output_dir))
            print(
                f"Downloaded {len(res.downloaded_filepaths)} versions of CLI data for {station_id}"
            )
            print(f"Wrote {len(res.written_filepaths)} files to {output_dir}")

    # Download all past 1 minute data for our specified station
    elif args.mode == DownloadMode.ONE_MINUTE:
        assert args.start_month is not None
        assert args.end_month is not None
        for station_id in args.station_ids:
            months = pd.period_range(
                start=args.start_month, end=args.end_month, freq="M"
            )
            for month in tqdm(months):
                print(f"Downloading one-minute data for {month}")
                start = month.to_timestamp()
                end = min(
                    month.to_timestamp() + relativedelta(months=1), datetime.today()
                )
                res = nws.download_one_minute_data(
                    station_id,
                    safe_open_dir(output_dir),
                    start=start,
                    end=end,
                )
                print(
                    f"Requested One-Minute Data from station {station_id} "
                    f"for timeframe {res.requested_start.isoformat()} to "
                    f"{res.requested_end.isoformat()}."
                )
                if res.true_start is not None:
                    assert res.true_end is not None
                    print(
                        f"Downloaded {res.num_rows} rows of 1 minute data from station "
                        f"{station_id} for timeframe {res.true_start.isoformat()} to "
                        f"{res.true_end.isoformat()}."
                    )
                    print(f"Wrote data to {output_dir}")
                else:
                    print(
                        f"No data available from station {station_id} for timeframe "
                        f"{res.requested_start.isoformat()} to {res.requested_end.isoformat()}."
                    )

    # Download all temp data within a fixed radius of a point
    elif args.mode == DownloadMode.TEMP:
        for station_id in args.station_ids:
            print(f"Downloading temperature timeseries data for station {station_id}")
            months = pd.period_range(
                start=args.start_month, end=args.end_month, freq="M"
            )
            prog = tqdm(months)
            num_downloaded = 0
            num_written = 0
            for month in prog:
                prog.set_postfix(month=month)
                prog.refresh()

                start = month.to_timestamp()
                end = min(
                    month.to_timestamp() + relativedelta(months=1), datetime.today()
                )
                res = nws.download_timeseries(
                    station_id,
                    output_dir=safe_open_dir(output_dir),
                    start=start,
                    end=end,
                    radius=args.radius,
                )
                num_downloaded += len(res.downloaded_filepaths)
                num_written += len(res.written_filepaths)

            print(
                f"Downloaded {num_downloaded} temp data for stations withing radius {args.radius} of {station_id}"
            )
            print(f"Wrote {num_written} files to {output_dir}.")

    else:
        raise NotImplementedError(f"Mode {args.mode} not implemented")
