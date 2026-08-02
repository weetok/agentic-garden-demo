#!/usr/bin/env python3
"""Derived layer: Hargreaves ET, water balance, threshold-based advice.

Reads data/sensor_series.json + data/weather_regional.json +
docs/data/planting_map.json; emits docs/data/derived.json and
docs/data/briefing.md, overwriting the Evening 1 stubs. Stress and actions
are rule-based on computed water balance — never hand-written. Advice
phrasing is rephrased by the Anthropic API when ANTHROPIC_API_KEY is set
(same facts, no new decisions); falls back to the deterministic template
built here when the key is absent, per CLAUDE.md hard rule 5.
"""
import json
import math
import os
import pathlib
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS_DATA = ROOT / "docs" / "data"

LAT_DEG = 53.2194  # Groningen allotment
SCHEMA_VERSION = 1

WATER_NEED_FACTOR = {"low": 0.7, "medium": 1.0, "high": 1.35}
ROOT_RESERVE_MM = {"shallow": 5.0, "medium": 15.0, "deep": 35.0}  # plant-available water, rough estimate by rooting depth
MULCH_ET_FACTOR = 0.75  # mulch cuts evaporative demand roughly a quarter

# balance >= WATCH_FLOOR -> ok; >= ACT_FLOOR -> watch; below ACT_FLOOR -> act
WATCH_FLOOR_MM = -5.0
ACT_FLOOR_MM = -15.0

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

HOURLY_WINDOW_HOURS = 7 * 24  # trailing week, for the Trends tab's hourly-conditions charts


def hargreaves_et0(tmax, tmin, tmean, day_of_year, lat_deg=LAT_DEG):
    """Hargreaves-Samani reference ET0, mm/day. CLAUDE.md hard rule 3: this
    is the ceiling for this demo — do not upgrade to full FAO-56 Penman-Monteith."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    decl = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))
    ra_mj = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )
    ra_mm = 0.408 * ra_mj
    return 0.0023 * (tmean + 17.8) * math.sqrt(max(0.0, tmax - tmin)) * ra_mm


def load_json(path):
    return json.loads(path.read_text())


def aggregate_site_daily(sensor_series):
    by_day = defaultdict(list)
    for r in sensor_series:
        by_day[r["ts"][:10]].append(r)
    daily = {}
    for d, readings in sorted(by_day.items()):
        temps = [r["temperature_c"] for r in readings]
        daily[d] = {
            "tmax": max(temps),
            "tmin": min(temps),
            "rain_mm": round(sum(r["rain_mm"] for r in readings), 2),
        }
    return daily


def build_daily_series(site_daily, weather):
    regional_rain = dict(zip(weather["daily"]["time"], weather["daily"]["precipitation_sum"]))
    series = []
    for d in sorted(site_daily):
        dt = date.fromisoformat(d)
        tmax, tmin = site_daily[d]["tmax"], site_daily[d]["tmin"]
        tmean = (tmax + tmin) / 2
        et = hargreaves_et0(tmax, tmin, tmean, dt.timetuple().tm_yday)
        series.append({
            "date": d,
            "et_mm": round(et, 1),
            "rain_site_mm": round(site_daily[d]["rain_mm"], 1),
            "rain_regional_mm": round(regional_rain.get(d, 0.0), 1),
        })
    return series


def build_outlook(weather, period_end):
    start = period_end + timedelta(days=1)
    idx = {t: i for i, t in enumerate(weather["daily"]["time"])}
    days = [start + timedelta(days=i) for i in range(7)]
    forecast_rain = forecast_et = 0.0
    for d in days:
        i = idx[d.isoformat()]
        tmax = weather["daily"]["temperature_2m_max"][i]
        tmin = weather["daily"]["temperature_2m_min"][i]
        forecast_et += hargreaves_et0(tmax, tmin, (tmax + tmin) / 2, d.timetuple().tm_yday)
        forecast_rain += weather["daily"]["precipitation_sum"][i]
    forecast_rain, forecast_et = round(forecast_rain, 1), round(forecast_et, 1)
    return {
        "period": {"start": days[0].isoformat(), "end": days[-1].isoformat()},
        "source": "regional_forecast",
        "forecast_rain_mm": forecast_rain,
        "forecast_et_mm": forecast_et,
        "drivers": [
            "Based on regional forecast — the site has no forward-looking sensor data of its own",
            f"Regional forecast: {forecast_rain} mm rain vs {forecast_et} mm ET demand over the week ahead"
            + (", continuing this period's deficit" if forecast_et > forecast_rain else ""),
        ],
    }


def watering_by_bed(observations, start_date, end_date):
    """Sum manual watering per bed within an inclusive date window. Watering
    is a targeted, per-bed input — distinct from the site rain gauge — so it
    only ever adjusts individual beds' water balance, never daily_series."""
    totals = {}
    for obs in observations:
        if start_date <= date.fromisoformat(obs["date"]) <= end_date:
            totals[obs["bed_id"]] = totals.get(obs["bed_id"], 0.0) + obs["amount_mm"]
    return totals


