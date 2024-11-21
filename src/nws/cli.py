"""
Utilities for manipulation of NWS CLIs
"""

import re
from datetime import date, datetime, time, timedelta
from dateutil import parser
from pathlib import Path

from ..params import *
from .dataclasses import *
from ..file_utils import glob, pathlike
from .utils import normalize_time_str, in_date_range


def cli_path(
    station: StationID | None = None,
    issuance_datetime: datetime | None = None,
    summary_date: date | None = None,
    output_dir: Path = CLI_OBSERVATIONS,
) -> Path:
    """
    For arguments that are not provided, uses a wildcard instead.
    """
    return (
        output_dir
        / str(station)
        / (
            f"cli.{station if station is not None else '*'}."
            f"issued-{issuance_datetime.strftime(PATH_DATETIME_FORMAT) if issuance_datetime is not None else '*'}"
            f".summary-{summary_date.strftime(PATH_DATE_FORMAT) if summary_date is not None else '*'}.txt"
        )
    )


@pathlike("cli_path")
def parse_cli_path(cli_path: Path) -> CLIPathParse:
    """
    Parse a CLI file path to extract the station, issuance time, and summary date.
    """
    parts = cli_path.stem.split(".")
    station = StationID(parts[1])
    assert cli_path.parent.name == str(station)
    issuance_time = datetime.strptime(
        parts[2].removeprefix("issued-"), PATH_DATETIME_FORMAT
    )
    issuance_time = STATION_TZ[station].localize(issuance_time)
    summary_date = datetime.strptime(
        parts[3].removeprefix("summary-"), PATH_DATE_FORMAT
    ).date()
    return CLIPathParse(
        station=station,
        issuance_time=issuance_time,
        summary_date=summary_date,
        output_dir=cli_path.parent.parent,
        path=cli_path,
    )


def load_clis(
    station: StationID,
    start: date | None = None,
    end: date | None = None,
    output_dir: Path = CLI_OBSERVATIONS,
) -> list[CLI]:
    cli_station_dir = output_dir / str(station)
    if not cli_station_dir.exists():
        raise FileNotFoundError(f"Station {station} not found in {output_dir}")

    cli_file_pattern = cli_path(station=station, output_dir=output_dir)
    cli_file_paths = glob(cli_file_pattern)

    cli_file_paths = [
        cli_file_path
        for cli_file_path in cli_file_paths
        if in_date_range(
            parse_cli_path(cli_file_path).summary_date, start=start, end=end
        )
    ]

    clis = []
    for cli_file_path in cli_file_paths:
        with open(cli_file_path, "r") as f:
            clis.append(parse_product_text(f.read()))

    return clis


