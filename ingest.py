"""
Live data ingestion for the Outdoor Conditions Advisor.

Run manually:      python ingest.py
Run automatically: .github/workflows/ingest.yml (hourly, on GitHub's
                    runners -- this is the "live" part of the project;
                    the database keeps filling in even when nobody has
                    the dashboard open).

For every tracked city (cities.py) this script:
  1. Pulls a 48-hour hourly forecast for temperature / apparent temp /
     precipitation probability / UV index from Open-Meteo's free
     weather API (no key required).
  2. Pulls the matching 48-hour hourly air-quality forecast (PM2.5,
     US AQI, ozone) from Open-Meteo's free air-quality API.
  3. Computes a rule-based comfort_score for every hour (scoring.py).
  4. Upserts everything into the `readings` table.
  5. Re-fits an IsolationForest per city on that city's accumulated
     history and flags anomalous hours (scoring.py).

Requires a `DATABASE_URL` environment variable pointing at a Postgres
instance (Neon / Supabase both work), e.g.:
  postgresql://user:password@host/dbname?sslmode=require
"""

from __future__ import annotations
import os
import sys
import time
import requests
import pandas as pd
from sqlalchemy import create_engine, text

from cities import CITIES
from scoring import comfort_score, flag_anomalies, FEATURE_COLS

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
FORECAST_HOURS = 48
REQUEST_TIMEOUT = 20


def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL environment variable is not set.")
    # SQLAlchemy wants postgresql:// not postgres://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, pool_pre_ping=True)


def upsert_cities(engine):
    with engine.begin() as conn:
        for c in CITIES:
            conn.execute(
                text(
                    """
                    INSERT INTO cities (name, country, lat, lon)
                    VALUES (:name, :country, :lat, :lon)
                    ON CONFLICT (name, country) DO NOTHING
                    """
                ),
                c,
            )
        rows = conn.execute(text("SELECT id, name, country, lat, lon FROM cities")).mappings().all()
    return {(r["name"], r["country"]): r["id"] for r in rows}, rows


def fetch_city_forecast(lat: float, lon: float) -> pd.DataFrame | None:
    try:
        w = requests.get(
            WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,apparent_temperature,precipitation_probability,uv_index",
                "forecast_days": 2,
                "timezone": "UTC",
            },
            timeout=REQUEST_TIMEOUT,
        )
        w.raise_for_status()
        wj = w.json()["hourly"]

        a = requests.get(
            AIR_QUALITY_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "pm2_5,us_aqi,ozone",
                "forecast_days": 2,
                "timezone": "UTC",
            },
            timeout=REQUEST_TIMEOUT,
        )
        a.raise_for_status()
        aj = a.json()["hourly"]
    except requests.RequestException as e:
        print(f"  ! request failed: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"  ! unexpected API response shape: {e}")
        return None

    weather_df = pd.DataFrame(
        {
            "ts": pd.to_datetime(wj["time"], utc=True),
            "temperature_c": wj.get("temperature_2m"),
            "apparent_temp_c": wj.get("apparent_temperature"),
            "precip_prob": wj.get("precipitation_probability"),
            "uv_index": wj.get("uv_index"),
        }
    )
    air_df = pd.DataFrame(
        {
            "ts": pd.to_datetime(aj["time"], utc=True),
            "pm2_5": aj.get("pm2_5"),
            "us_aqi": aj.get("us_aqi"),
            "ozone": aj.get("ozone"),
        }
    )
    merged = weather_df.merge(air_df, on="ts", how="inner")
    # Keep only the next FORECAST_HOURS from "now" -- the API returns the
    # whole local day(s), including hours already in the past.
    now = pd.Timestamp.utcnow()
    merged = merged[merged["ts"] >= now.floor("h")].head(FORECAST_HOURS).reset_index(drop=True)
    return merged


def upsert_readings(engine, city_id: int, df: pd.DataFrame):
    if df.empty:
        return
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text(
                    """
                    INSERT INTO readings
                        (city_id, ts, temperature_c, apparent_temp_c, precip_prob,
                         uv_index, pm2_5, us_aqi, ozone, comfort_score,
                         is_anomaly, anomaly_score)
                    VALUES
                        (:city_id, :ts, :temperature_c, :apparent_temp_c, :precip_prob,
                         :uv_index, :pm2_5, :us_aqi, :ozone, :comfort_score,
                         :is_anomaly, :anomaly_score)
                    ON CONFLICT (city_id, ts) DO UPDATE SET
                        temperature_c   = EXCLUDED.temperature_c,
                        apparent_temp_c = EXCLUDED.apparent_temp_c,
                        precip_prob     = EXCLUDED.precip_prob,
                        uv_index        = EXCLUDED.uv_index,
                        pm2_5           = EXCLUDED.pm2_5,
                        us_aqi          = EXCLUDED.us_aqi,
                        ozone           = EXCLUDED.ozone,
                        comfort_score   = EXCLUDED.comfort_score,
                        is_anomaly      = EXCLUDED.is_anomaly,
                        anomaly_score   = EXCLUDED.anomaly_score,
                        fetched_at      = now()
                    """
                ),
                {
                    "city_id": city_id,
                    "ts": row["ts"].to_pydatetime(),
                    "temperature_c": row.get("temperature_c"),
                    "apparent_temp_c": row.get("apparent_temp_c"),
                    "precip_prob": row.get("precip_prob"),
                    "uv_index": row.get("uv_index"),
                    "pm2_5": row.get("pm2_5"),
                    "us_aqi": row.get("us_aqi"),
                    "ozone": row.get("ozone"),
                    "comfort_score": row.get("comfort_score"),
                    "is_anomaly": bool(row.get("is_anomaly", False)),
                    "anomaly_score": row.get("anomaly_score"),
                },
            )


def load_history(engine, city_id: int, exclude_ts) -> pd.DataFrame:
    q = text(
        """
        SELECT temperature_c, uv_index, us_aqi, pm2_5
        FROM readings
        WHERE city_id = :city_id AND ts < :cutoff
        """
    )
    with engine.begin() as conn:
        df = pd.read_sql(q, conn, params={"city_id": city_id, "cutoff": exclude_ts})
    return df


def run():
    engine = get_engine()
    city_ids, _ = upsert_cities(engine)
    print(f"Tracking {len(city_ids)} cities.")

    for c in CITIES:
        key = (c["name"], c["country"])
        city_id = city_ids.get(key)
        if city_id is None:
            print(f"  ! could not resolve city id for {key}, skipping")
            continue

        print(f"[{c['name']}, {c['country']}] fetching forecast...")
        df = fetch_city_forecast(c["lat"], c["lon"])
        if df is None or df.empty:
            print("  ! no data returned, skipping")
            continue

        df["comfort_score"] = df.apply(
            lambda r: comfort_score(
                r["temperature_c"], r["apparent_temp_c"], r["precip_prob"], r["uv_index"], r["us_aqi"]
            ),
            axis=1,
        )

        earliest_ts = df["ts"].min().to_pydatetime()
        history = load_history(engine, city_id, earliest_ts)
        df = flag_anomalies(history, df)

        upsert_readings(engine, city_id, df)
        n_anom = int(df["is_anomaly"].sum())
        print(f"  wrote {len(df)} rows ({n_anom} flagged anomalous)")

        time.sleep(0.5)  # be polite to the free API

    print("Done.")


if __name__ == "__main__":
    run()
