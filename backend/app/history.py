"""
Conversation history persistence.

Every successful /chat call appends a row to the conversations table.
The right-rail sidebar in the UI lists past conversations and lets the
user click back into one.

The schema stores trace and sources as JSON text rather than as proper
relational rows because they are read-mostly, vary per row in shape,
and are only ever round-tripped through the API. A future change to
trace shape doesn't require a schema migration.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from backend.app.db import get_engine
from backend.app.schemas import ToolTraceEntry

log = logging.getLogger("history")


def append_turn(
    conversation_id: str,
    question: str,
    answer: str,
    trace: list[ToolTraceEntry],
    sources: list[str],
) -> None:
    """Append one Q&A turn to the given conversation."""
    trace_json = json.dumps([t.model_dump(mode="json") for t in trace])
    sources_json = json.dumps(sources)
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversations "
                "(conversation_id, created_at, question, answer, trace_json, sources_json) "
                "VALUES (:cid, :ts, :q, :a, :t, :s)"
            ),
            {
                "cid": conversation_id,
                "ts": datetime.now(timezone.utc),
                "q": question,
                "a": answer,
                "t": trace_json,
                "s": sources_json,
            },
        )


def list_conversations(limit: int = 50) -> list[dict]:
    """List conversations newest first, one row per conversation_id with
    metadata about its first question and turn count."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    conversation_id,
                    MIN(created_at) AS started_at,
                    MAX(created_at) AS last_at,
                    COUNT(*) AS turn_count,
                    (ARRAY_AGG(question ORDER BY created_at ASC))[1] AS first_question
                FROM conversations
                GROUP BY conversation_id
                ORDER BY last_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).all()
    return [
        {
            "conversation_id": r.conversation_id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "last_at": r.last_at.isoformat() if r.last_at else None,
            "turn_count": r.turn_count,
            "first_question": r.first_question,
        }
        for r in rows
    ]


def get_conversation(conversation_id: str) -> Optional[list[dict]]:
    """Return all turns of one conversation in chronological order."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT created_at, question, answer, trace_json, sources_json
                FROM conversations
                WHERE conversation_id = :cid
                ORDER BY created_at ASC
                """
            ),
            {"cid": conversation_id},
        ).all()
    if not rows:
        return None
    return [
        {
            "created_at": r.created_at.isoformat(),
            "question": r.question,
            "answer": r.answer,
            "trace": json.loads(r.trace_json),
            "sources": json.loads(r.sources_json),
        }
        for r in rows
    ]