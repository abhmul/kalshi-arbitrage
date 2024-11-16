import argparse

from pprint import pprint

from src.nws import NWSClient
from src.params import *

parser = argparse.ArgumentParser(description="Download data from the internet")
parser.add_argument(
    "station_id",
    type=StationID,
    choices=[s.value for s in StationID],
)
parser.add_argument(
    "-r",
    "--radius",
    type=int,
    default=25,
    help="Radius in miles from the center of the area of interest",
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
    nws.
