"""
This file contains the filepaths used for the python project.
Data points from src directory, not the directory this file is in. 
"""

from pathlib import Path

PROJECT_DIR = Path("../")
DATA_DIR = PROJECT_DIR / "data"
INPUTS_DIR = DATA_DIR / "inputs"
MODELS_DIR = PROJECT_DIR / "models"
PLOTS_DIR = PROJECT_DIR / "plots"
LOGS_DIR = PROJECT_DIR / "logs"
TMP_DIR = PROJECT_DIR / "tmp"
PARAMS_DIR = PROJECT_DIR / "src/params"
KEYS_DIR = PROJECT_DIR / "keys"

KALSHI_KEY = KEYS_DIR / "kalshi_key.key"
DEMO_KALSHI_KEY = KEYS_DIR / "demo_kalshi_key.key"
LEGACY_DEMO_KALSHI_KEY = KEYS_DIR / "demo_kalshi_key.legacy.key"

# Data
ONE_MINUTE_OBSERVATIONS = INPUTS_DIR / "one_minute"
CLI_OBSERVATIONS = INPUTS_DIR / "cli"
TEMP_OBSERVATIONS = INPUTS_DIR / "temp"
STATION_SPECS = INPUTS_DIR / "station_specs.csv"

PATH_DATE_FORMAT = "%Y-%m-%d"
PATH_DATETIME_FORMAT = "%Y-%m-%dT%H-%M-%S"
PATH_TIME_FORMAT = "T%H-%M-%S"
