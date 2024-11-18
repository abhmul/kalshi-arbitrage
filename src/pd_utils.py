from pathlib import Path
from datetime import datetime, date, time
from typing import Any

import pandas as pd

from .file_utils import pathlike

PD_INT_DTYPES: list = [
    pd.Int64Dtype(),
    pd.Int32Dtype(),
    pd.Int16Dtype(),
    pd.Int8Dtype(),
]
PD_FLOAT_DTYPES: list = [pd.Float64Dtype(), pd.Float32Dtype()]
PD_STRING_DTYPES: list = [pd.StringDtype()]

PD_DTYPES = PD_INT_DTYPES + PD_FLOAT_DTYPES + PD_STRING_DTYPES


def coerce_to_schema(df: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    """
    Coerce a DataFrame to a schema.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to coerce.
    schema : dict[str, type]
        The schema to coerce the DataFrame to.

    Returns
    -------
    pd.DataFrame
        The coerced DataFrame.
    """
    for col, dtype in schema.items():
        if col in df.columns:
            if dtype in PD_DTYPES:
                df[col] = df[col].astype(dtype)
            elif dtype == datetime:
                df[col] = pd.to_datetime(df[col])
            elif dtype == date:
                df[col] = pd.to_datetime(df[col]).dt.date
            elif dtype == time:
                df[col] = pd.to_datetime(df[col]).dt.time
            else:
                df[col] = df[col].apply(dtype)

    return df


@pathlike("path")
def load_csv(path: Path, schema: dict[str, type], **kwargs) -> pd.DataFrame:
    """
    Load a CSV file with a schema.

    Parameters
    ----------
    path : Path
        The path to the CSV file.
    schema : dict[str, type]
        The schema for the CSV file.

    Returns
    -------
    pd.DataFrame
        The loaded DataFrame.
    """
    filtered_schema = {
        col: dtype for col, dtype in schema.items() if dtype in PD_DTYPES
    }
    print(kwargs)
    df = pd.read_csv(path, dtype=filtered_schema, **kwargs)
    df = coerce_to_schema(df, schema)

    return df
