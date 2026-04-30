"""
Tool registry for the orchestrator.

Each entry binds a tool name (the string the LLM emits in a tool call)
to its Pydantic input schema and the Python function that implements
it. The registry produces:

  - tool_definitions(): list of Anthropic-format tool defs
  - dispatch(name, args): validate args, run the tool, return JSON-able result

There is no path from an LLM tool call to a Python function that does
not go through dispatch(), which means there is no path that bypasses
Pydantic validation.
"""

from typing import Any, Callable, TypedDict

from pydantic import BaseModel

from backend.app.schemas import (
    ComputeAggregateInput, QueryMetricsInput, SearchDocumentsInput,
)
from backend.app.tools.compute_aggregate import compute_aggregate
from backend.app.tools.query_metrics import query_metrics
from backend.app.tools.search_documents import search_documents


class ToolEntry(TypedDict):
    description: str
    input_model: type[BaseModel]
    func: Callable[[Any], BaseModel]


# Descriptions are the text the LLM reads when deciding which tool to call.
# Be specific about what the tool does, what dimensions and metrics are
# available, and what kind of question it answers. Vague descriptions
# produce wrong tool choices.

REGISTRY: dict[str, ToolEntry] = {
    "query_metrics": {
        "description": (
            "Query aggregated business metrics from the structured database. "
            "Use this to answer quantitative questions about watch volume, "
            "completion rates, viewer counts, and average ratings. "
            "Metrics: watch_count, completion_rate, avg_minutes, unique_viewers, avg_rating. "
            "Group by: genre, movie, city, country, age_band, month, week. "
            "Filter by genre, movie title, city, country, or date range. "
            "Returns a list of (dimension, value) rows. "
            "Examples: 'completion rate by genre in 2025', 'top cities by watch count last month', "
            "'monthly watches for Stellar Run'."
        ),
        "input_model": QueryMetricsInput,
        "func": query_metrics,
    },
    "search_documents": {
        "description": (
            "Search internal business documents (quarterly reports, campaign summaries, "
            "content roadmap, policy guidelines, audience behavior report) for qualitative "
            "context that explains the WHY behind metrics. Use this when a question asks "
            "about reasons, narratives, plans, policies, or strategic context that the "
            "structured database cannot provide. Returns relevant text chunks with source "
            "document names. Optionally filter by source filename to look in a specific "
            "document. "
            "Examples: 'why is Stellar Run trending', 'what does the policy say about "
            "viewer data', 'what's planned for 2026'."
        ),
        "input_model": SearchDocumentsInput,
        "func": search_documents,
    },
    "compute_aggregate": {
        "description": (
            "Compute analytical aggregations on flat-file business data (marketing spend "
            "and regional performance CSVs). Supports sum, mean, count, 4-week rolling "
            "mean, and week-over-week percent change. Use this for time-series analysis "
            "(rolling averages, growth rates) and for marketing-spend or regional "
            "questions that require pandas-style operations. "
            "Files: marketing_spend (columns: spend_usd, impressions; group by movie_id, "
            "channel, region, week_start), regional_performance (columns: total_minutes_watched, "
            "unique_viewers; group by city, week_start, top_genre). "
            "Examples: 'rolling 4-week marketing spend for Stellar Run', 'week-over-week "
            "viewer growth by city', 'total spend by channel'."
        ),
        "input_model": ComputeAggregateInput,
        "func": compute_aggregate,
    },
}


def tool_definitions() -> list[dict]:
    """Return the registry as Anthropic-format tool definitions.

    Anthropic's tool-use API expects:
      {"name": str, "description": str, "input_schema": JSON Schema dict}
    """
    defs = []
    for name, entry in REGISTRY.items():
        schema = entry["input_model"].model_json_schema()
        # Anthropic doesn't use $defs at the top level; flatten if present
        # by inlining definitions. For our schemas this is automatic because
        # Pydantic embeds enums by ref, which Anthropic accepts as-is.
        defs.append({
            "name": name,
            "description": entry["description"],
            "input_schema": schema,
        })
    return defs


def dispatch(name: str, raw_args: dict) -> dict:
    """Validate args against the tool's Pydantic schema, run it, return JSON.

    Raises:
      KeyError: tool name not in registry
      pydantic.ValidationError: args fail schema validation
      Exception: any error raised by the tool itself
    """
    if name not in REGISTRY:
        raise KeyError(f"unknown tool: {name}")

    entry = REGISTRY[name]
    validated = entry["input_model"](**raw_args)  # raises ValidationError on bad args
    result: BaseModel = entry["func"](validated)
    return result.model_dump(mode="json")