def compute_beds(planting_map, rain_7d, et_7d, watered_7d):
    beds = []
    for bed in planting_map["beds"]:
        factor = WATER_NEED_FACTOR[bed["water_need"]]
        mulch_factor = MULCH_ET_FACTOR if bed["mulched"] else 1.0
        effective_et = et_7d * factor * mulch_factor
        reserve = ROOT_RESERVE_MM[bed["root_depth"]]
        watered = watered_7d.get(bed["id"], 0.0)
        balance = round(reserve + (rain_7d + watered - effective_et), 1)
        if balance >= WATCH_FLOOR_MM:
            stress = "ok"
        elif balance >= ACT_FLOOR_MM:
            stress = "watch"
        else:
            stress = "act"
        beds.append({
            "bed_id": bed["id"], "name": bed["name"], "root_depth": bed["root_depth"],
            "water_need": bed["water_need"], "mulched": bed["mulched"],
            "stress": stress, "water_balance_mm": balance, "watered_7d_mm": watered,
        })
    return beds


def bed_trait_line(b, suffix):
    return f"{b['name']}: {b['root_depth']}-rooted, {'mulched' if b['mulched'] else 'unmulched'} — {suffix}"


def build_advice(beds, rain_7d, et_7d, regional_7d):
    act_beds = sorted([b for b in beds if b["stress"] == "act"], key=lambda b: b["water_balance_mm"])
    best_bed = max(beds, key=lambda b: b["water_balance_mm"])

    actions = []
    for b in act_beds:
        action = "deep_water" if b["mulched"] else "deep_water_and_mulch"
        actions.append({"bed_id": b["bed_id"], "action": action})
    if best_bed["bed_id"] not in {a["bed_id"] for a in actions}:
        actions.append({"bed_id": best_bed["bed_id"], "action": "none"})

    # Narrate only the worst few beds by name for readability; actions/stress
    # above already cover every act bed regardless of how many are named here.
    named = act_beds[:3]
    if act_beds:
        parts = [b["name"] for b in named]
        remainder = len(act_beds) - len(named)
        if remainder > 0:
            parts.append(f"{remainder} other bed{'s' if remainder > 1 else ''}")
        beds_text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f" and {parts[-1]}"
        headline = f"Deep-water {beds_text} tonight, then mulch where unmulched. Leave {best_bed['name']} alone."
    else:
        headline = f"No beds need urgent watering this week — {best_bed['name']} is best buffered."

    why = [
        f"Site rain {rain_7d} mm vs {regional_7d} mm recorded regionally over the same 7 days",
        f"ET {et_7d} mm outpaced rainfall over the same period",
    ]
    watered_beds = [b for b in beds if b["watered_7d_mm"] > 0]
    if watered_beds:
        total_watered = round(sum(b["watered_7d_mm"] for b in watered_beds), 1)
        why.append(f"Plus {total_watered} mm applied via manual watering across {len(watered_beds)} beds this week")
    for b in named:
        mulch_state = "mulched" if b["mulched"] else "unmulched"
        why.append(f"{b['name']}: {b['water_need']} water need, {mulch_state}, {b['root_depth']}-rooted")
    remainder = len(act_beds) - len(named)
    if remainder > 0:
        why.append(f"{remainder} further bed{'s' if remainder > 1 else ''} also flagged for watering — see actions")
    why.append(bed_trait_line(best_bed, "buffered against the deficit"))

    return headline, actions, why


