"""
FastAPI application entry point.

Exposes:
  GET  /health   — liveness probe
  POST /chat     — main entry point (added in step I)

Run with:
  uvicorn backend.app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm-up: pre-load the embedding model and DB pool so the first
    # /chat call doesn't pay the cold-start cost.
    log.info("warming up tools...")
    try:
        from backend.app.tools.search_documents import _get_collection
        _get_collection()  # forces embedding-model load
        log.info("vector store ready")
    except Exception as e:
        log.warning("vector store not ready: %s", e)

    yield
    log.info("shutdown")


app = FastAPI(
    title="Secure AI Insights Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Pydantic validation failures — bad client input."""
    log.warning("validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": "invalid request", "errors": exc.errors()},
    )

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """Catch-all so users never see raw stack traces."""
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error"},
    )

# CORS for the local Vite dev server (phase 4). Tightened in phase 5.
import os

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

from fastapi import HTTPException

from backend.app.history import (
    append_turn, get_conversation, list_conversations,
)
from backend.app.orchestrator import answer_question
from backend.app.schemas import ChatRequest, ChatResponse

from backend.app.admin_ingest import router as admin_router
app.include_router(admin_router)

import anthropic

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        answer, trace, sources = answer_question(req.question)
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=503, detail="LLM provider unreachable. Try again shortly.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limited by LLM provider. Please retry.")
    except anthropic.AuthenticationError:
        log.error("Anthropic auth failed — check ANTHROPIC_API_KEY")
        raise HTTPException(status_code=500, detail="LLM authentication failed.")
    except anthropic.APIStatusError as e:
        log.error("Anthropic API error: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e.status_code}")

    append_turn(
        conversation_id=req.conversation_id,
        question=req.question,
        answer=answer,
        trace=trace,
        sources=sources,
    )
    return ChatResponse(
        answer=answer, trace=trace, sources=sources,
        conversation_id=req.conversation_id,
    )

@app.get("/conversations")
def conversations():
    return list_conversations()


@app.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str):
    turns = get_conversation(conversation_id)
    if turns is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation_id": conversation_id, "turns": turns}

from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Serve the React static bundle if it's been built into the image.
# In dev mode it doesn't exist; the Vite dev server handles the UI on a separate port.
_static_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
    