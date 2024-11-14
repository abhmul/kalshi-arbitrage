from typing import Any
import requests  # type: ignore[import-untyped]
from datetime import datetime, date
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

    def _request_cli_urls(self, stationid: StationID) -> dict:
        url = CLI_API_BASE / "locations" / f"{stationid}"
        response = requests.get(url)
        response.raise_for_status()
        res = response.json()

        return res

    def get_cli_urls(self, stationid: StationID) -> list[CLIInfo]:
        res = self._request_cli_urls(stationid)

        url_info = []
        for url_data in res["@graph"]:
            info = CLIInfo(
                url=URL(url_data["@id"]),
                id=url_data["id"],
                wmo_collective_id=url_data["wmoCollectiveId"],
                issuing_office=url_data["issuingOffice"],
                issuance_time=datetime.strptime(
                    url_data["issuanceTime"], self.DATETIME_FORMAT
                ),
            )
            url_info.append(info)

        return url_info

    @cached(cache=TTLCache(maxsize=1024, ttl=3600))
    def get_cli_data(self, url: URL) -> CLI:
        response = requests.get(url)
        response.raise_for_status()
        res = response.json()

        return self.parse_json(res)

    def get_all_cli_data(self, stationid: StationID) -> list[CLI]:
        urls = self.get_cli_urls(stationid)
        cli_data = []
        for url_info in urls:
            data = self.get_cli_data(url_info.url)
            cli_data.append(data)
        return cli_data

    @staticmethod
    def _parse_product_text(
        product_text: str,
    ) -> ParsedCLIReport:
        # Extract relevant sections using regular expressions

        date_match = re.search(r"SUMMARY FOR (.+?)\.\.\.", product_text)

        temp_pattern = re.compile(
            r"""
            (MAXIMUM|MINIMUM|AVERAGE)\s+         # Match the label (MAXIMUM, MINIMUM, AVERAGE)
            (\d+)R?\s+                             # Match the observed value
            (\d{1,2}:?\d{2}\s[APM]{2})?\s*        # Match the time (optional for AVERAGE)
            (\d+)?\s*                            # Match the record value (optional for AVERAGE)
            (\d{4})?\s*                          # Match the record year (optional for AVERAGE)
            (\d+)?\s*                            # Match the normal value (optional for AVERAGE)
            ([+-]?\d+)?\s*                       # Match the departure from normal (optional for AVERAGE)
            (\d+)?                               # Match the last year value (optional for AVERAGE)
        """,
            re.VERBOSE,
        )

        matches = temp_pattern.findall(product_text)

        temp_data: dict[str, Any] = {}
        time_parse_with_col = "%I:%M %p"
        time_parse_without_col = "%I%M %p"
        date_parse = "%B %d %Y"

        for match in matches:
            label, observed_value, time, *_ = match
            if label == "MAXIMUM":
                temp_data["max_temp"] = int(observed_value)
                if time:
                    if ":" in time:
                        temp_data["max_temp_time"] = datetime.strptime(
                            f"{date_match.group(1)} {time}", f"{date_parse} {time_parse_with_col}"  # type: ignore[union-attr]
                        )
                    else:
                        temp_data["max_temp_time"] = datetime.strptime(
                            f"{date_match.group(1)} {time}", f"{date_parse} {time_parse_without_col}"  # type: ignore[union-attr]
                        )
            elif label == "MINIMUM":
                temp_data["min_temp"] = int(observed_value)
                if time:
                    if ":" in time:
                        temp_data["min_temp_time"] = datetime.strptime(
                            f"{date_match.group(1)} {time}", f"{date_parse} {time_parse_with_col}"  # type: ignore[union-attr]
                        )
                    else:
                        temp_data["min_temp_time"] = datetime.strptime(
                            f"{date_match.group(1)} {time}", f"{date_parse} {time_parse_without_col}"  # type: ignore[union-attr]
                        )
            elif label == "AVERAGE":
                temp_data["avg_temp"] = int(observed_value)

        highest_wind_speed_match = re.search(
            r"HIGHEST WIND SPEED\s+(\d+)", product_text
        )
        highest_wind_direction_match = re.search(
            r"HIGHEST WIND DIRECTION\s+(\w+)", product_text
        )
        highest_gust_speed_match = re.search(
            r"HIGHEST GUST SPEED\s+(\d+)", product_text
        )
        highest_gust_direction_match = re.search(
            r"HIGHEST GUST DIRECTION\s+(\w+)", product_text
        )
        average_wind_speed_match = re.search(
            r"AVERAGE WIND SPEED\s+(\d+\.\d+)", product_text
        )
        average_sky_cover_match = re.search(
            r"AVERAGE SKY COVER\s+(\d+\.\d+)", product_text
        )
        highest_humidity_match = re.search(r"HIGHEST\s+(\d+)", product_text)
        lowest_humidity_match = re.search(r"LOWEST\s+(\d+)", product_text)
        average_humidity_match = re.search(r"AVERAGE\s+(\d+)", product_text)

        # Convert date and time strings to date and datetime objects
        # if date_match is None:
        # print(product_text)
        summary_date_obj = datetime.strptime(date_match.group(1), "%B %d %Y").date()  # type: ignore[union-attr]

        return ParsedCLIReport(
            summary_date=summary_date_obj,
            raw_text=product_text,
            max_temp=temp_data.get("max_temp"),
            max_temp_time=temp_data.get("max_temp_time"),
            min_temp=temp_data.get("min_temp"),
            min_temp_time=temp_data.get("min_temp_time"),
            avg_temp=temp_data.get("avg_temp"),
            # precipitation=precipitation_data["day"],
            # precipitation_month_to_date=precipitation_data["month_to_date"],
            # precipitation_since_sep_1=precipitation_data["since_sep_1"],
            # precipitation_since_jan_1=precipitation_data["since_jan_1"],
            highest_wind_speed=(
                int(highest_wind_speed_match.group(1))
                if highest_wind_speed_match
                else None
            ),
            highest_wind_direction=(
                highest_wind_direction_match.group(1)
                if highest_wind_direction_match
                else None
            ),
            highest_gust_speed=(
                int(highest_gust_speed_match.group(1))
                if highest_gust_speed_match
                else None
            ),
            highest_gust_direction=(
                highest_gust_direction_match.group(1)
                if highest_gust_direction_match
                else None
            ),
            average_wind_speed=(
                float(average_wind_speed_match.group(1))
                if average_wind_speed_match
                else None
            ),
            average_sky_cover=(
                float(average_sky_cover_match.group(1))
                if average_sky_cover_match
                else None
            ),
            highest_humidity=(
                int(highest_humidity_match.group(1)) if highest_humidity_match else None
            ),
            lowest_humidity=(
                int(lowest_humidity_match.group(1)) if lowest_humidity_match else None
            ),
            average_humidity=(
                int(average_humidity_match.group(1)) if average_humidity_match else None
            ),
        )

    @staticmethod
    def parse_json(json_data: dict) -> CLI:
        issuance_time = datetime.fromisoformat(json_data["issuanceTime"])
        product_code = json_data["productCode"]
        product_name = json_data["productName"]
        issuing_office = json_data["issuingOffice"]
        product_text = json_data["productText"]
        url = URL(json_data["@id"])

        # print(product_text)
        parsed_report = NWSClient._parse_product_text(product_text)
        cli = CLI(
            url=url,
            id=json_data["id"],
            issuance_time=issuance_time,
            product_code=product_code,
            product_name=product_name,
            issuing_office=issuing_office,
            report=parsed_report,
        )

        return cli

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
