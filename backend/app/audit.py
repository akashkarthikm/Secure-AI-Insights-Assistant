"""
Audit log for tool calls.

Every tool invocation appends one JSON line to data/generated/audit.log
recording: timestamp, tool name, arguments (validated, so no raw user
input), result row count or error, and elapsed milliseconds.

The log file is append-only from this code path. Operators rotate or
archive it externally.

Why JSONL: trivially greppable, every line is a self-contained event,
no library needed to read it back. Phase 5 can ship logs to a real sink
without changing the call sites.
"""

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "generated" / "audit.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _write(record: dict) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


@contextmanager
def audit(tool_name: str, args: dict[str, Any]):
    """Context manager wrapping a tool call.

    Usage:
        with audit("query_metrics", {"metric": "completion_rate"}) as record:
            result = ...
            record["result_rows"] = len(result)
    """
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "args": args,
        "ok": True,
    }
    start = time.perf_counter()
    try:
        yield record
    except Exception as e:
        record["ok"] = False
        record["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        record["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 1)
        _write(record)


def tail(n: int = 20) -> list[dict]:
    """Read the last n entries. For debugging and the trace UI in phase 4."""
    if not LOG_PATH.exists():
        return []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines[-n:]]