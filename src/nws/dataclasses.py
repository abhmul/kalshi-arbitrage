from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum


class TemperatureType(Enum):
    HIGH = "high"
    LOW = "low"

    def str(self):
        return self.value


@dataclass
class Forecast:
    lat: float
    lon: float
    generated_at: datetime
    update_time: datetime
    start_time: datetime
    end_time: datetime
    date: date
    temperature: float
    temperature_type: TemperatureType
