"""
compute_aggregate — the CSV analytics tool.

The LLM picks a CSV file (from CsvFile enum), names a metric column and
optional group-by and filter, and chooses an aggregation (from
Aggregation enum). The tool loads the CSV, validates that all named
columns are in the per-file allow-list, applies filters and grouping,
and returns the result.

The per-file ALLOWED_COLUMNS dictionary is the security gate. Even
though metric_column and group_by are free-text strings in the schema,
they cannot reach pandas without first matching a hardcoded entry in
this file. There is no path from LLM input to arbitrary column access.

CSVs are cached in memory after first load. Phase 5 will add file-mtime
checking; for now, restart the process to pick up data regeneration.
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.app.audit import audit
from backend.app.schemas import (
    AggregateRow, Aggregation, ComputeAggregateInput,
    ComputeAggregateResult, CsvFile,
)

CSV_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"

# Per-file allow-list: which columns the LLM may name for metric_column,
# group_by, filter_column. The first column in each list is the natural
# date column for that file (used by date filters and rolling/wow ops).
ALLOWED_COLUMNS: dict[CsvFile, dict[str, list[str]]] = {
    CsvFile.marketing_spend: {
        "date_column": "week_start",
        "metric": ["spend_usd", "impressions"],
        "group_by": ["movie_id", "channel", "region", "week_start"],
        "filter": ["movie_id", "channel", "region"],
    },
    CsvFile.regional_performance: {
        "date_column": "week_start",
        "metric": ["total_minutes_watched", "unique_viewers"],
        "group_by": ["city", "week_start", "top_genre"],
        "filter": ["city", "top_genre"],
    },
}


@lru_cache(maxsize=4)
def _load_csv(file: CsvFile) -> pd.DataFrame:
    path = CSV_ROOT / f"{file.value}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"CSV not found at {path}. Run data/generate.py first."
        )
    df = pd.read_csv(path)
    date_col = ALLOWED_COLUMNS[file]["date_column"]
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
    return df


def _validate_columns(inp: ComputeAggregateInput) -> None:
    """Raise ValueError if any named column is outside the per-file allow-list."""
    spec = ALLOWED_COLUMNS[inp.file]
    if inp.metric_column not in spec["metric"]:
        raise ValueError(
            f"metric_column {inp.metric_column!r} not allowed for {inp.file.value}. "
            f"Allowed: {spec['metric']}"
        )
    if inp.group_by is not None and inp.group_by not in spec["group_by"]:
        raise ValueError(
            f"group_by {inp.group_by!r} not allowed for {inp.file.value}. "
            f"Allowed: {spec['group_by']}"
        )
    if inp.filter_column is not None and inp.filter_column not in spec["filter"]:
        raise ValueError(
            f"filter_column {inp.filter_column!r} not allowed for {inp.file.value}. "
            f"Allowed: {spec['filter']}"
        )


def _apply_filters(df: pd.DataFrame, inp: ComputeAggregateInput) -> pd.DataFrame:
    spec = ALLOWED_COLUMNS[inp.file]
    date_col = spec["date_column"]

    if inp.filter_column and inp.filter_value is not None:
        df = df[df[inp.filter_column] == inp.filter_value]
    if inp.start_date is not None and date_col in df.columns:
        df = df[df[date_col] >= pd.Timestamp(inp.start_date)]
    if inp.end_date is not None and date_col in df.columns:
        df = df[df[date_col] < pd.Timestamp(inp.end_date)]
    return df


def _aggregate(df: pd.DataFrame, inp: ComputeAggregateInput) -> list[AggregateRow]:
    spec = ALLOWED_COLUMNS[inp.file]
    date_col = spec["date_column"]
    col = inp.metric_column
    agg = inp.aggregation

    # Time-series aggregations require a date dimension.
    if agg in (Aggregation.rolling_mean_4w, Aggregation.week_over_week_pct):
        # If a group-by is given, do the time-series op per group.
        # Otherwise, sum across all rows per week first, then apply the op.
        if inp.group_by and inp.group_by != date_col:
            grouped = (
                df.groupby([inp.group_by, date_col])[col]
                .sum()
                .reset_index()
                .sort_values(date_col)
            )
            out_rows: list[AggregateRow] = []
            for key, sub in grouped.groupby(inp.group_by):
                series = sub.set_index(date_col)[col].sort_index()
                if agg == Aggregation.rolling_mean_4w:
                    transformed = series.rolling(4, min_periods=1).mean()
                else:
                    transformed = series.pct_change() * 100
                latest = transformed.dropna().iloc[-1] if not transformed.dropna().empty else 0.0
                out_rows.append(AggregateRow(dimension=str(key), value=float(latest)))
            out_rows.sort(key=lambda r: r.value, reverse=True)
            return out_rows[: inp.limit]
        else:
            series = (
                df.groupby(date_col)[col].sum().sort_index()
            )
            if agg == Aggregation.rolling_mean_4w:
                transformed = series.rolling(4, min_periods=1).mean()
            else:
                transformed = series.pct_change() * 100
            transformed = transformed.dropna()
            return [
                AggregateRow(dimension=str(idx.date()), value=float(val))
                for idx, val in transformed.tail(inp.limit).items()
            ]

    # Plain aggregations.
    if inp.group_by:
        grouped = df.groupby(inp.group_by)[col]
        if agg == Aggregation.sum:
            series = grouped.sum()
        elif agg == Aggregation.mean:
            series = grouped.mean()
        else:  # count
            series = grouped.count()
        series = series.sort_values(ascending=False).head(inp.limit)
        return [
            AggregateRow(dimension=str(idx), value=float(val))
            for idx, val in series.items()
        ]
    else:
        if agg == Aggregation.sum:
            value = df[col].sum()
        elif agg == Aggregation.mean:
            value = df[col].mean()
        else:
            value = df[col].count()
        return [AggregateRow(dimension="all", value=float(value))]


def compute_aggregate(inp: ComputeAggregateInput) -> ComputeAggregateResult:
    with audit("compute_aggregate", inp.model_dump(mode="json")) as record:
        _validate_columns(inp)
        df = _load_csv(inp.file)
        df = _apply_filters(df, inp)
        rows = _aggregate(df, inp)

        record["result_rows"] = len(rows)

        return ComputeAggregateResult(
            file=inp.file.value,
            metric_column=inp.metric_column,
            aggregation=inp.aggregation.value,
            rows=rows,
            row_count=len(rows),
        )