def parse_product_text(
    product_text: str,
) -> CLI:
    # Extract relevant sections using regular expressions

    lines = product_text.splitlines()

    # Extract the site - line 1
    line_i = 0
    site_re = re.compile(r"CDUS\d+\sK([A-Z]{3})")
    while (match := re.search(site_re, lines[line_i])) is None:
        line_i += 1
        if line_i >= len(lines):
            raise ValueError("Could not find the site in the product text")
    site = match.group(1)
    line_i += 1

    station_re = re.compile(r"CLI([A-Z]{3})")
    while (match := re.search(station_re, lines[line_i])) is None:
        line_i += 1
        if line_i >= len(lines):
            raise ValueError("Could not find the station in the product text")
    station = StationID(match.group(1))
    line_i += 1

    # Check integrity of following lines
    assert lines[line_i].strip() == ""
    line_i += 1
    assert lines[line_i].strip().startswith("CLIMATE REPORT")
    line_i += 1
    assert lines[line_i].strip().startswith("NATIONAL WEATHER SERVICE")
    line_i += 1

    # Extract the issuance datetime
    # Add a colon to the issuance datetime string
    split_issuance = lines[line_i].split()
    if len(split_issuance[0]) == 3:
        split_issuance[0] = "0" + split_issuance[0]
    split_issuance[0] = split_issuance[0][:2] + ":" + split_issuance[0][2:]
    issuance_datetime = parser.parse(" ".join(split_issuance), ignoretz=True)
    issuance_datetime = STATION_TZ[station].localize(issuance_datetime)
    line_i += 1

    # Summary date
    summary_date_re = re.compile(r"CLIMATE\sSUMMARY\sFOR\s(.+?)\.\.\.")
    while (match := re.search(summary_date_re, lines[line_i])) is None:
        line_i += 1
        if line_i >= len(lines):
            raise ValueError("Could not find the summary date in the product text")
    summary_date = parser.parse(match.group(1)).date()
    line_i += 1

    # Valid time if it is there - line 11
    valid_datetime = None
    if "VALID" in lines[line_i]:
        match = re.search(r"AS\s+OF\s+(\d{4}\s+(AM|PM))\s+LOCAL\s+TIME", lines[line_i])
        assert match is not None
        valid_time = datetime.strptime(match.group(1), "%I%M %p").time()
        valid_datetime = datetime.combine(summary_date, valid_time)
        valid_datetime = STATION_TZ[station].localize(valid_datetime)
        line_i += 1

    # Extract the temperature data
    temp_re = re.compile(r"TEMPERATURE\s+\(F\)")
    while (match := re.search(temp_re, lines[line_i])) is None:
        line_i += 1
        if line_i >= len(lines):
            raise ValueError("Could not find the temperature data in the product text")
    line_i += 1

    if (issuance_datetime.date() - summary_date) == timedelta(days=1):
        assert "YESTERDAY" == lines[line_i].strip()
    elif (issuance_datetime.date() - summary_date) == timedelta(days=0):
        assert "TODAY" == lines[line_i].strip()
    else:
        raise ValueError("Could not find the correct day for the temperature data")
    line_i += 1

    # Maximum
    match = re.search(
        r"MAXIMUM\s+(\d+|(MM))R?\s+((\d{1,2}:?\d{2}\s(PM|AM))|(MM))", lines[line_i]
    )
    assert match is not None
    if match.group(1) == "MM":
        max_temp = None
    else:
        max_temp = int(match.group(1))
    if match.group(3) == "MM":
        max_temp_datetime = None
    else:
        max_temp_time_str = normalize_time_str(match.group(3))
        max_temp_time = datetime.strptime(max_temp_time_str, "%I:%M %p").time()
        max_temp_datetime = STATION_TZ[station].localize(
            datetime.combine(summary_date, max_temp_time)
        )
    line_i += 1

    # Minimum
    min_re = re.compile(r"MINIMUM\s+(\d+|(MM))R?\s+((\d{1,2}:?\d{2}\s(PM|AM))|(MM))")
    tod_yest_re = re.compile(r"(TODAY|YESTERDAY)")
    while (match := re.search(min_re, lines[line_i])) is None:
        line_i += 1
        if re.search(tod_yest_re, lines[line_i]) is not None or line_i >= len(lines):
            raise ValueError(
                "Could not find the minimum temperature data in the product text"
            )
    if match.group(1) == "MM":
        min_temp = None
    else:
        min_temp = int(match.group(1))
    if match.group(3) == "MM":
        min_temp_datetime = None
    else:
        min_temp_time_str = normalize_time_str(match.group(3))
        min_temp_time = datetime.strptime(min_temp_time_str, "%I:%M %p").time()
        min_temp_datetime = STATION_TZ[station].localize(
            datetime.combine(summary_date, min_temp_time)
        )
    line_i += 1

    # Average
    avg_re = re.compile(r"AVERAGE\s+(\d+|(MM))R?")
    while (match := re.search(avg_re, lines[line_i])) is None:
        line_i += 1
        if re.search(tod_yest_re, lines[line_i]) is not None or line_i >= len(lines):
            raise ValueError(
                "Could not find the average temperature data in the product text"
            )
    if match.group(1) == "MM":
        avg_temp = None
    else:
        avg_temp = int(match.group(1))
        line_i += 1

    # TODO Precipitation, Snowfall, Wind, Sky Cover, Weather Conditions, Relative Humidity

    is_correction = "CORRECTED" in product_text
    is_afternoon_report = valid_datetime is not None and valid_datetime.time() >= time(
        11, 0
    )

    return CLI(
        station=station,
        issuance_time=issuance_datetime,
        issuing_office=site,
        summary_date=summary_date,
        raw_text=product_text,
        is_afternoon_report=is_afternoon_report,
        max_temp=max_temp,
        max_temp_time=max_temp_datetime,
        min_temp=min_temp,
        min_temp_time=min_temp_datetime,
        avg_temp=avg_temp,
        valid_time=valid_datetime,
        is_correction=is_correction,
    )
