from typing import Any, cast
import requests  # type: ignore[import-untyped]
from datetime import datetime, date, timedelta
from dateutil import parser
import re
import pytz

from cachetools import cached, TTLCache  # type: ignore[import-untyped]
from urlpath import URL  # type: ignore[import-untyped]
import pandas as pd

from ..params import *

from .dataclasses import *


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

    def cli_url(self, stationid: StationID, version: int = 1) -> URL:
        assert version <= 50  # NWS only stores 50 versions at this url
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

    def _request_cli_data(
        self, stationid: StationID, version: int = 1
    ) -> requests.Response:
        url = self.cli_url(stationid, version)
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
        return NWSClient._parse_product_text(cli_text)

    @staticmethod
    def _parse_product_text(
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
        assert lines[line_i].strip() == "CLIMATE REPORT"
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
            match = re.search(
                r"AS\s+OF\s+(\d{4}\s+(AM|PM))\s+LOCAL\s+TIME", lines[line_i]
            )
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
                raise ValueError(
                    "Could not find the temperature data in the product text"
                )
        line_i += 1

        if (issuance_datetime.date() - summary_date) == timedelta(days=1):
            assert "YESTERDAY" == lines[line_i].strip()
        elif (issuance_datetime.date() - summary_date) == timedelta(days=0):
            assert "TODAY" == lines[line_i].strip()
        else:
            raise ValueError("Could not find the correct day for the temperature data")
        line_i += 1

        # Maximum
        match = re.search(r"MAXIMUM\s+(\d+)\s+(\d{1,2}:\d{2}\s(PM|AM))", lines[line_i])
        assert match is not None
        max_temp = int(match.group(1))
        max_temp_time = datetime.strptime(match.group(2), "%I:%M %p").time()
        max_temp_datetime = STATION_TZ[station].localize(
            datetime.combine(summary_date, max_temp_time)
        )
        line_i += 1

        # Minimum
        match = re.search(r"MINIMUM\s+(\d+)\s+(\d{1,2}:\d{2}\s(PM|AM))", lines[line_i])
        assert match is not None
        min_temp = int(match.group(1))
        min_temp_time = datetime.strptime(match.group(2), "%I:%M %p").time()
        min_temp_datetime = STATION_TZ[station].localize(
            datetime.combine(summary_date, min_temp_time)
        )
        line_i += 1

        # Average
        match = re.search(r"AVERAGE\s+(\d+)", lines[line_i])
        assert match is not None
        avg_temp = int(match.group(1))
        line_i += 1

        # TODO Precipitation, Snowfall, Wind, Sky Cover, Weather Conditions, Relative Humidity

        return CLI(
            issuance_time=issuance_datetime,
            issuing_office=site,
            summary_date=summary_date,
            raw_text=product_text,
            max_temp=max_temp,
            max_temp_time=max_temp_datetime,
            min_temp=min_temp,
            min_temp_time=min_temp_datetime,
            avg_temp=avg_temp,
            valid_time=valid_datetime,
        )

    @cached(cache=TTLCache(maxsize=1024, ttl=3600))
    def _request_observations_from_station(
        self, stationid: StationID, start: datetime, end: datetime, radius: int = 0
    ):
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

        res = response.json()

        return res

    def get_timeseries(
        self, stationid: StationID, start: datetime, end: datetime, radius: int = 0
    ) -> list[pd.DataFrame]:
        res = self._request_observations_from_station(
            stationid, start, end, radius=radius
        )

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
