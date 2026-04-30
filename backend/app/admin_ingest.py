"""
Admin-gated data ingestion endpoint.

POST /admin/ingest with header X-Admin-Token rebuilds one or more
stages of the data pipeline:

  - "csv":    regenerate CSVs in data/raw/
  - "pdf":    regenerate PDFs in data/raw/
  - "db":     drop & reload the Postgres schema from CSVs
  - "vector": rebuild the Chroma index from PDFs
  - "all":    all four, in dependency order

The token is read from ADMIN_TOKEN in .env. A request without it (or
with the wrong one) returns 401. This is intentionally simple — full
RBAC is out of scope for a single-user assignment — but the gate is
real and is enforced before any destructive work runs.
"""

import logging
import os
from enum import Enum

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict

log = logging.getLogger("admin.ingest")

router = APIRouter(prefix="/admin", tags=["admin"])


class Stage(str, Enum):
    csv = "csv"
    pdf = "pdf"
    db = "db"
    vector = "vector"
    all = "all"


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Stage = Stage.all


class StageResult(BaseModel):
    stage: str
    ok: bool
    detail: str


class IngestResponse(BaseModel):
    results: list[StageResult]


def _check_token(x_admin_token: str | None) -> None:
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected:
        # Missing config is a 500 (not the caller's fault) so it's not
        # silently accepted in production-shaped deploys.
        raise HTTPException(
            status_code=500,
            detail="ADMIN_TOKEN not configured on the server",
        )
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")


def _run_csv() -> StageResult:
    from data import generate as gen
    gen.main()
    return StageResult(stage="csv", ok=True, detail="CSVs regenerated in data/raw/")


def _run_pdf() -> StageResult:
    from data import generate_pdfs as gp
    gp.main()
    return StageResult(stage="pdf", ok=True, detail="PDFs regenerated in data/raw/")


def _run_db() -> StageResult:
    from data import load_db as ld
    ld.main()
    return StageResult(stage="db", ok=True, detail="schema dropped and reloaded")


def _run_vector() -> StageResult:
    from data import ingest_pdfs as ip
    ip.main()
    # Bust the lru_cache so the next request rebuilds the in-memory collection.
    from backend.app.tools.search_documents import _get_collection
    _get_collection.cache_clear()
    return StageResult(stage="vector", ok=True, detail="vector index rebuilt")


_RUNNERS = {
    Stage.csv: _run_csv,
    Stage.pdf: _run_pdf,
    Stage.db: _run_db,
    Stage.vector: _run_vector,
}

# When stage=all, run in this order so dependencies are satisfied.
_ALL_ORDER = [Stage.csv, Stage.pdf, Stage.db, Stage.vector]


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    req: IngestRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> IngestResponse:
    _check_token(x_admin_token)

    stages = _ALL_ORDER if req.stage == Stage.all else [req.stage]
    results: list[StageResult] = []

    for stage in stages:
        try:
            log.info("running ingestion stage: %s", stage.value)
            results.append(_RUNNERS[stage]())
        except Exception as e:
            log.exception("stage %s failed", stage.value)
            results.append(StageResult(
                stage=stage.value, ok=False, detail=f"{type(e).__name__}: {e}",
            ))
            # Stop the chain; later stages depend on earlier ones.
            break

    return IngestResponse(results=results)