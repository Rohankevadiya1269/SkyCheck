"""
Scoring and anomaly-detection logic shared by ingest.py (writes) and
app.py (reads/displays).

Two distinct things happen here, and it's worth keeping them mentally
separate (and honest about, if you're describing this project in an
interview):

1. `comfort_score()` is a transparent, hand-designed heuristic (0-100).
   It is NOT machine learning -- it's feature engineering / domain
   scoring, the same way you'd build a rule-based baseline before ever
   reaching for a model. It's what actually drives the "best time to be
   outside" ranking, because it's interpretable and users can trust it.

2. `flag_anomalies()` IS machine learning: an unsupervised Isolation
   Forest fit per city on that city's own accumulated history, used to
   flag when the *combination* of temperature / UV / AQI / PM2.5 is
   statistically unusual for that location -- not just "hot" or
   "polluted" in isolation, but an unusual joint pattern (e.g. unusually
   hot AND unusually polluted at the same time). This is the legitimate
   ML claim for the project.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

MIN_HISTORY_FOR_ML = 40  # need this many past readings for a city before IsolationForest is trustworthy
FEATURE_COLS = ["temperature_c", "uv_index", "us_aqi", "pm2_5"]


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def comfort_score(
    temperature_c: float | None,
    apparent_temp_c: float | None,
    precip_prob: float | None,
    uv_index: float | None,
    us_aqi: float | None,
) -> float:
    """
    Rule-based 0-100 'good time to be outside' score. Higher is better.
    Missing inputs are treated neutrally (score 70/100 for that factor)
    so one missing field from the API doesn't tank the whole score.
    """
    scores = []

    # Temperature comfort: peak comfort ~18-24C, tapering off outside that.
    t = apparent_temp_c if apparent_temp_c is not None else temperature_c
    if t is None:
        scores.append(70)
    else:
        if 18 <= t <= 24:
            scores.append(100)
        else:
            dist = min(abs(t - 18), abs(t - 24)) if t < 18 or t > 24 else 0
            scores.append(_clip(100 - dist * 4, 0, 100))

    # Precipitation: linear penalty by probability of rain.
    if precip_prob is None:
        scores.append(70)
    else:
        scores.append(_clip(100 - precip_prob, 0, 100))

    # UV index: 0-2 great, climbs steeply past 6 (high/very high/extreme).
    if uv_index is None:
        scores.append(70)
    else:
        if uv_index <= 2:
            scores.append(100)
        elif uv_index <= 5:
            scores.append(85)
        elif uv_index <= 7:
            scores.append(60)
        elif uv_index <= 10:
            scores.append(35)
        else:
            scores.append(10)

    # US AQI: EPA breakpoints (0-50 good ... 300+ hazardous).
    if us_aqi is None:
        scores.append(70)
    else:
        if us_aqi <= 50:
            scores.append(100)
        elif us_aqi <= 100:
            scores.append(80)
        elif us_aqi <= 150:
            scores.append(55)
        elif us_aqi <= 200:
            scores.append(30)
        elif us_aqi <= 300:
            scores.append(12)
        else:
            scores.append(2)

    return round(float(np.mean(scores)), 1)


def flag_anomalies(history_df: pd.DataFrame, latest_df: pd.DataFrame) -> pd.DataFrame:
    """
    Fit an IsolationForest on a city's historical readings and score the
    latest batch of readings against it.

    Parameters
    ----------
    history_df : past readings for ONE city (columns = FEATURE_COLS), used
                 to fit the model. Should already exclude rows being scored.
    latest_df   : the new readings for that same city to score (same columns,
                 plus it's fine if it has extra columns -- only FEATURE_COLS
                 are used for the model).

    Returns
    -------
    latest_df with two new columns added: is_anomaly (bool), anomaly_score (float)
    If there isn't enough history yet, is_anomaly=False / anomaly_score=NaN
    for every row (cold start -- nothing to compare against yet).
    """
    out = latest_df.copy()

    usable_history = history_df.dropna(subset=FEATURE_COLS)
    if len(usable_history) < MIN_HISTORY_FOR_ML:
        out["is_anomaly"] = False
        out["anomaly_score"] = np.nan
        return out

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,  # expect ~5% of readings to be flagged as unusual
        random_state=42,
    )
    model.fit(usable_history[FEATURE_COLS].values)

    scoreable = out.dropna(subset=FEATURE_COLS)
    if scoreable.empty:
        out["is_anomaly"] = False
        out["anomaly_score"] = np.nan
        return out

    preds = model.predict(scoreable[FEATURE_COLS].values)          # -1 = anomaly, 1 = normal
    scores = model.decision_function(scoreable[FEATURE_COLS].values)  # lower = more anomalous

    out.loc[scoreable.index, "is_anomaly"] = preds == -1
    out.loc[scoreable.index, "anomaly_score"] = scores
    out["is_anomaly"] = out["is_anomaly"].fillna(False)
    return out
