#!/usr/bin/env python3
"""Author the block 2.1 mock inputs: hourly site sensor series + Open-Meteo-
shaped regional weather (history + forecast). Run once; output is committed
under data/. This is data authoring, not the derived-layer pipeline (2.2) —
it emits raw mock inputs only, never advice or ET.

Story (PLAN.md block 2.1): week 1 normal, weeks 2-3 heat and wind building,
final week site gauge catches 2.0 mm against a 10.0 mm regional total —
the divergence the demo's advice is built on.
"""
import json
import math
import random
import zlib
from datetime import date, datetime, timedelta, timezone

STATION_ID = "allotment-01"
SCHEMA_VERSION = 1
LAT, LON, ELEVATION = 53.2194, 6.5665, 3.0  # Groningen allotment

SENSOR_START = date(2026, 7, 11)
SENSOR_END = date(2026, 7, 31)  # inclusive: 3 weeks
FORECAST_END = date(2026, 8, 7)  # inclusive: +7 days for the regional outlook

# date -> (tmax_c, tmin_c, hum_max_pct, hum_min_pct, wind_mean_ms, rain_mm)
SITE_DAYS = {
    date(2026, 7, 11): (21, 12, 75, 55, 2.5, 4.0),
    date(2026, 7, 12): (20, 11, 78, 58, 2.2, 2.5),
    date(2026, 7, 13): (22, 13, 72, 52, 2.8, 0.0),
    date(2026, 7, 14): (23, 13, 68, 48, 2.6, 0.0),
    date(2026, 7, 15): (24, 14, 65, 45, 2.4, 3.0),
    date(2026, 7, 16): (22, 13, 70, 50, 2.9, 4.5),
    date(2026, 7, 17): (21, 12, 74, 54, 2.7, 0.0),
    date(2026, 7, 18): (24, 14, 62, 42, 3.0, 2.0),
    date(2026, 7, 19): (25, 15, 58, 40, 3.2, 0.0),
    date(2026, 7, 20): (26, 15, 55, 38, 3.4, 0.0),
    date(2026, 7, 21): (26, 16, 54, 36, 3.5, 1.5),
    date(2026, 7, 22): (27, 16, 52, 35, 3.6, 0.0),
    date(2026, 7, 23): (27, 17, 50, 34, 3.8, 0.0),
    date(2026, 7, 24): (28, 17, 48, 33, 3.9, 0.0),
    date(2026, 7, 25): (28, 17, 46, 32, 4.0, 0.5),
    date(2026, 7, 26): (28, 18, 44, 30, 4.0, 0.0),
    date(2026, 7, 27): (29, 18, 42, 29, 4.1, 0.0),
    date(2026, 7, 28): (29, 18, 40, 28, 4.1, 0.0),
    date(2026, 7, 29): (29, 19, 39, 28, 4.2, 1.5),
    date(2026, 7, 30): (29.4, 19, 38, 27, 4.3, 0.0),
    date(2026, 7, 31): (29, 18, 39, 28, 4.2, 0.0),
}

# date -> (tmax_c, tmin_c, rain_mm) — regional station, same historical dates
REGIONAL_DAYS = {
    date(2026, 7, 11): (21, 12, 3.5),
    date(2026, 7, 12): (20, 12, 3.0),
    date(2026, 7, 13): (22, 13, 0.5),
    date(2026, 7, 14): (23, 13, 0.0),
    date(2026, 7, 15): (24, 14, 2.5),
    date(2026, 7, 16): (22, 13, 3.5),
    date(2026, 7, 17): (21, 12, 0.5),
    date(2026, 7, 18): (24, 14, 3.0),
    date(2026, 7, 19): (25, 15, 1.5),
    date(2026, 7, 20): (26, 16, 1.0),
    date(2026, 7, 21): (26, 16, 2.0),
    date(2026, 7, 22): (27, 17, 0.5),
    date(2026, 7, 23): (27, 17, 0.0),
    date(2026, 7, 24): (28, 18, 0.0),
    date(2026, 7, 25): (28, 18, 1.0),
    date(2026, 7, 26): (29, 18, 1.5),
    date(2026, 7, 27): (29, 18, 2.0),
    date(2026, 7, 28): (30, 19, 2.0),
    date(2026, 7, 29): (30, 19, 2.0),
    date(2026, 7, 30): (30, 19, 1.0),
    date(2026, 7, 31): (29, 18, 0.5),
}

