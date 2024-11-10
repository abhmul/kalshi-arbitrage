import requests  # type: ignore[import-untyped]
from datetime import datetime, date

from cachetools import cached, TTLCache  # type: ignore[import-untyped]
from urlpath import URL  # type: ignore[import-untyped]

from ..params import *

from .dataclasses import Forecast, TemperatureType


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
