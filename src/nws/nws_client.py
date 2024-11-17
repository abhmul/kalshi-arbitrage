from io import StringIO
from typing import Any, cast
import requests  # type: ignore[import-untyped]
from datetime import datetime, date, timedelta
import re
import pytz
from collections import defaultdict

from cachetools import cached, TTLCache  # type: ignore[import-untyped]
from urlpath import URL  # type: ignore[import-untyped]
import pandas as pd
from tqdm import tqdm  # type: ignore[import-untyped]

from ..params import *
from ..file_utils import pathlike, safe_open_dir, safe_open_file

from .dataclasses import *
from .utils import normalize_time_str
from .cli import parse_product_text, cli_path
from .one_minute import one_minute_path


class NWSClient:
    # Example: 2024-11-10T14:00:00-05:00
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

    @cached(cache=TTLCache(maxsize=1024, ttl=3600))
    def get_location_info(self, lat: float, lon: float):
        url = NWS_POINTS / f"{lat},{lon}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def get_forecast_url(self, lat: float, lon: float):
        location_info = self.get_location_info(lat, lon)
        return URL(location_info["properties"]["forecast"])

    def get_hourly_forecast_url(self, lat: float, lon: float):
        location_info = self.get_location_info(lat, lon)
        return URL(location_info["properties"]["forecastHourly"])

    def get_forecast_data(self, lat: float, lon: float):
        forecast_url = self.get_forecast_url(lat, lon)
        response = requests.get(forecast_url)
        response.raise_for_status()
        res = response.json()

        return self.parse_forecast_json(res, lat, lon)

    def parse_forecast_json(self, forecast_json, lat: float, lon: float):
        properties = forecast_json["properties"]
        periods = properties["periods"]
        forecast = []
        generated_at = datetime.strptime(
            properties["generatedAt"], self.DATETIME_FORMAT
        )
        update_time = datetime.strptime(properties["updateTime"], self.DATETIME_FORMAT)
        for period in periods:
            start_time = datetime.strptime(period["startTime"], self.DATETIME_FORMAT)
            end_time = datetime.strptime(period["endTime"], self.DATETIME_FORMAT)
            date = start_time.date()
            temperature = period["temperature"]
            temperature_type = (
                TemperatureType.HIGH if period["isDaytime"] else TemperatureType.LOW
            )
            forecast.append(
                Forecast(
                    lat=lat,
                    lon=lon,
                    polygon=forecast_json["geometry"]["coordinates"],
                    generated_at=generated_at,
                    update_time=update_time,
                    start_time=start_time,
                    end_time=end_time,
                    date=date,
                    temperature=temperature,
                    temperature_type=temperature_type,
                )
            )
        return forecast

    def get_hourly_forecast_data(self, lat: float, lon: float):
        forecast_url = self.get_hourly_forecast_url(lat, lon)
        response = requests.get(forecast_url)
        response.raise_for_status()
        res = response.json()

        return self.parse_forecast_json(res, lat, lon)

    @staticmethod
    def cli_url(stationid: StationID, version: int = 1) -> URL:
        assert version <= NUM_CLI_VERSIONS  # NWS only stores 50 versions at this url
        url = NWS_FORECAST_HOME / "product.php"
        url = url.add_query(
            site=SITE_ID[stationid],
            issuedby=stationid,
            product="CLI",
            format="txt",
            glossary=0,
            version=version,
        )
        return url

    @staticmethod
    def _request_cli_data(stationid: StationID, version: int = 1) -> requests.Response:
        url = NWSClient.cli_url(stationid, version)
        response = requests.get(url)
        response.raise_for_status()

        return response

    def get_cli_data(self, stationid: StationID, version: int = 1) -> CLI:
        res = self._request_cli_data(stationid, version)

        return self._parse_cli_response(res)

    @staticmethod
    def _parse_cli_response(
        response: requests.Response, station: StationID | None = None
    ) -> CLI:
        lines = response.text.splitlines()
        for i in range(len(lines) - 3):
            match_start = (
                (
                    f"CLI{station}" in lines[i]
                    if station is not None
                    else any(f"CLI{s}" for s in StationID)
                )
                and "CLIMATE REPORT" in lines[i + 2]
                and "NATIONAL WEATHER SERVICE" in lines[i + 3]
            )
            if match_start:
                match_start_i = i - 2
            match_end = "$$" in lines[i]
            if match_end:
                match_end_i = i

        cli_text = "\n".join(lines[match_start_i : match_end_i + 1])
        return parse_product_text(cli_text)

    @staticmethod
    @cached(cache=TTLCache(maxsize=1024, ttl=3600))
    def _request_observations_from_station(
        stationid: StationID, start: datetime, end: datetime, radius: int = 0
    ) -> requests.Response:
        assert start.tzinfo is not None
        assert end.tzinfo is not None

        url = TIME_SERIES_BASE
        params = {
            "radius": f"k{stationid.value.lower()},{radius}",
            "start": start.astimezone(pytz.utc).strftime("%Y%m%d%H%M"),
            "end": end.astimezone(pytz.utc).strftime("%Y%m%d%H%M"),
            "vars": "air_temp,wind_speed,wind_direction,relative_humidity,air_temp_high_6_hour,air_temp_high_24_hour",
            "token": PUBLIC_TOKEN,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()

        return response

    def get_timeseries(
        self, stationid: StationID, start: datetime, end: datetime, radius: int = 0
    ) -> list[pd.DataFrame]:
        if start.tzinfo is None:
            start = STATION_TZ[stationid].localize(start)
        if end.tzinfo is None:
            end = STATION_TZ[stationid].localize(end)

        res = self._request_observations_from_station(
            stationid, start, end, radius=radius
        ).json()

        station_dfs = []
        for station_obs in res["STATION"]:
            data = station_obs["OBSERVATIONS"]
            df = pd.DataFrame(data)
            df["date_time"] = pd.to_datetime(df["date_time"])
            df.set_index("date_time", inplace=True)

            df = df.tz_convert(STATION_TZ[stationid])
            df["time"] = df.index.time  # type: ignore[attr-defined]
            df["station_id"] = station_obs["STID"]
            df["station_name"] = station_obs["NAME"]
            df["distance"] = station_obs["DISTANCE"]

            station_dfs.append(df)

        return station_dfs

    @pathlike("output_dir")
    def download_timeseries(
        self,
        stationid: StationID,
        output_dir: Path,
        start: datetime,
        end: datetime,
        radius: int = 0,
        overwrite: bool = False,
    ) -> DownloadTimeseriesResult:
        days = pd.period_range(start=start, end=end, freq="D")
        all_days_dfs: dict[str, pd.DataFrame] = defaultdict(pd.DataFrame)
        for day in tqdm(days):
            day = STATION_TZ[stationid].localize(day.to_timestamp())
            data = self.get_timeseries(
                stationid, day, day + timedelta(days=1), radius=radius
            )
            for df in data:
                data_station = df["station_id"].iloc[0]
                all_days_dfs[data_station] = pd.concat([all_days_dfs[data_station], df])

        written_fps = []
        downloaded_fps = []
        for df in all_days_dfs.values():
            output_fp = safe_open_dir(output_dir / f"{stationid}") / (
                f"timeseries.{stationid}."
                f"start-{start.strftime(PATH_DATETIME_FORMAT)}."
                f"end-{end.strftime(PATH_DATETIME_FORMAT)}."
                f"station-{df['station_id'].iloc[0]}."
                f"distance-{df['distance'].iloc[0]}.csv"
            )
            downloaded_fps.append(output_fp)
            if not output_fp.exists() or overwrite:
                df.to_csv(output_fp, index=True)
                written_fps.append(output_fp)

        return DownloadTimeseriesResult(
            requested_start=start,
            requested_end=end,
            written_filepaths=written_fps,
            downloaded_filepaths=downloaded_fps,
        )

    @pathlike("output_dir")
    def download_cli_data(
        self,
        stationid: StationID,
        output_dir: Path,
        versions: int | list | None = None,
        overwrite: bool = False,
    ) -> DownloadCLIsResult:
        if versions is None:
            versions = list(range(1, NUM_CLI_VERSIONS + 1))
        elif isinstance(versions, int):
            versions = [versions]

        written_fps = []
        downloaded_fps = []
        prog = tqdm(versions) if len(versions) > 1 else versions
        for version in prog:
            cli = self.get_cli_data(stationid, version)
            output_fp = safe_open_file(
                cli_path(
                    station=stationid,
                    issuance_datetime=cli.issuance_time,
                    summary_date=cli.summary_date,
                    output_dir=output_dir,
                )
            )
            downloaded_fps.append(output_fp)
            if not output_fp.exists() or overwrite:
                with open(output_fp, "w") as f:
                    f.write(cli.raw_text)
                written_fps.append(output_fp)

        return DownloadCLIsResult(
            written_filepaths=written_fps, downloaded_filepaths=downloaded_fps
        )

    @staticmethod
    @cached(cache=TTLCache(maxsize=1024, ttl=3600))
    def _request_one_minute_data(
        stationid: StationID, start: datetime, end: datetime
    ) -> requests.Response:
        assert start.tzinfo is not None
        assert end.tzinfo is not None

        params = {
            "station": stationid,
            "vars": "tmpf",
            "sts": start.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ets": end.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sample": "1min",
            "what": "view",
            "tz": "UTC",
        }
        url = ONE_MINUTE_BASE.add_query(**params)
        response = requests.get(url)
        response.raise_for_status()

        return response

    def get_one_minute_data(
        self, stationid: StationID, start: datetime, end: datetime
    ) -> pd.DataFrame:
        if start.tzinfo is None:
            start = STATION_TZ[stationid].localize(start)
        if end.tzinfo is None:
            end = STATION_TZ[stationid].localize(end)

        res = self._request_one_minute_data(stationid, start, end)

        df = pd.read_csv(StringIO(res.text), header=0)
        df["valid(UTC)"] = pd.to_datetime(df["valid(UTC)"], utc=True)
        df["valid"] = df["valid(UTC)"].dt.tz_convert(STATION_TZ[stationid])
        df.drop(columns=["valid(UTC)"], inplace=True)

        return df

    @pathlike("output_dir")
    def download_one_minute_data(
        self,
        stationid: StationID,
        output_dir: Path,
        start: datetime,
        end: datetime,
        overwrite: bool = False,
    ) -> DownloadOneMinuteResult:
        data = self.get_one_minute_data(stationid, start, end)
        if len(data) == 0:
            return DownloadOneMinuteResult(
                num_rows=0,
                requested_start=start,
                requested_end=end,
                true_start=None,
                true_end=None,
            )

        true_start = data["valid"].min()
        true_end = data["valid"].max()

        output_fp = safe_open_file(
            one_minute_path(
                station=stationid, start=true_start, end=true_end, output_dir=output_dir
            )
        )
        if not output_fp.exists() or overwrite:
            data.to_csv(output_fp, index=False)
            num_rows = len(data)
        else:
            num_rows = 0

        return DownloadOneMinuteResult(
            num_rows=num_rows,
            requested_start=start,
            requested_end=end,
            true_start=true_start,
            true_end=true_end,
        )


#     def get_metadata(self):
#         url = f"{self.base_url}/{self.lat},{self.lon}"
#         response = requests.get(url)
#         response.raise_for_status()
#         return response.json()

#     def get_forecast_url(self, metadata):
#         return metadata["properties"]["forecast"]

#     def get_forecast_data(self, forecast_url):
#         response = requests.get(forecast_url)
#         response.raise_for_status()
#         return response.json()

#     def get_forecast(self):
#         metadata = self.get_metadata()
#         forecast_url = self.get_forecast_url(metadata)
#         forecast_data = self.get_forecast_data(forecast_url)
#         return forecast_data


# if __name__ == "__main__":
#     lat = 38.8894
#     lon = -77.0352
#     client = NWSClient(lat, lon)
#     forecast = client.get_forecast()
#     print(forecast)
