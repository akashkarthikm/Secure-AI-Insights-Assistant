"""
Database loader for the Secure AI Insights Assistant.

Reads the six CSVs under data/raw/ and loads them into the database
specified by DATABASE_URL in .env. Drops and recreates tables on each run
so phase 1 stays idempotent.

Run: python data/load_db.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Index,
    String, Integer, Date, Boolean, Numeric, BigInteger,
)

load_dotenv()

RAW = Path(__file__).parent / "raw"
DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
metadata = MetaData()

# ---------- schema ----------

movies = Table(
    "movies", metadata,
    Column("movie_id", String(8), primary_key=True),
    Column("title", String(200), nullable=False),
    Column("genre", String(40), nullable=False, index=True),
    Column("release_date", Date, nullable=False),
    Column("runtime_min", Integer, nullable=False),
    Column("language", String(40), nullable=False),
    Column("production_budget_usd", BigInteger, nullable=False),
)

viewers = Table(
    "viewers", metadata,
    Column("viewer_id", String(10), primary_key=True),
    Column("age_band", String(10), nullable=False, index=True),
    Column("country", String(60), nullable=False, index=True),
    Column("city", String(60), nullable=False, index=True),
    Column("subscription_tier", String(20), nullable=False),
    Column("signup_date", Date, nullable=False),
)

watch_activity = Table(
    "watch_activity", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("viewer_id", String(10), nullable=False, index=True),
    Column("movie_id", String(8), nullable=False, index=True),
    Column("watch_date", Date, nullable=False, index=True),
    Column("minutes_watched", Integer, nullable=False),
    Column("completed", Boolean, nullable=False),
    Column("device", String(20), nullable=False),
)
Index("ix_watch_movie_date", watch_activity.c.movie_id, watch_activity.c.watch_date)

reviews = Table(
    "reviews", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("viewer_id", String(10), nullable=False),
    Column("movie_id", String(8), nullable=False, index=True),
    Column("rating", Integer, nullable=False),
    Column("review_date", Date, nullable=False),
    Column("sentiment_score", Numeric(5, 3), nullable=False),
)

marketing_spend = Table(
    "marketing_spend", metadata,
    Column("campaign_id", String(10), primary_key=True),
    Column("movie_id", String(8), nullable=False, index=True),
    Column("channel", String(20), nullable=False),
    Column("region", String(40), nullable=False, index=True),
    Column("week_start", Date, nullable=False, index=True),
    Column("spend_usd", Integer, nullable=False),
    Column("impressions", BigInteger, nullable=False),
)

regional_performance = Table(
    "regional_performance", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("city", String(60), nullable=False, index=True),
    Column("week_start", Date, nullable=False, index=True),
    Column("total_minutes_watched", BigInteger, nullable=False),
    Column("unique_viewers", Integer, nullable=False),
    Column("top_genre", String(40), nullable=False),
)

# ---------- load ----------

CSV_TO_TABLE = [
    ("movies.csv", "movies", ["release_date"]),
    ("viewers.csv", "viewers", ["signup_date"]),
    ("watch_activity.csv", "watch_activity", ["watch_date"]),
    ("reviews.csv", "reviews", ["review_date"]),
    ("marketing_spend.csv", "marketing_spend", ["week_start"]),
    ("regional_performance.csv", "regional_performance", ["week_start"]),
]


def main():
    print(f"Connecting to {DATABASE_URL.split('@')[-1]}")

    # Drop and recreate everything. Phase 1 is reproducible from CSVs.
    print("Dropping and recreating schema...")
    metadata.drop_all(engine)
    metadata.create_all(engine)

    print("Loading CSVs...")
    for csv_name, table_name, date_cols in CSV_TO_TABLE:
        path = RAW / csv_name
        df = pd.read_csv(path, parse_dates=date_cols)
        # pandas reads dates as datetime; cast to date for proper Date columns.
        for col in date_cols:
            df[col] = df[col].dt.date
        df.to_sql(table_name, engine, if_exists="append", index=False, chunksize=5000)
        print(f"  {table_name:<22} {len(df):>6} rows")

    # Quick sanity: row counts straight from the database.
    print("Verifying...")
    from sqlalchemy import select, func
    with engine.connect() as conn:
        for _, table_name, _ in CSV_TO_TABLE:
            tbl = metadata.tables[table_name]
            count = conn.execute(select(func.count()).select_from(tbl)).scalar()
            print(f"  {table_name:<22} {count:>6} rows in db")
    print("done.")


if __name__ == "__main__":
    main()