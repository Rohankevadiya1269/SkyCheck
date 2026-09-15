"""
Integration test: runs the real ingest.py pipeline (upsert_cities,
fetch + parse, comfort scoring, anomaly flagging, upsert_readings) against
a local SQLite database standing in for Postgres (SQLite supports the same
ON CONFLICT ... DO UPDATE syntax the app uses), with the Open-Meteo HTTP
calls mocked. Also verifies re-running ingestion updates existing rows
instead of duplicating them (upsert idempotency).

Run with: python test_db_roundtrip.py
"""
import os
import sys
from unittest.mock import patch, Mock
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, event

DB_FILE = "test_roundtrip.db"
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE}"

sys.path.insert(0, ".")

# SQLite-compatible version of schema.sql (SERIAL -> INTEGER PK autoincrement, TIMESTAMPTZ -> TEXT/DATETIME)
SQLITE_SCHEMA = """
CREATE TABLE cities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    UNIQUE (name, country)
);
CREATE TABLE readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    ts TIMESTAMP NOT NULL,
    temperature_c REAL,
    apparent_temp_c REAL,
    precip_prob REAL,
    uv_index REAL,
    pm2_5 REAL,
    us_aqi REAL,
    ozone REAL,
    comfort_score REAL,
    is_anomaly BOOLEAN DEFAULT 0,
    anomaly_score REAL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (city_id, ts)
);
"""

engine = create_engine(f"sqlite:///{DB_FILE}")


# SQLite has no now()/EXCLUDED-in-DO-UPDATE quirks handled below; register
# a `now()` function so the *unmodified* production query (which uses
# Postgres's now()) runs as-is against SQLite for this test.
@event.listens_for(engine, "connect")
def _register_now(dbapi_conn, conn_record):
    dbapi_conn.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())


with engine.begin() as conn:
    for stmt in SQLITE_SCHEMA.strip().split(";"):
        if stmt.strip():
            conn.execute(text(stmt))

import ingest
import importlib
importlib.reload(ingest)

# monkeypatch ingest.get_engine to return our sqlite engine
ingest.get_engine = lambda: engine

# --- mock the two Open-Meteo calls, same as test_logic.py -------------
rng = np.random.default_rng(7)
hours = pd.date_range(pd.Timestamp.utcnow().floor("h"), periods=48, freq="h")
time_strs = [h.strftime("%Y-%m-%dT%H:%M") for h in hours]
weather_json = {
    "hourly": {
        "time": time_strs,
        "temperature_2m": list(np.round(rng.normal(20, 3, 48), 1)),
        "apparent_temperature": list(np.round(rng.normal(19, 3, 48), 1)),
        "precipitation_probability": list(np.round(np.clip(rng.normal(20, 15, 48), 0, 100), 0)),
        "uv_index": list(np.round(np.clip(rng.normal(4, 2, 48), 0, 11), 1)),
    }
}
air_json = {
    "hourly": {
        "time": time_strs,
        "pm2_5": list(np.round(rng.normal(12, 4, 48), 1)),
        "us_aqi": list(np.round(rng.normal(45, 15, 48), 0)),
        "ozone": list(np.round(rng.normal(30, 8, 48), 1)),
    }
}


def fake_get(url, params=None, timeout=None):
    m = Mock()
    m.raise_for_status = lambda: None
    m.json = lambda: weather_json if "air-quality" not in url else air_json
    return m


# only run against the first 3 cities to keep the test fast
ingest.CITIES = ingest.CITIES[:3]

with patch("requests.get", side_effect=fake_get):
    ingest.run()

# --- verify data landed correctly --------------------------------------
with engine.begin() as conn:
    n_cities = conn.execute(text("SELECT COUNT(*) FROM cities")).scalar()
    n_readings = conn.execute(text("SELECT COUNT(*) FROM readings")).scalar()
    sample = pd.read_sql(text("SELECT * FROM readings LIMIT 5"), conn)

print(f"\ncities table rows: {n_cities} (expect 3)")
print(f"readings table rows: {n_readings} (expect ~90-144, i.e. up to 48 x 3 cities)")
print(sample[["city_id", "ts", "temperature_c", "comfort_score", "is_anomaly"]])

assert n_cities == 3
assert n_readings > 0

# --- run ingest a SECOND time to verify upsert (ON CONFLICT DO UPDATE) works ---
with patch("requests.get", side_effect=fake_get):
    ingest.run()

with engine.begin() as conn:
    n_readings_2 = conn.execute(text("SELECT COUNT(*) FROM readings")).scalar()
print(f"\nreadings table rows after 2nd run: {n_readings_2} (expect SAME as first run -- upsert, not duplicate)")
assert n_readings_2 == n_readings, "upsert failed -- rows duplicated instead of updated"

os.remove(DB_FILE)
print("\nDB ROUND-TRIP TEST PASSED (upsert + query logic verified against real SQL engine)")
