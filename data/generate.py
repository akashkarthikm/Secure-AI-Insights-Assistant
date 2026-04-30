"""
Synthetic data generator for the Secure AI Insights Assistant.

Produces six CSVs under data/raw/ with deliberate signals:
  - Stellar Run: Q3 2025 watch spike correlated with marketing campaign
  - Dark Orbit: high completion rate, lower total watches
  - Last Kingdom: high total watches, lower completion rate
  - Comedy genre: underperforms across 2025
  - Mumbai: strongest engagement in the most recent month

Run: python data/generate.py
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# Determinism: same seed -> same data across runs.
SEED = 42
random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

OUT = Path(__file__).parent / "raw"
OUT.mkdir(parents=True, exist_ok=True)

GENRES = ["Drama", "Comedy", "Thriller", "Sci-Fi", "Action", "Romance", "Documentary", "Horror"]
LANGUAGES = ["English", "Hindi", "Spanish", "Korean", "French"]
TIERS = ["Free", "Standard", "Premium"]
DEVICES = ["Mobile", "Web", "TV", "Tablet"]
CHANNELS = ["YouTube", "Instagram", "TV", "Print", "Search", "Display"]
CITIES = [
    ("Mumbai", "India"), ("Delhi", "India"), ("Bangalore", "India"),
    ("New York", "USA"), ("Los Angeles", "USA"), ("Chicago", "USA"),
    ("London", "UK"), ("Manchester", "UK"),
    ("Berlin", "Germany"), ("Paris", "France"),
    ("Tokyo", "Japan"), ("Seoul", "South Korea"),
    ("Sao Paulo", "Brazil"), ("Mexico City", "Mexico"),
]

# ---------- movies ----------

def build_movies():
    """Catalog of ~60 titles. Three named titles are pinned with specific traits."""
    rows = []
    # Pinned titles required by the example questions.
    rows.append({
        "movie_id": "M0001", "title": "Stellar Run", "genre": "Sci-Fi",
        "release_date": "2025-06-15", "runtime_min": 128, "language": "English",
        "production_budget_usd": 80_000_000,
    })
    rows.append({
        "movie_id": "M0002", "title": "Dark Orbit", "genre": "Sci-Fi",
        "release_date": "2024-11-02", "runtime_min": 142, "language": "English",
        "production_budget_usd": 95_000_000,
    })
    rows.append({
        "movie_id": "M0003", "title": "Last Kingdom", "genre": "Drama",
        "release_date": "2025-02-20", "runtime_min": 156, "language": "English",
        "production_budget_usd": 60_000_000,
    })
    # Filler titles.
    for i in range(4, 61):
        genre = random.choice(GENRES)
        release = fake.date_between(start_date="-3y", end_date="today")
        rows.append({
            "movie_id": f"M{i:04d}",
            "title": fake.catch_phrase(),
            "genre": genre,
            "release_date": release.isoformat(),
            "runtime_min": random.randint(85, 170),
            "language": random.choice(LANGUAGES),
            "production_budget_usd": random.randint(2_000_000, 120_000_000),
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "movies.csv", index=False)
    print(f"  movies.csv         {len(df):>6} rows")
    return df

# ---------- viewers ----------

def build_viewers(n=5000):
    age_bands = ["18-24", "25-34", "35-44", "45-54", "55+"]
    rows = []
    for i in range(1, n + 1):
        city, country = random.choice(CITIES)
        rows.append({
            "viewer_id": f"V{i:06d}",
            "age_band": random.choices(age_bands, weights=[2, 4, 3, 2, 1])[0],
            "country": country,
            "city": city,
            "subscription_tier": random.choices(TIERS, weights=[1, 5, 3])[0],
            "signup_date": fake.date_between(start_date="-4y", end_date="-1d").isoformat(),
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "viewers.csv", index=False)
    print(f"  viewers.csv        {len(df):>6} rows")
    return df

# ---------- watch_activity ----------

def build_watch_activity(movies, viewers, n=50_000):
    """The fact table. Planted signals live here."""
    rows = []
    movie_ids = movies["movie_id"].tolist()
    runtime_by_movie = dict(zip(movies["movie_id"], movies["runtime_min"]))
    genre_by_movie = dict(zip(movies["movie_id"], movies["genre"]))
    viewer_ids = viewers["viewer_id"].tolist()
    viewer_city = dict(zip(viewers["viewer_id"], viewers["city"]))

    today = datetime(2025, 11, 30)  # treat "now" as end of Nov 2025

    for _ in range(n):
        movie_id = random.choice(movie_ids)
        viewer_id = random.choice(viewer_ids)
        runtime = runtime_by_movie[movie_id]
        genre = genre_by_movie[movie_id]
        city = viewer_city[viewer_id]

        watch_date = today - timedelta(days=random.randint(0, 540))

        # ---- planted signals ----
        # Stellar Run: watch-volume spike in Aug-Oct 2025.
        if movie_id == "M0001" and watch_date < datetime(2025, 8, 1):
            if random.random() < 0.7:
                continue  # suppress most pre-spike watches
        # Dark Orbit: high completion (~85%).
        if movie_id == "M0002":
            completion_pct = random.uniform(0.88, 0.99)
        # Last Kingdom: people start it but rarely finish - the "watched but didn't complete" pattern.
        elif movie_id == "M0003":
            completion_pct = random.uniform(0.25, 0.55)
        # Comedy: depressed completion in 2025.
        elif genre == "Comedy" and watch_date.year == 2025:
            completion_pct = random.uniform(0.20, 0.55)
        else:
            completion_pct = random.uniform(0.40, 0.95)

        # Mumbai boost in the most recent month (Nov 2025).
        if city == "Mumbai" and watch_date >= datetime(2025, 11, 1):
            completion_pct = min(0.99, completion_pct + 0.15)

        minutes_watched = int(runtime * completion_pct)
        completed = completion_pct >= 0.85

        rows.append({
            "viewer_id": viewer_id,
            "movie_id": movie_id,
            "watch_date": watch_date.date().isoformat(),
            "minutes_watched": minutes_watched,
            "completed": completed,
            "device": random.choice(DEVICES),
        })

    # Mumbai engagement boost: extra watches in Nov 2025 to lift volume too.
    mumbai_viewers = [v for v in viewer_ids if viewer_city[v] == "Mumbai"]
    for _ in range(2000):
        movie_id = random.choice(movie_ids)
        viewer_id = random.choice(mumbai_viewers)
        runtime = runtime_by_movie[movie_id]
        watch_date = today - timedelta(days=random.randint(0, 28))
        completion_pct = random.uniform(0.60, 0.99)
        rows.append({
            "viewer_id": viewer_id,
            "movie_id": movie_id,
            "watch_date": watch_date.date().isoformat(),
            "minutes_watched": int(runtime * completion_pct),
            "completed": completion_pct >= 0.85,
            "device": random.choice(DEVICES),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "watch_activity.csv", index=False)
    print(f"  watch_activity.csv {len(df):>6} rows")
    return df

# ---------- reviews ----------

def build_reviews(movies, viewers, watch):
    """Reviews mirror the watch quality signal."""
    rows = []
    sample = watch.sample(frac=0.08, random_state=SEED)  # ~8% of watches leave a review
    for _, w in sample.iterrows():
        movie_id = w["movie_id"]
        # Comedy in 2025 gets harsher reviews.
        movie_genre = movies.loc[movies.movie_id == movie_id, "genre"].iloc[0]
        watch_year = int(w["watch_date"][:4])
        if movie_genre == "Comedy" and watch_year == 2025:
            rating = random.choices([1, 2, 3, 4, 5], weights=[3, 4, 3, 1, 1])[0]
        elif movie_id == "M0001":  # Stellar Run gets buzz
            rating = random.choices([1, 2, 3, 4, 5], weights=[1, 1, 2, 5, 6])[0]
        elif movie_id == "M0002":  # Dark Orbit critically loved
            rating = random.choices([1, 2, 3, 4, 5], weights=[1, 1, 2, 4, 5])[0]
        else:
            rating = random.choices([1, 2, 3, 4, 5], weights=[1, 2, 3, 4, 3])[0]

        rows.append({
            "viewer_id": w["viewer_id"],
            "movie_id": movie_id,
            "rating": rating,
            "review_date": w["watch_date"],
            "sentiment_score": round(random.uniform(-1, 1) * 0.3 + (rating - 3) * 0.3, 3),
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "reviews.csv", index=False)
    print(f"  reviews.csv        {len(df):>6} rows")
    return df

# ---------- marketing_spend ----------

def build_marketing_spend(movies):
    """One row per (movie, week, channel, region) combination for a sample of titles."""
    rows = []
    weeks_2025 = pd.date_range("2025-01-06", "2025-11-24", freq="W-MON")
    regions = ["North America", "Europe", "India", "LATAM", "APAC"]

    # Stellar Run: heavy campaign in Jul-Sep 2025 (drives the trend signal).
    for week in weeks_2025:
        for region in regions:
            for channel in CHANNELS:
                if datetime(2025, 7, 1) <= week.to_pydatetime() <= datetime(2025, 9, 30):
                    spend = random.randint(15_000, 90_000)
                else:
                    spend = random.randint(0, 8_000)
                rows.append({
                    "campaign_id": f"C{len(rows)+1:05d}",
                    "movie_id": "M0001",
                    "channel": channel,
                    "region": region,
                    "week_start": week.date().isoformat(),
                    "spend_usd": spend,
                    "impressions": spend * random.randint(80, 200),
                })

    # Other titles: lighter, more uniform spend.
    sampled = movies.sample(20, random_state=SEED)
    for _, m in sampled.iterrows():
        if m["movie_id"] == "M0001":
            continue
        for week in random.sample(list(weeks_2025), 12):
            for region in random.sample(regions, 2):
                channel = random.choice(CHANNELS)
                spend = random.randint(2_000, 25_000)
                rows.append({
                    "campaign_id": f"C{len(rows)+1:05d}",
                    "movie_id": m["movie_id"],
                    "channel": channel,
                    "region": region,
                    "week_start": week.date().isoformat(),
                    "spend_usd": spend,
                    "impressions": spend * random.randint(80, 200),
                })

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "marketing_spend.csv", index=False)
    print(f"  marketing_spend.csv {len(df):>5} rows")
    return df

# ---------- regional_performance ----------

def build_regional_performance(watch, viewers, movies):
    """Pre-aggregated weekly view by city."""
    df = watch.merge(viewers[["viewer_id", "city"]], on="viewer_id")
    df = df.merge(movies[["movie_id", "genre"]], on="movie_id")
    df["watch_date"] = pd.to_datetime(df["watch_date"])
    df["week_start"] = df["watch_date"].dt.to_period("W-MON").apply(lambda r: r.start_time.date())

    agg = df.groupby(["city", "week_start"]).agg(
        total_minutes_watched=("minutes_watched", "sum"),
        unique_viewers=("viewer_id", "nunique"),
        top_genre=("genre", lambda s: s.value_counts().idxmax()),
    ).reset_index()

    agg.to_csv(OUT / "regional_performance.csv", index=False)
    print(f"  regional_performance.csv {len(agg):>4} rows")
    return agg

# ---------- main ----------

def main():
    print(f"Generating data into {OUT}/")
    movies = build_movies()
    viewers = build_viewers()
    watch = build_watch_activity(movies, viewers)
    build_reviews(movies, viewers, watch)
    build_marketing_spend(movies)
    build_regional_performance(watch, viewers, movies)
    print("done.")

if __name__ == "__main__":
    main()