def phrase_with_llm(headline, why):
    """Rephrase the same facts more fluently via the Anthropic API. Returns
    (headline, why) unchanged on any failure or missing key — the underlying
    decision never depends on this call."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return headline, why
    prompt = (
        "Rephrase the following gardening advice for fluency and warmth. "
        "Do not add, remove, or change any fact, number, or bed name. "
        "Keep the headline to one sentence pair and each why-bullet to one short sentence. "
        "Return strict JSON: {\"headline\": str, \"why\": [str, ...]}.\n\n"
        f"headline: {headline}\nwhy:\n" + "\n".join(f"- {w}" for w in why)
    )
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        text = result["content"][0]["text"]
        parsed = json.loads(text)
        if parsed.get("headline") and isinstance(parsed.get("why"), list) and len(parsed["why"]) == len(why):
            return parsed["headline"], parsed["why"]
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
        pass
    return headline, why


def build_derived(sensor_series, weather, planting_map, observations):
    site_daily = aggregate_site_daily(sensor_series)
    daily_series = build_daily_series(site_daily, weather)
    period_start = date.fromisoformat(daily_series[0]["date"])
    period_end = date.fromisoformat(daily_series[-1]["date"])

    last_7 = daily_series[-7:]
    rain_7d = round(sum(d["rain_site_mm"] for d in last_7), 1)
    regional_7d = round(sum(d["rain_regional_mm"] for d in last_7), 1)
    et_7d = round(sum(d["et_mm"] for d in last_7), 1)

    latest = sensor_series[-1]
    headline_metrics = {
        "temperature_c": latest["temperature_c"],
        "humidity_pct": latest["humidity_pct"],
        "wind_speed_ms": latest["wind_speed_ms"],
        "rain_7d_mm": rain_7d,
        "et_7d_mm": et_7d,
    }

    watered_7d = watering_by_bed(observations, date.fromisoformat(last_7[0]["date"]), period_end)
    beds = compute_beds(planting_map, rain_7d, et_7d, watered_7d)
    headline, actions, why = build_advice(beds, rain_7d, et_7d, regional_7d)
    headline, why = phrase_with_llm(headline, why)

    outlook = build_outlook(weather, period_end)
    generated_at = datetime(period_end.year, period_end.month, period_end.day, tzinfo=timezone.utc) + timedelta(days=1, hours=6)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
        "headline_metrics": headline_metrics,
        "daily_series": daily_series,
        "outlook": outlook,
        "beds": [{"bed_id": b["bed_id"], "stress": b["stress"], "water_balance_mm": b["water_balance_mm"]} for b in beds],
        "advice": {"headline": headline, "actions": actions, "why": why},
        "_beds_full": beds,  # internal: carried through for briefing text only, stripped before write
        "_regional_7d": regional_7d,
    }


def human_date(d):
    return date.fromisoformat(d).strftime("%-d %B %Y")


def build_briefing(derived):
    p = derived["period"]
    hm = derived["headline_metrics"]
    series = derived["daily_series"]
    outlook = derived["outlook"]
    advice = derived["advice"]

    week_len = 7
    weeks = [series[i:i + week_len] for i in range(0, len(series), week_len)]
    week_nets = [round(sum(d["rain_site_mm"] - d["et_mm"] for d in w), 1) for w in weeks]
    week_trend = ", ".join(f"week {i+1} {abs(n)} mm short" if n < 0 else f"week {i+1} balanced" for i, n in enumerate(week_nets))
    widened = all(week_nets[i] >= week_nets[i + 1] for i in range(len(week_nets) - 1)) and len(week_nets) > 1

    this_week = (
        f"Over {human_date(series[-7]['date'])}–{human_date(p['end'])}, the site logged {hm['rain_7d_mm']} mm of rain "
        f"against {derived['_regional_7d']} mm recorded regionally over the same days — the site ran markedly drier "
        f"than the surrounding area. ET reached {hm['et_7d_mm']} mm over the same seven days, "
        f"outpacing rainfall as heat and wind pushed water demand up. Across the full three-week record ({week_trend}), "
        + ("the deficit widened week on week to this week's shortfall." if widened else
           "this week's shortfall was the sharpest of the three.")
    )
    outlook_text = (
        f"The week ahead ({human_date(outlook['period']['start'])}–{human_date(outlook['period']['end'])}) is forecast — "
        f"via the regional weather service, not site sensors — to bring {outlook['forecast_rain_mm']} mm of rain against "
        f"{outlook['forecast_et_mm']} mm of estimated ET. "
        + ("Given the site has run drier than the region this period, actual conditions may be drier still."
           if outlook['forecast_et_mm'] > outlook['forecast_rain_mm'] else
           "Rain is expected to help close the deficit.")
    )

    action_by_bed = {b["bed_id"]: b for b in derived["_beds_full"]}
    action_lines = []
    for a in advice["actions"]:
        bed = action_by_bed[a["bed_id"]]
        label = {"deep_water_and_mulch": "deep-water, then mulch", "deep_water": "deep-water", "none": "no action"}[a["action"]]
        action_lines.append(f"- {bed['name']}: {label}")

    numbers_table = (
        "| Metric | Value |\n| --- | --- |\n"
        f"| Temperature (°C) | {hm['temperature_c']} |\n"
        f"| Humidity (%) | {hm['humidity_pct']} |\n"
        f"| Wind speed (m/s) | {hm['wind_speed_ms']} |\n"
        f"| Rain, 7 days (mm) | {hm['rain_7d_mm']} |\n"
        f"| ET, 7 days (mm) | {hm['et_7d_mm']} |"
    )

    gen_dt = datetime.strptime(derived["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
    week_no = date.fromisoformat(p["end"]).isocalendar()[1]

    return f"""# Weekly briefing — week {week_no}, {date.fromisoformat(p['end']).year}