# date -> (tmax_c, tmin_c, hum_max_pct, hum_min_pct, wind_mean_ms, rain_mm)
# Forward-looking only — no site sensor exists for these dates (contract rule 13).
REGIONAL_FORECAST_DAYS = {
    date(2026, 8, 1): (28, 17, 45, 30, 4.0, 0.5),
    date(2026, 8, 2): (27, 17, 48, 32, 3.8, 1.0),
    date(2026, 8, 3): (26, 16, 50, 34, 3.5, 0.5),
    date(2026, 8, 4): (26, 16, 52, 35, 3.3, 0.0),
    date(2026, 8, 5): (25, 15, 55, 38, 3.0, 1.0),
    date(2026, 8, 6): (24, 15, 58, 40, 2.8, 0.5),
    date(2026, 8, 7): (23, 14, 60, 42, 2.6, 0.5),
}

PEAK_HOUR = 15  # temperature peak; humidity trough coincides, wind eases toward evening


def date_range(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def seeded_rng(*parts):
    seed = zlib.crc32("|".join(parts).encode())
    return random.Random(seed)


def diurnal(hour, lo, hi, invert=False):
    mid, amp = (hi + lo) / 2, (hi - lo) / 2
    phase = (hour - PEAK_HOUR) / 24 * 2 * math.pi
    return mid - amp * math.cos(phase) if invert else mid + amp * math.cos(phase)


def rain_hours_for_day(source, d, total_mm):
    """Deterministically place a day's rain total into 1-2 hourly buckets."""
    if total_mm <= 0:
        return {}
    rng = seeded_rng(source, d.isoformat())
    n_hours = 1 if total_mm <= 1.5 else 2
    window = rng.choice([[3, 4, 5, 6], [18, 19, 20, 21]])
    hours = rng.sample(window, n_hours)
    if n_hours == 1:
        return {hours[0]: round(total_mm, 1)}
    split = rng.uniform(0.4, 0.6)
    first = round(total_mm * split, 1)
    return {hours[0]: first, hours[1]: round(total_mm - first, 1)}


def wind_direction(source, d, hour):
    rng = seeded_rng(source, d.isoformat(), str(hour))
    prevailing = 225  # SW, typical for this site
    drift = ((d - SENSOR_START).days) * 1.5  # slow rotation over the period
    return round((prevailing + drift + rng.uniform(-20, 20)) % 360)


def battery_v(hour, rng):
    base = 3.75 + 0.15 * math.cos((hour - 14) / 24 * 2 * math.pi)
    return round(max(3.5, min(4.1, base + rng.uniform(-0.03, 0.03))), 2)


def build_sensor_series():
    readings = []
    rng = random.Random(zlib.crc32(b"sensor-jitter"))
    for d in date_range(SENSOR_START, SENSOR_END):
        tmax, tmin, hum_max, hum_min, wind_mean, rain_total = SITE_DAYS[d]
        rain_by_hour = rain_hours_for_day("site", d, rain_total)
        for hour in range(24):
            temp = diurnal(hour, tmin, tmax) + rng.uniform(-0.3, 0.3)
            hum = diurnal(hour, hum_min, hum_max, invert=True) + rng.uniform(-1.5, 1.5)
            wind = wind_mean + 0.4 * math.sin((hour - 6) / 24 * 2 * math.pi) + rng.uniform(-0.2, 0.2)
            ts = datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)
            readings.append({
                "schema_version": SCHEMA_VERSION,
                "station_id": STATION_ID,
                "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "temperature_c": round(temp, 1),
                "humidity_pct": round(max(0, min(100, hum))),
                "wind_speed_ms": round(max(0, wind), 1),
                "wind_direction_deg": wind_direction("site", d, hour),
                "rain_mm": rain_by_hour.get(hour, 0.0),
                "battery_v": battery_v(hour, rng),
            })
    return readings


