# Live Outdoor Conditions Advisor

A live dashboard that tells you the best times to be outside over the next
48 hours, for ~50 major world cities — combining real-time weather and air
quality data with an ML anomaly detector that flags when today's conditions
are statistically unusual for that city.

No sign-in, no data-science knowledge required to use it: pick a city, get
an answer.

## How it works

```
GitHub Actions (hourly cron)
        │
        ▼
   ingest.py  ──►  Open-Meteo weather + air-quality APIs (free, no key)
        │
        ▼
PostgreSQL (Neon/Supabase, free tier)
        │
        ├── comfort_score: transparent rule-based 0-100 score
        │   (temperature comfort + rain chance + UV + EPA AQI)
        │
        └── IsolationForest (scikit-learn): fit per city on that city's
            accumulated history, flags statistically unusual hours
        │
        ▼
   app.py (Streamlit) ──► public live dashboard
```

| File | Purpose |
|---|---|
| `cities.py` | curated list of ~50 tracked cities (name, country, lat/lon) |
| `schema.sql` | Postgres schema — run once against your database |
| `scoring.py` | comfort-score heuristic + Isolation Forest anomaly detection |
| `ingest.py` | pulls live data, scores it, writes to the database |
| `app.py` | the Streamlit dashboard |
| `.github/workflows/ingest.yml` | runs `ingest.py` every hour, automatically |
| `test_logic.py`, `test_db_roundtrip.py` | tests (mocked API, real SQL round-trip) |

## One-time setup (~15-20 minutes)

### 1. Create a free Postgres database

Go to **[neon.tech](https://neon.tech)** (or supabase.com — either works), sign
in with GitHub, create a new project. Copy the connection string it gives you
— it looks like:

```
postgresql://user:password@ep-xxxx.neon.tech/neondb?sslmode=require
```

### 2. Create the tables

Locally, with `psql` installed:

```bash
psql "<your connection string>" -f schema.sql
```

(No `psql` handy? Neon and Supabase both have a "SQL Editor" in their web
dashboard — paste the contents of `schema.sql` there and run it instead.)

### 3. Push this repo to GitHub

```bash
cd live-outdoor-advisor
git init
git add .
git commit -m "Live outdoor conditions advisor"
git branch -M main
git remote add origin https://github.com/Rohankevadiya1269/live-outdoor-advisor.git
git push -u origin main
```

### 4. Add your database URL as a GitHub secret

On the repo page: **Settings → Secrets and variables → Actions → New
repository secret**

- Name: `DATABASE_URL`
- Value: the connection string from step 1

This is what lets the hourly GitHub Actions job write live data in the
background, whether or not the dashboard is open.

### 5. Run ingestion once manually (don't wait for the hourly schedule)

Repo page → **Actions** tab → "Hourly live data ingestion" → **Run workflow**.
This populates the database with the first batch of live data so the
dashboard has something to show immediately.

(Anomaly flagging needs ~40 accumulated readings per city before it turns
on — it runs in "cold start / no flags yet" mode for the first couple of
days, which is expected and mentioned in the app itself.)

### 6. Deploy the dashboard — [share.streamlit.io](https://share.streamlit.io)

Sign in with GitHub → **New app** → pick this repo → main file path `app.py`
→ before clicking deploy, open **Advanced settings → Secrets** and paste:

```toml
DATABASE_URL = "postgresql://user:password@ep-xxxx.neon.tech/neondb?sslmode=require"
```

Deploy. You'll get a public URL like `https://<something>.streamlit.app` —
that's the link for your resume/LinkedIn.

## Running locally (optional, for development)

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in DATABASE_URL
export $(cat .env | xargs)
python ingest.py              # populate the database once
streamlit run app.py          # view at localhost:8501
```

## Tests

```bash
python test_logic.py          # comfort score + anomaly detection unit tests (mocked API)
python test_db_roundtrip.py   # full pipeline against a local SQLite DB (real SQL, mocked API)
```

## Notes on the ML

The comfort score is a transparent, hand-designed heuristic, not a trained
model — that's deliberate, since it's the number driving user-facing
recommendations and needs to stay interpretable. The actual machine
learning is the **Isolation Forest anomaly detector** in `scoring.py`: it's
fit per city on that city's own accumulated history and flags hours where
the *combination* of temperature, UV, AQI, and PM2.5 is statistically
unusual for that specific location — a legitimate unsupervised anomaly
detection use case, not just a threshold check.

## Data source

Weather and air-quality data: [Open-Meteo](https://open-meteo.com/) (free,
no API key required, CC-BY 4.0).
