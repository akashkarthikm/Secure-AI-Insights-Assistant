"""
Shared Pydantic schemas for the tool layer.

The principle: every value the LLM can pass to a tool is either an
Enum member (validated against an allow-list) or a primitive type with
range checks. There are no free-text fields the LLM controls that
become SQL fragments, file paths, or column names. Validation failures
raise pydantic.ValidationError before any tool body runs.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class Metric(str, Enum):
    """Allowed metrics for query_metrics."""
    watch_count = "watch_count"
    completion_rate = "completion_rate"
    avg_minutes = "avg_minutes"
    unique_viewers = "unique_viewers"
    avg_rating = "avg_rating"


class GroupBy(str, Enum):
    """Allowed group-by dimensions for query_metrics."""
    genre = "genre"
    movie = "movie"
    city = "city"
    country = "country"
    age_band = "age_band"
    month = "month"
    week = "week"


class QueryMetricsInput(BaseModel):
    """Input to query_metrics. LLM constructs this from its tool call."""
    model_config = ConfigDict(extra="forbid")  # reject unknown fields

    metric: Metric
    group_by: Optional[GroupBy] = None
    genre: Optional[str] = Field(default=None, max_length=40)
    movie_title: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=60)
    country: Optional[str] = Field(default=None, max_length=60)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = Field(default=50, ge=1, le=500)


class MetricRow(BaseModel):
    """One row of metric output. The LLM sees a list of these."""
    dimension: str
    value: float
    extra: Optional[dict] = None


class QueryMetricsResult(BaseModel):
    metric: str
    group_by: Optional[str]
    rows: list[MetricRow]
    row_count: int

class SearchDocumentsInput(BaseModel):
    """Input to search_documents."""
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=500)
    k: int = Field(default=4, ge=1, le=10)
    source_filter: Optional[str] = Field(default=None, max_length=100)


class DocumentChunk(BaseModel):
    text: str
    source: str
    doc_title: str
    chunk_index: int
    distance: float


class SearchDocumentsResult(BaseModel):
    query: str
    chunks: list[DocumentChunk]
    chunk_count: int

class CsvFile(str, Enum):
    """Allowed CSV files for compute_aggregate."""
    marketing_spend = "marketing_spend"
    regional_performance = "regional_performance"


class Aggregation(str, Enum):
    """Allowed aggregation operations."""
    sum = "sum"
    mean = "mean"
    count = "count"
    rolling_mean_4w = "rolling_mean_4w"
    week_over_week_pct = "week_over_week_pct"


class ComputeAggregateInput(BaseModel):
    """Input to compute_aggregate."""
    model_config = ConfigDict(extra="forbid")

    file: CsvFile
    metric_column: str = Field(min_length=1, max_length=50)
    aggregation: Aggregation
    group_by: Optional[str] = Field(default=None, max_length=50)
    filter_column: Optional[str] = Field(default=None, max_length=50)
    filter_value: Optional[str] = Field(default=None, max_length=200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = Field(default=50, ge=1, le=500)


class AggregateRow(BaseModel):
    dimension: str
    value: float


class ComputeAggregateResult(BaseModel):
    file: str
    metric_column: str
    aggregation: str
    rows: list[AggregateRow]
    row_count: int