# Derived data schema

## Rules

1. This file is the dashboard's only data source besides `planting_map.json`;
   if a view needs a value, it must be present here precomputed. `planting_map.json`
   is `data/planting_map.yaml` transformed 1:1 — same fields, same ids, no
   computation; the YAML remains the source of truth, the JSON inherits its
   schema by reference. `bed_id` values are the join key between the two files.
2. All _\_mm, _\_c, _\_ms, _\_pct fields use the units in their suffix; no unit
   ever appears inside a value.
3. `daily_series` is ordered by `date` ascending, one entry per day, no gaps
   within `period`. Daily grain: `date` is a date, never a timestamp.
4. Series values are per-day amounts; consumers may sum them for cumulative
   display.
5. `beds[].bed_id` must exist in `planting_map.json`; every bed in
   `planting_map.json` appears exactly once in `beds`.
6. `stress` is exactly one of: ok | watch | act. No other values, ever.
7. Every `advice.actions[].bed_id` must appear in `beds`, and every bed with
   stress "act" must have an action.
8. `advice.headline` and `advice.why` are presentation-ready text; the
   dashboard renders them verbatim, no transformation.
9. Consumers must ignore unknown extra fields.
10. Latest value is used for metrics whenever there is no specification in the suffix.
11. `outlook.period.start` is `period.end` + 1 day: no gap or overlap between
    history and outlook.
12. `outlook` feeds the briefing's Outlook section only; no other view renders
    it — it is not a source for the water-balance chart or any dashboard view.
13. `outlook.source` is always `"regional_forecast"` — the site has no forward-
    looking sensor data, only a regional forecast. At least one entry in
    `outlook.drivers` must state this provenance explicitly, so the same
    site-vs-regional divergence the demo's advice is built on isn't quietly
    lost in the outlook text.

## example

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-01T20:00:00Z",
  "period": { "start": "2026-07-11", "end": "2026-07-31" },

  "headline_metrics": {
    "temperature_c": 29.4,
    "humidity_pct": 38,
    "wind_speed_ms": 4.2,
    "rain_7d_mm": 2.0,
    "et_7d_mm": 31.0
  },

  "daily_series": [
    {
      "date": "2026-07-11",
      "et_mm": 3.1,
      "rain_site_mm": 4.0,
      "rain_regional_mm": 3.5
    }
  ],

  "outlook": {
    "period": { "start": "2026-08-01", "end": "2026-08-07" },
    "source": "regional_forecast",
    "forecast_rain_mm": 4.0,
    "forecast_et_mm": 28.0,
    "drivers": [
      "Based on regional forecast — site typically runs drier",
      "High pressure holding, ET demand expected to stay elevated"
    ]
  },

  "beds": [
    {
      "bed_id": "square_foot_beds",
      "stress": "act",
      "water_balance_mm": -18.0
    }
  ],

  "advice": {
    "headline": "Deep-water the square-foot beds tonight, then mulch. Leave the apple guild alone.",
    "actions": [
      { "bed_id": "square_foot_beds", "action": "deep_water_and_mulch" },
      { "bed_id": "apple_guild", "action": "none" }
    ],
    "why": [
      "Site rain 2 mm vs 10 mm regional forecast",
      "ET 31 mm outpaced rainfall over 7 days",
      "Square-foot beds: shallow-rooted, unmulched",
      "Apple guild: deep-rooted, mulched"
    ]
  }
}
```
