"""
Unit tests for scoring.py and the fetch_city_forecast() parsing logic in
ingest.py. The Open-Meteo HTTP calls are mocked so these tests run fast,
offline, and deterministically (no dependency on a third-party API being
up) -- run with: python test_logic.py
"""
import sys
from unittest.mock import patch, Mock
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from scoring import comfort_score, flag_anomalies, FEATURE_COLS

# --- 1. comfort_score sanity checks -----------------------------------
print("comfort_score tests:")
perfect = comfort_score(21, 21, 0, 1, 20)
print(f"  ideal conditions -> {perfect} (expect high, ~95-100)")
assert perfect > 90

bad = comfort_score(38, 41, 80, 11, 250)
print(f"  heatwave+smog+rain -> {bad} (expect low, <20)")
assert bad < 20

missing = comfort_score(None, None, None, None, None)
print(f"  all missing -> {missing} (expect neutral ~70)")
assert 65 <= missing <= 75
print("  OK\n")

# --- 2. flag_anomalies with insufficient history -----------------------
print("flag_anomalies cold-start test:")
latest = pd.DataFrame({c: [20.0] for c in FEATURE_COLS})
short_history = pd.DataFrame({c: np.random.rand(5) * 20 for c in FEATURE_COLS})
result = flag_anomalies(short_history, latest)
assert result["is_anomaly"].iloc[0] == False
print("  OK (correctly skips ML with <40 history rows)\n")

# --- 3. flag_anomalies with enough history + an obvious outlier --------
print("flag_anomalies with sufficient history + obvious outlier:")
rng = np.random.default_rng(42)
normal_history = pd.DataFrame(
    {
        "temperature_c": rng.normal(20, 3, 200),
        "uv_index": rng.normal(4, 1, 200),
        "us_aqi": rng.normal(40, 10, 200),
        "pm2_5": rng.normal(10, 3, 200),
    }
)
latest_batch = pd.DataFrame(
    {
        "temperature_c": [20.5, 45.0],   # second row = extreme outlier
        "uv_index": [4.1, 11.0],
        "us_aqi": [42.0, 400.0],
        "pm2_5": [9.5, 250.0],
    }
)
result = flag_anomalies(normal_history, latest_batch)
print(result[["temperature_c", "us_aqi", "is_anomaly", "anomaly_score"]])
assert result["is_anomaly"].iloc[0] == False, "normal reading was wrongly flagged"
assert result["is_anomaly"].iloc[1] == True, "obvious outlier was NOT flagged"
print("  OK (normal reading passed, extreme outlier correctly flagged)\n")

# --- 4. mocked Open-Meteo response -> fetch_city_forecast parsing ------
print("fetch_city_forecast() parsing test (mocked HTTP):")

hours = pd.date_range("2026-09-15T00:00:00Z", periods=48, freq="h")
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


with patch("requests.get", side_effect=fake_get):
    import importlib
    import ingest
    importlib.reload(ingest)
    df = ingest.fetch_city_forecast(41.88, -87.63)

assert df is not None and not df.empty, "parsing returned no rows"
assert set(["ts", "temperature_c", "apparent_temp_c", "precip_prob", "uv_index", "pm2_5", "us_aqi", "ozone"]).issubset(df.columns)
print(f"  parsed {len(df)} hourly rows, columns OK")
print(df.head(3))
print("  OK\n")

print("ALL LOGIC TESTS PASSED")
