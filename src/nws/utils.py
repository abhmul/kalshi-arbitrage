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
