"""
Live Outdoor Conditions Advisor -- Streamlit dashboard.

Pick a city, see current conditions and the best (and worst) times to be
outside over the next two days, based on live weather + air-quality data.
Flags a warning banner when today's conditions are statistically unusual
for that city (Isolation Forest anomaly detection over accumulated
history -- see scoring.py for what "unusual" means here).

Deploy: push this repo to GitHub, connect it at share.streamlit.io, and
set DATABASE_URL in the app's Secrets. See README.md for the full walkthrough.
"""

import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Outdoor Conditions Advisor", page_icon="\U0001F324️", layout="wide")


@st.cache_resource
def get_engine():
    db_url = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL"))
    if not db_url:
        st.error("DATABASE_URL is not configured. Add it in Streamlit Cloud → Settings → Secrets.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, pool_pre_ping=True)


@st.cache_data(ttl=300)
def load_cities():
    engine = get_engine()
    with engine.begin() as conn:
        df = pd.read_sql(text("SELECT id, name, country FROM cities ORDER BY name"), conn)
    return df


@st.cache_data(ttl=300)
def load_readings(city_id: int):
    engine = get_engine()
    q = text(
        """
        SELECT ts, temperature_c, apparent_temp_c, precip_prob, uv_index,
               pm2_5, us_aqi, ozone, comfort_score, is_anomaly, anomaly_score
        FROM readings
        WHERE city_id = :city_id AND ts >= now() - interval '1 hour'
        ORDER BY ts ASC
        """
    )
    engine = get_engine()
    with engine.begin() as conn:
        df = pd.read_sql(q, conn, params={"city_id": city_id})
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def aqi_label(aqi):
    if aqi is None or pd.isna(aqi):
        return "n/a"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy (sensitive groups)"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


st.title("\U0001F324️ Live Outdoor Conditions Advisor")
st.caption(
    "Live weather + air-quality data, refreshed hourly. Pick a city to see the best times "
    "to be outside over the next two days."
)

cities_df = load_cities()
if cities_df.empty:
    st.warning(
        "No cities found yet. Run `python ingest.py` once (with DATABASE_URL set) to populate the database."
    )
    st.stop()

city_labels = [f"{r['name']}, {r['country']}" for _, r in cities_df.iterrows()]
choice = st.selectbox("City", city_labels, index=city_labels.index("Chicago, USA") if "Chicago, USA" in city_labels else 0)
city_row = cities_df.iloc[city_labels.index(choice)]

readings = load_readings(int(city_row["id"]))

if readings.empty:
    st.warning("No forecast data for this city yet -- the hourly ingestion job may not have run yet.")
    st.stop()

latest = readings.iloc[0]

if bool(latest["is_anomaly"]):
    st.error(
        "⚠️ Conditions right now are **statistically unusual** for this city "
        "compared to its recent history (flagged by an Isolation Forest anomaly model)."
    )

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Temperature", f"{latest['temperature_c']:.1f} °C" if pd.notna(latest["temperature_c"]) else "n/a")
col2.metric("Feels like", f"{latest['apparent_temp_c']:.1f} °C" if pd.notna(latest["apparent_temp_c"]) else "n/a")
col3.metric("Rain chance", f"{latest['precip_prob']:.0f}%" if pd.notna(latest["precip_prob"]) else "n/a")
col4.metric("UV index", f"{latest['uv_index']:.1f}" if pd.notna(latest["uv_index"]) else "n/a")
col5.metric(
    "Air quality (US AQI)",
    f"{latest['us_aqi']:.0f}" if pd.notna(latest["us_aqi"]) else "n/a",
    help=aqi_label(latest["us_aqi"]),
)

st.subheader(f"Comfort score right now: {latest['comfort_score']:.0f} / 100")
st.progress(min(max(int(latest["comfort_score"]), 0), 100) / 100)

st.subheader("Next 48 hours")
chart_df = readings.set_index("ts")[["comfort_score"]]
st.line_chart(chart_df, height=260)

best = readings.sort_values("comfort_score", ascending=False).head(3)
worst = readings.sort_values("comfort_score", ascending=True).head(3)

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Best times to be outside**")
    for _, r in best.iterrows():
        st.write(f"- {r['ts'].strftime('%a %I:%M %p UTC')} — score {r['comfort_score']:.0f}")
with c2:
    st.markdown("**Times to avoid**")
    for _, r in worst.iterrows():
        st.write(f"- {r['ts'].strftime('%a %I:%M %p UTC')} — score {r['comfort_score']:.0f}")

with st.expander("How this works"):
    st.markdown(
        """
- **Data**: live hourly weather and air-quality forecasts from the free [Open-Meteo](https://open-meteo.com) API,
  pulled every hour by a scheduled GitHub Actions job and stored in a PostgreSQL database.
- **Comfort score**: a transparent, rule-based 0-100 score combining temperature comfort, rain chance,
  UV exposure, and air quality (EPA AQI breakpoints).
- **Anomaly flag**: an unsupervised **Isolation Forest** (scikit-learn) is fit per city on that city's own
  accumulated history and flags hours where the *combination* of temperature / UV / AQI / PM2.5 is
  statistically unusual for that location -- not just "hot" or "polluted" in isolation.
- Data updates hourly. Timestamps shown in UTC.
        """
    )

st.caption("Built by Rohan Kevadiya · Data: Open-Meteo · Source: github.com/Rohankevadiya1269")
