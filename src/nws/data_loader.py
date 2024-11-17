from io import StringIO
from typing import Any, cast
import requests  # type: ignore[import-untyped]
from datetime import datetime, date, timedelta
from dateutil import parser
import re
import pytz
from collections import defaultdict

from cachetools import cached, TTLCache  # type: ignore[import-untyped]
from urlpath import URL  # type: ignore[import-untyped]
import pandas as pd
from tqdm import tqdm  # type: ignore[import-untyped]

from ..params import *
from ..file_utils import pathlike, safe_open_dir, glob

from .dataclasses import *
from .utils import normalize_time_str
from .cli import cli_path, parse_product_text, parse_cli_path


class NWSDataLoader:

    @staticmethod
    def load_clis(station: StationID, start: date, end: date, output_dir):
        cli_station_dir = CLI_OBSERVATIONS / str(station)
        if not cli_station_dir.exists():
            raise FileNotFoundError(
                f"Station {station} not found in {CLI_OBSERVATIONS}"
            )

        cli_file_pattern = cli_path(station=station, output_dir=output_dir)
        cli_file_paths = glob(cli_file_pattern)  # type: ignore[type-var]

        cli_file_paths = [
            cli_file_path
            for cli_file_path in cli_file_paths
            if start <= parse_cli_path(cli_file_path).summary_date <= end
        ]

        clis = []
        for cli_file_path in cli_file_paths:
            with open(cli_file_path, "r") as f:
                clis.append(parse_product_text(f.read()))

        return clis