## This week

{this_week}

## Outlook

{outlook_text}

## Advice

{advice['headline']}

{chr(10).join(action_lines)}

## Why

{chr(10).join(f"- {w}" for w in advice['why'])}

## Numbers

{numbers_table}

Generated by the Agentic Garden pipeline on {gen_dt.strftime('%d-%m-%Y')}
"""


def main():
    sensor_series = load_json(DATA / "sensor_series.json")
    weather = load_json(DATA / "weather_regional.json")
    planting_map = load_json(DOCS_DATA / "planting_map.json")
    observations = load_json(DATA / "observations.json")

    derived = build_derived(sensor_series, weather, planting_map, observations)
    briefing_md = build_briefing(derived)

    derived_out = {k: v for k, v in derived.items() if not k.startswith("_")}
    (DOCS_DATA / "derived.json").write_text(json.dumps(derived_out, indent=2) + "\n")
    (DOCS_DATA / "briefing.md").write_text(briefing_md)

    # Verbatim trailing-week slice of the raw sensor payload — not a derived
    # value, just a windowed copy for the Trends tab's hourly-conditions
    # charts. Not one of the three frozen contracts (like planting_map.json).
    hourly_out = sensor_series[-HOURLY_WINDOW_HOURS:]
    (DOCS_DATA / "hourly.json").write_text(json.dumps(hourly_out, indent=2) + "\n")

    # Straight pass-through of the manual watering log — the "Observations"
    # mock source. Not a contract; the Trends chart overlays it for texture,
    # and it already feeds compute_beds() above via watering_by_bed().
    (DOCS_DATA / "observations.json").write_text(json.dumps(observations, indent=2) + "\n")

    print(f"beds: {[(b['bed_id'], b['stress']) for b in derived['_beds_full']]}")
    print(f"headline: {derived['advice']['headline']}")
    print(f"wrote docs/data/derived.json, docs/data/briefing.md, docs/data/hourly.json ({len(hourly_out)} readings), "
          f"docs/data/observations.json ({len(observations)} events)")


if __name__ == "__main__":
    main()
