"""
query_metrics — the SQL tool.

The LLM picks a metric (from Metric enum) and an optional group-by
(from GroupBy enum). The tool maps those to hardcoded SQL fragments,
binds user-supplied filter values as parameters, runs the query through
the read-only session, and returns typed rows.

What the LLM can influence:
  - which metric (allow-list)
  - which group-by dimension (allow-list)
  - filter values (genre, city, country, date range, movie title) — all bound
    as parameters, never concatenated into SQL
  - row limit (range-checked 1..500)

What the LLM cannot do:
  - write SQL
  - name a column or table
  - bypass the read-only transaction
  - return more than 500 rows
"""

from sqlalchemy import text

from backend.app.audit import audit
from backend.app.db import read_only_session
from backend.app.schemas import (
    GroupBy, Metric, MetricRow, QueryMetricsInput, QueryMetricsResult,
)


# ---------- SQL fragments ----------
#
# Each metric maps to a SELECT expression that produces a numeric value.
# Each group-by maps to a column expression and a join hint. These are
# the only fragments that ever reach the database; the LLM cannot
# influence their text.

_METRIC_SQL = {
    Metric.watch_count:     "COUNT(*)::float",
    Metric.completion_rate: "AVG(CASE WHEN w.completed THEN 1.0 ELSE 0.0 END)",
    Metric.avg_minutes:     "AVG(w.minutes_watched)::float",
    Metric.unique_viewers:  "COUNT(DISTINCT w.viewer_id)::float",
    # avg_rating is special: it queries the reviews table instead of watch_activity.
    Metric.avg_rating:      "AVG(r.rating)::float",
}

_GROUP_BY_SQL = {
    GroupBy.genre:    ("m.genre",                            {"movies"}),
    GroupBy.movie:    ("m.title",                            {"movies"}),
    GroupBy.city:     ("v.city",                             {"viewers"}),
    GroupBy.country:  ("v.country",                          {"viewers"}),
    GroupBy.age_band: ("v.age_band",                         {"viewers"}),
    GroupBy.month:    ("date_trunc('month', w.watch_date)",  set()),
    GroupBy.week:     ("date_trunc('week', w.watch_date)",   set()),
}


def _build_query(inp: QueryMetricsInput) -> tuple[str, dict]:
    """Return (sql, bind_params). All user-supplied values are in bind_params."""

    is_rating_metric = inp.metric == Metric.avg_rating
    base_table = "reviews r" if is_rating_metric else "watch_activity w"
    activity_alias = "r" if is_rating_metric else "w"
    date_col = f"{activity_alias}.{'review_date' if is_rating_metric else 'watch_date'}"

    metric_expr = _METRIC_SQL[inp.metric]

    # Decide which joins we need based on group-by and filter usage.
    needs_movies = (
        inp.group_by in (GroupBy.genre, GroupBy.movie)
        or inp.genre is not None
        or inp.movie_title is not None
    )
    needs_viewers = (
        inp.group_by in (GroupBy.city, GroupBy.country, GroupBy.age_band)
        or inp.city is not None
        or inp.country is not None
    )

    joins = []
    if needs_movies:
        joins.append(f"JOIN movies m ON m.movie_id = {activity_alias}.movie_id")
    if needs_viewers:
        joins.append(f"JOIN viewers v ON v.viewer_id = {activity_alias}.viewer_id")

    # WHERE clause: every value is a bind parameter.
    where = []
    params: dict = {}
    if inp.genre is not None:
        where.append("m.genre = :genre")
        params["genre"] = inp.genre
    if inp.movie_title is not None:
        where.append("m.title = :movie_title")
        params["movie_title"] = inp.movie_title
    if inp.city is not None:
        where.append("v.city = :city")
        params["city"] = inp.city
    if inp.country is not None:
        where.append("v.country = :country")
        params["country"] = inp.country
    if inp.start_date is not None:
        where.append(f"{date_col} >= :start_date")
        params["start_date"] = inp.start_date
    if inp.end_date is not None:
        where.append(f"{date_col} < :end_date")
        params["end_date"] = inp.end_date

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    join_sql = " ".join(joins)

    if inp.group_by is not None:
        dim_expr, _ = _GROUP_BY_SQL[inp.group_by]
        sql = f"""
            SELECT {dim_expr}::text AS dimension, {metric_expr} AS value
            FROM {base_table}
            {join_sql}
            {where_sql}
            GROUP BY {dim_expr}
            ORDER BY value DESC NULLS LAST
            LIMIT :limit
        """
    else:
        # No group-by: a single scalar wrapped as one row with dimension='all'.
        sql = f"""
            SELECT 'all'::text AS dimension, {metric_expr} AS value
            FROM {base_table}
            {join_sql}
            {where_sql}
            LIMIT :limit
        """

    params["limit"] = inp.limit
    return sql, params


def query_metrics(inp: QueryMetricsInput) -> QueryMetricsResult:
    """Run a metric query. Audited."""
    with audit("query_metrics", inp.model_dump(mode="json")) as record:
        sql, params = _build_query(inp)
        with read_only_session() as session:
            rows = session.execute(text(sql), params).all()

        result_rows = [
            MetricRow(
                dimension=str(r.dimension) if r.dimension is not None else "unknown",
                value=float(r.value) if r.value is not None else 0.0,
            )
            for r in rows
        ]
        record["result_rows"] = len(result_rows)

        return QueryMetricsResult(
            metric=inp.metric.value,
            group_by=inp.group_by.value if inp.group_by else None,
            rows=result_rows,
            row_count=len(result_rows),
        )