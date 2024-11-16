import argparse

from pprint import pprint

from src.nws import NWSClient
from src.params import *
from src.file_utils import safe_open_dir

parser = argparse.ArgumentParser(description="Download data from the internet")
parser.add_argument(
    "station_id",
    type=StationID,
    choices=list(StationID),
)
parser.add_argument(
    "-r",
    "--radius",
    type=int,
    default=25,
    help="Radius in miles from the center of the area of interest",
)
parser.add_argument(
    "-co",
    "--cli_output_dir",
    type=safe_open_dir,
    default=CLI_OBSERVATIONS,
    help="Directory to save downloaded CLI data",
)


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

    # Download all past CLI data for our specified station
    res = nws.download_cli_data(args.station_id, safe_open_dir(args.cli_output_dir))
    print(
        f"Downloaded {len(res.downloaded_filepaths)} versions of CLI data for {args.station_id}"
    )
    print(f"Wrote {len(res.written_filepaths)} files to {args.cli_output_dir}")
