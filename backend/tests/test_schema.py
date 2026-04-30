"""
Validation tests for the tool input schemas.

These tests do not touch the database, the vector store, or the CSVs.
They prove that the Pydantic gate on each tool refuses out-of-bounds
input before any tool body runs. If these tests ever fail, the tool
layer's security promise is broken.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.schemas import (
    Aggregation, ComputeAggregateInput, CsvFile,
    GroupBy, Metric, QueryMetricsInput,
    SearchDocumentsInput,
)


# ---------- query_metrics ----------

class TestQueryMetricsInput:
    def test_minimal_valid(self):
        inp = QueryMetricsInput(metric=Metric.watch_count)
        assert inp.metric == Metric.watch_count
        assert inp.group_by is None
        assert inp.limit == 50

    def test_full_valid(self):
        inp = QueryMetricsInput(
            metric=Metric.completion_rate,
            group_by=GroupBy.genre,
            genre="Drama",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
            limit=100,
        )
        assert inp.group_by == GroupBy.genre
        assert inp.limit == 100

    def test_rejects_unknown_metric(self):
        with pytest.raises(ValidationError):
            QueryMetricsInput(metric="evil; DROP TABLE movies; --")

    def test_rejects_unknown_group_by(self):
        with pytest.raises(ValidationError):
            QueryMetricsInput(metric=Metric.watch_count, group_by="ssn")

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            QueryMetricsInput(metric=Metric.watch_count, sql_injection="anything")

    def test_rejects_limit_above_cap(self):
        with pytest.raises(ValidationError):
            QueryMetricsInput(metric=Metric.watch_count, limit=10_000)

    def test_rejects_limit_below_one(self):
        with pytest.raises(ValidationError):
            QueryMetricsInput(metric=Metric.watch_count, limit=0)

    def test_rejects_overlong_filter_values(self):
        with pytest.raises(ValidationError):
            QueryMetricsInput(metric=Metric.watch_count, genre="x" * 100)


# ---------- search_documents ----------

class TestSearchDocumentsInput:
    def test_minimal_valid(self):
        inp = SearchDocumentsInput(query="why is comedy weak")
        assert inp.k == 4
        assert inp.source_filter is None

    def test_rejects_too_short_query(self):
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="hi")

    def test_rejects_too_long_query(self):
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="x" * 1000)

    def test_rejects_k_out_of_range(self):
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="why is comedy weak", k=50)
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="why is comedy weak", k=0)

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            SearchDocumentsInput(query="ok", embed_path="/etc/passwd")


# ---------- compute_aggregate ----------

class TestComputeAggregateInput:
    def test_minimal_valid(self):
        inp = ComputeAggregateInput(
            file=CsvFile.marketing_spend,
            metric_column="spend_usd",
            aggregation=Aggregation.sum,
        )
        assert inp.file == CsvFile.marketing_spend

    def test_rejects_unknown_file(self):
        with pytest.raises(ValidationError):
            ComputeAggregateInput(
                file="../../etc/passwd",
                metric_column="spend_usd",
                aggregation=Aggregation.sum,
            )

    def test_rejects_unknown_aggregation(self):
        with pytest.raises(ValidationError):
            ComputeAggregateInput(
                file=CsvFile.marketing_spend,
                metric_column="spend_usd",
                aggregation="exec",
            )

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ComputeAggregateInput(
                file=CsvFile.marketing_spend,
                metric_column="spend_usd",
                aggregation=Aggregation.sum,
                shell_cmd="ls",
            )

    def test_rejects_overlong_column_names(self):
        with pytest.raises(ValidationError):
            ComputeAggregateInput(
                file=CsvFile.marketing_spend,
                metric_column="x" * 100,
                aggregation=Aggregation.sum,
            )