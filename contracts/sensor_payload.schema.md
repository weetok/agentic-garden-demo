# Sensor Payload schema

## Rules

1. The series file is a JSON array of these objects ordered by `ts` ascending.
2. `ts` is ISO-8601 UTC. All fields use SI/metric units as named.
3. `rain_mm` is millimetres since the previous reading (not cumulative).
4. `humidity_pct` is 0-100; `wind_direction_deg` is 0–359, direction the wind comes from.
5. `wind_speed_ms` is average wind speed since previous reading in meters per second.
6. `battery_v` is the current available voltage in the battery.
7. A missing measurement is `null`; fields are never absent.
8. Consumers must ignore unknown extra fields.

## Example

```json
{
  "schema_version": 1,
  "station_id": "allotment-01",
  "ts": "2026-07-30T14:00:00Z",
  "temperature_c": 28.4,
  "humidity_pct": 41,
  "wind_speed_ms": 4.2,
  "wind_direction_deg": 230,
  "rain_mm": 0.0,
  "battery_v": 3.9
}
```
