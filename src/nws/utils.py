from datetime import date, datetime

from ..params import *

Datelike = date | datetime


def celsius_to_fahrenheit(celsius: float) -> float:
    """
    Convert a temperature from Celsius to Fahrenheit.
    """
    return celsius * 9 / 5 + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """
    Convert a temperature from Fahrenheit to Celsius.
    """
    return (fahrenheit - 32) * 5 / 9


def normalize_time_str(time_str: str) -> str:
    time, pm_am = time_str.split()
    if ":" not in time:
        time = time[:-2] + ":" + time[-2:]
    if len(time) == 3:
        time = "0" + time
    time_str = " ".join([time, pm_am])
    return time_str


def in_date_range(
    date_: Datelike, start: Datelike | None = None, end: Datelike | None = None
) -> bool:
    """
    Check if a date is within a date range.
    """
    return (start is None or start <= date_) and (end is None or date_ <= end)


def has_date_intersection(
    start1: Datelike | None = None,
    end1: Datelike | None = None,
    start2: Datelike | None = None,
    end2: Datelike | None = None,
) -> bool:
    """
    Check if two date ranges intersect.
    """
    assert start1 is None or end1 is None or start1 <= end1
    assert start2 is None or end2 is None or start2 <= end2
    return (start1 is None or end2 is None or start1 <= end2) and (
        start2 is None or end1 is None or start2 <= end1
    )