def build_weather_regional():
    rng = random.Random(zlib.crc32(b"regional-jitter"))
    hourly = {
        "time": [], "temperature_2m": [], "relative_humidity_2m": [],
        "precipitation": [], "wind_speed_10m": [], "wind_direction_10m": [],
    }
    daily = {
        "time": [], "temperature_2m_max": [], "temperature_2m_min": [],
        "precipitation_sum": [], "wind_speed_10m_max": [],
    }

    def day_table(d):
        if d in REGIONAL_DAYS:
            tmax, tmin, rain_total = REGIONAL_DAYS[d]
            site_tmax, site_tmin, hum_max, hum_min, wind_mean, _ = SITE_DAYS[d]
            return tmax, tmin, hum_max + 5, hum_min + 5, wind_mean * 0.9, rain_total
        tmax, tmin, hum_max, hum_min, wind_mean, rain_total = REGIONAL_FORECAST_DAYS[d]
        return tmax, tmin, hum_max, hum_min, wind_mean, rain_total

    for d in date_range(SENSOR_START, FORECAST_END):
        tmax, tmin, hum_max, hum_min, wind_mean, rain_total = day_table(d)
        rain_by_hour = rain_hours_for_day("regional", d, rain_total)
        wind_max = 0.0
        for hour in range(24):
            temp = diurnal(hour, tmin, tmax) + rng.uniform(-0.3, 0.3)
            hum = diurnal(hour, hum_min, hum_max, invert=True) + rng.uniform(-1.5, 1.5)
            wind = wind_mean + 0.4 * math.sin((hour - 6) / 24 * 2 * math.pi) + rng.uniform(-0.2, 0.2)
            wind = max(0, wind)
            wind_max = max(wind_max, wind)
            ts = datetime(d.year, d.month, d.day, hour)
            hourly["time"].append(ts.strftime("%Y-%m-%dT%H:%M"))
            hourly["temperature_2m"].append(round(temp, 1))
            hourly["relative_humidity_2m"].append(round(max(0, min(100, hum))))
            hourly["precipitation"].append(rain_by_hour.get(hour, 0.0))
            hourly["wind_speed_10m"].append(round(wind, 1))
            hourly["wind_direction_10m"].append(wind_direction("regional", d, hour))
        daily["time"].append(d.isoformat())
        daily["temperature_2m_max"].append(tmax)
        daily["temperature_2m_min"].append(tmin)
        daily["precipitation_sum"].append(round(rain_total, 1))
        daily["wind_speed_10m_max"].append(round(wind_max, 1))

    return {
        "latitude": LAT,
        "longitude": LON,
        "generationtime_ms": 0.21,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": ELEVATION,
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
            "wind_speed_10m": "m/s",
            "wind_direction_10m": "°",
        },
        "hourly": hourly,
        "daily_units": {
            "time": "iso8601",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_sum": "mm",
            "wind_speed_10m_max": "m/s",
        },
        "daily": daily,
    }


def main():
    import pathlib
    data_dir = pathlib.Path(__file__).resolve().parent.parent / "data"

    sensor_series = build_sensor_series()
    (data_dir / "sensor_series.json").write_text(json.dumps(sensor_series, indent=2) + "\n")

    weather_regional = build_weather_regional()
    (data_dir / "weather_regional.json").write_text(json.dumps(weather_regional, indent=2) + "\n")

    print(f"wrote {len(sensor_series)} sensor readings to data/sensor_series.json")
    print(f"wrote {len(weather_regional['hourly']['time'])} hourly + "
          f"{len(weather_regional['daily']['time'])} daily regional rows to data/weather_regional.json")


if __name__ == "__main__":
    main()
