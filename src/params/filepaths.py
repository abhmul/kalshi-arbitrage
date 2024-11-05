"""
This file contains the filepaths used for the python project.
Data points from src directory, not the directory this file is in. 
"""

from glob import glob
import os
from pathlib import Path

PROJECT_DIR = Path("../")
DATA_DIR = PROJECT_DIR / "data"
MODELS_DIR = PROJECT_DIR / "models"
PLOTS_DIR = PROJECT_DIR / "plots"
LOGS_DIR = PROJECT_DIR / "logs"
TMP_DIR = PROJECT_DIR / "tmp"
PARAMS_DIR = PROJECT_DIR / "src/params"
KEYS_DIR = PROJECT_DIR / "keys"

KALSHI_KEY = KEYS_DIR / "kalshi_key.key"
DEMO_KALSHI_KEY = KEYS_DIR / "demo_kalshi_key.key"
LEGACY_DEMO_KALSHI_KEY = KEYS_DIR / "demo_kalshi_key.legacy.key"
