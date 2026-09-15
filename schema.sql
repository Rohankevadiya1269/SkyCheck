-- Live Outdoor Conditions Advisor -- database schema (PostgreSQL)
-- Run this once against your Neon/Supabase Postgres database before the
-- first ingestion run:
--   psql "$DATABASE_URL" -f schema.sql

CREATE TABLE IF NOT EXISTS cities (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    UNIQUE (name, country)
);

CREATE TABLE IF NOT EXISTS readings (
    id               BIGSERIAL PRIMARY KEY,
    city_id          INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    ts               TIMESTAMPTZ NOT NULL,          -- forecast/observation hour
    temperature_c    DOUBLE PRECISION,
    apparent_temp_c  DOUBLE PRECISION,
    precip_prob      DOUBLE PRECISION,               -- % chance of precipitation
    uv_index         DOUBLE PRECISION,
    pm2_5            DOUBLE PRECISION,
    us_aqi           DOUBLE PRECISION,
    ozone            DOUBLE PRECISION,
    comfort_score    DOUBLE PRECISION,                -- 0-100 rule-based "good time to be outside" score
    is_anomaly       BOOLEAN DEFAULT FALSE,            -- flagged by IsolationForest
    anomaly_score    DOUBLE PRECISION,                 -- raw IsolationForest decision_function score
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (city_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_readings_city_ts   ON readings (city_id, ts);
CREATE INDEX IF NOT EXISTS idx_readings_city_anom  ON readings (city_id, is_anomaly);
