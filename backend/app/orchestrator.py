"""
LLM orchestration loop.

answer_question(question) sends the question to Claude with our three
tools attached. Claude decides which to call, in what order. The loop
runs each tool through the registry's dispatch (which validates input
via Pydantic) and feeds the result back. The loop ends when Claude
returns a plain-text response instead of another tool call.

Returns: final answer text, the full trace, and the list of sources cited.
"""

import json
import logging
import os

import anthropic
from pydantic import ValidationError

from backend.app.registry import dispatch, tool_definitions
from backend.app.schemas import ToolTraceEntry

log = logging.getLogger("orchestrator")

MODEL = "claude-sonnet-4-5-20250929"
MAX_ITERATIONS = 8  # safety cap; real questions need 1-4 tool calls
MAX_TOKENS = 2048

SYSTEM_PROMPT = """You are an internal analytics assistant for a streaming entertainment company. You answer business questions about movies, viewers, watch activity, marketing, and regional performance.

You have three tools:
  - query_metrics: aggregated metrics from the structured database
  - search_documents: qualitative context from internal PDF reports
  - compute_aggregate: pandas-style analytics on marketing-spend and regional CSVs

Behavior rules:
  1. Ground every claim in tool results. Do not state numbers, names, or facts that did not come from a tool call. If you don't have the data to answer, say so.
  2. For "why" or "explain" questions, call search_documents to get the qualitative reason, and back it up with query_metrics or compute_aggregate to confirm the quantitative pattern.
  3. For comparison questions ("X vs Y"), call query_metrics with each side and compare the returned values.
  4. Cite the document filename whenever you use a fact from search_documents. Format: "(source: quarterly_report_q3_2025.pdf)".
  5. Keep answers concise — typically 3-6 sentences. Lead with the direct answer; follow with the supporting evidence.
  6. If a question is outside scope (general knowledge, opinions, anything unrelated to the company's data), politely decline.

The current reference date inside the data is end of November 2025."""


_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def _cached_tool_definitions() -> list[dict]:
    """Tool defs with a cache marker on the last entry so the whole tools
    block is cached as a single prefix."""
    defs = tool_definitions()
    if defs:
        defs[-1] = {**defs[-1], "cache_control": {"type": "ephemeral"}}
    return defs

def _summarize_result(result: dict) -> str:
    """Produce a one-line description of a tool result for the trace UI."""
    if "row_count" in result:
        return f"{result['row_count']} row(s)"
    if "chunk_count" in result:
        sources = sorted({c["source"] for c in result.get("chunks", [])})
        return f"{result['chunk_count']} chunk(s) from {len(sources)} source(s)"
    return "ok"

def _is_chartable(result: dict) -> bool:
    """Decide whether a tool result is worth surfacing as a chart in the UI.

    query_metrics and compute_aggregate return rows; search_documents returns
    chunks (not chartable). We also skip single-row scalar results.
    """
    rows = result.get("rows")
    return isinstance(rows, list) and len(rows) >= 2

def answer_question(question: str) -> tuple[str, list[ToolTraceEntry], list[str]]:
    """Run the tool-calling loop until Claude produces a final answer."""
    messages: list[dict] = [{"role": "user", "content": question}]
    trace: list[ToolTraceEntry] = []
    sources: set[str] = set()

    for iteration in range(MAX_ITERATIONS):
        log.info("iteration %d, %d message(s) in context", iteration, len(messages))

        response = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=_cached_tool_definitions(),
            messages=messages,
        )

        # Append the assistant's full response (text + tool_use blocks) to the conversation.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Final answer: pull the text content out.
            text_parts = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_parts).strip(), trace, sorted(sources)

        if response.stop_reason != "tool_use":
            # Unexpected stop reason (max_tokens, refusal, etc.).
            log.warning("unexpected stop_reason: %s", response.stop_reason)
            text_parts = [b.text for b in response.content if b.type == "text"]
            fallback = "\n".join(text_parts).strip() or "(no answer produced)"
            return fallback, trace, sorted(sources)

        # Run every tool_use block in this response, append all results in one user turn.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            entry = ToolTraceEntry(
                tool=block.name,
                args=block.input,
                ok=False,
                result_summary="",
            )
            try:
                result = dispatch(block.name, block.input)
                entry.ok = True
                entry.result_summary = _summarize_result(result)
                entry.result = result if _is_chartable(result) else None

                # Track sources for citation.
                if "chunks" in result:
                    for c in result["chunks"]:
                        sources.add(c.get("source", ""))

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })
            except ValidationError as e:
                entry.error = f"ValidationError: {e.errors()[0]['msg']}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": entry.error,
                })
            except Exception as e:
                entry.error = f"{type(e).__name__}: {e}"
                log.exception("tool %s failed", block.name)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": entry.error,
                })

            trace.append(entry)

        messages.append({"role": "user", "content": tool_results})

    # Hit the iteration cap without a final answer.
    log.warning("hit MAX_ITERATIONS without end_turn")
    return (
        "I ran out of steps before I could fully answer that. Try a more specific question.",
        trace,
        sorted(sources),
    )