"""
Integration tests for the three tools.

These tests touch the real database, vector store, and CSVs. They run
in a few seconds total. They prove three things end-to-end:

  1. Each tool returns the expected planted signal from the test data.
  2. Runtime security boundaries hold (read-only DB, column allow-list).
  3. The audit log records every call.
"""

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError, ProgrammingError

from backend.app.audit import tail
from backend.app.db import read_only_session
from backend.app.schemas import (
    Aggregation, ComputeAggregateInput, CsvFile,
    GroupBy, Metric, QueryMetricsInput,
    SearchDocumentsInput,
)
from backend.app.tools.compute_aggregate import compute_aggregate
from backend.app.tools.query_metrics import query_metrics
from backend.app.tools.search_documents import search_documents


# ---------- query_metrics ----------

class TestQueryMetrics:
    def test_returns_rows_for_genre_breakdown(self):
        result = query_metrics(QueryMetricsInput(
            metric=Metric.completion_rate,
            group_by=GroupBy.genre,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        ))
        assert result.row_count == 8
        assert {r.dimension for r in result.rows} >= {
            "Drama", "Sci-Fi", "Comedy", "Action",
        }

    def test_comedy_is_lowest_completion_in_2025(self):
        result = query_metrics(QueryMetricsInput(
            metric=Metric.completion_rate,
            group_by=GroupBy.genre,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        ))
        # rows are returned ordered DESC by value; comedy should be the last entry
        assert result.rows[-1].dimension == "Comedy"

    def test_dark_orbit_completion_higher_than_last_kingdom(self):
        dark_orbit = query_metrics(QueryMetricsInput(
            metric=Metric.completion_rate,
            movie_title="Dark Orbit",
        ))
        last_kingdom = query_metrics(QueryMetricsInput(
            metric=Metric.completion_rate,
            movie_title="Last Kingdom",
        ))
        assert dark_orbit.rows[0].value > 0.85
        assert last_kingdom.rows[0].value < 0.10

    def test_mumbai_leads_in_november_2025(self):
        result = query_metrics(QueryMetricsInput(
            metric=Metric.watch_count,
            group_by=GroupBy.city,
            start_date=date(2025, 11, 1),
            end_date=date(2025, 12, 1),
            limit=5,
        ))
        assert result.rows[0].dimension == "Mumbai"

    def test_limit_is_respected(self):
        result = query_metrics(QueryMetricsInput(
            metric=Metric.watch_count,
            group_by=GroupBy.movie,
            limit=3,
        ))
        assert result.row_count <= 3


class TestQueryMetricsSecurity:
    """Runtime security: read-only at the DB level."""

    def test_database_refuses_write_in_read_only_session(self):
        with pytest.raises((InternalError, ProgrammingError)):
            with read_only_session() as session:
                session.execute(text("DELETE FROM movies WHERE movie_id = 'M0001'"))
                session.commit()


# ---------- search_documents ----------

class TestSearchDocuments:
    def test_returns_chunks_for_stellar_run_query(self):
        result = search_documents(SearchDocumentsInput(
            query="what caused Stellar Run to start trending in 2025",
            k=3,
        ))
        assert result.chunk_count == 3
        sources = {c.source for c in result.chunks}
        # The campaign or quarterly report should be in there.
        assert sources & {
            "campaign_performance_stellar_run.pdf",
            "quarterly_report_q3_2025.pdf",
        }

    def test_top_chunk_is_relevant(self):
        result = search_documents(SearchDocumentsInput(
            query="what caused Stellar Run to start trending",
            k=1,
        ))
        # Cosine distance under 0.5 indicates a strong semantic match.
        assert result.chunks[0].distance < 0.5

    def test_source_filter_excludes_other_documents(self):
        result = search_documents(SearchDocumentsInput(
            query="anything about content",
            k=5,
            source_filter="policy_guidelines.pdf",
        ))
        assert all(c.source == "policy_guidelines.pdf" for c in result.chunks)


# ---------- compute_aggregate ----------

class TestComputeAggregate:
    def test_total_spend_by_channel_returns_all_channels(self):
        result = compute_aggregate(ComputeAggregateInput(
            file=CsvFile.marketing_spend,
            metric_column="spend_usd",
            aggregation=Aggregation.sum,
            group_by="channel",
            filter_column="movie_id",
            filter_value="M0001",
        ))
        # Six channels: YouTube, Instagram, TV, Print, Search, Display.
        assert result.row_count == 6

    def test_mumbai_leads_rolling_avg_watch_minutes(self):
        result = compute_aggregate(ComputeAggregateInput(
            file=CsvFile.regional_performance,
            metric_column="total_minutes_watched",
            aggregation=Aggregation.rolling_mean_4w,
            group_by="city",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 1),
            limit=5,
        ))
        assert result.rows[0].dimension == "Mumbai"


class TestComputeAggregateSecurity:
    """Runtime security: per-file column allow-list."""

    def test_rejects_disallowed_metric_column(self):
        with pytest.raises(ValueError, match="not allowed"):
            compute_aggregate(ComputeAggregateInput(
                file=CsvFile.marketing_spend,
                metric_column="password",
                aggregation=Aggregation.sum,
            ))

    def test_rejects_disallowed_group_by(self):
        with pytest.raises(ValueError, match="not allowed"):
            compute_aggregate(ComputeAggregateInput(
                file=CsvFile.marketing_spend,
                metric_column="spend_usd",
                aggregation=Aggregation.sum,
                group_by="secret_column",
            ))


# ---------- audit log ----------

class TestAuditLog:
    def test_query_metrics_call_is_audited(self):
        before = len(tail(1000))
        query_metrics(QueryMetricsInput(metric=Metric.watch_count))
        after = tail(2)
        assert any(e["tool"] == "query_metrics" for e in after)
        # Most recent entry should be ours and should have a result count.
        assert "result_rows" in after[-1]

    def test_failed_call_is_audited_with_error(self):
        try:
            compute_aggregate(ComputeAggregateInput(
                file=CsvFile.marketing_spend,
                metric_column="password",
                aggregation=Aggregation.sum,
            ))
        except ValueError:
            pass
        last = tail(1)[0]
        assert last["tool"] == "compute_aggregate"
        assert last["ok"] is False
        assert "error" in last