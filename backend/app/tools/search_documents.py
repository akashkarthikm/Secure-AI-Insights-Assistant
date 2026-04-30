"""
search_documents — the document retrieval tool.

The LLM passes a natural-language query and an optional source filter
(useful for "look only in the policy guidelines" type questions). The
tool runs a vector search against the pre-built Chroma collection and
returns the top-k chunks with source metadata.

The collection is loaded once per process and reused. If ingestion has
not run, the tool raises a clear error rather than silently returning
empty results.
"""

from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from backend.app.audit import audit
from backend.app.schemas import (
    DocumentChunk, SearchDocumentsInput, SearchDocumentsResult,
)

PERSIST = Path(__file__).resolve().parents[3] / "data" / "generated" / "chroma"
COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_collection():
    """Lazy-load the collection on first use, then cache.

    Raises a useful error if the persist directory is missing — that
    means ingest_pdfs.py has not been run.
    """
    if not PERSIST.exists() or not any(PERSIST.iterdir()):
        raise RuntimeError(
            f"Vector index not found at {PERSIST}. "
            f"Run `python data/ingest_pdfs.py` first."
        )

    client = chromadb.PersistentClient(path=str(PERSIST))
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
    )
    return client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)


def search_documents(inp: SearchDocumentsInput) -> SearchDocumentsResult:
    with audit("search_documents", inp.model_dump(mode="json")) as record:
        collection = _get_collection()

        where = {"source": inp.source_filter} if inp.source_filter else None

        result = collection.query(
            query_texts=[inp.query],
            n_results=inp.k,
            where=where,
        )

        # Chroma returns parallel lists. Index 0 = first (and only) query.
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        chunks = [
            DocumentChunk(
                text=doc,
                source=meta.get("source", "unknown"),
                doc_title=meta.get("doc_title", "unknown"),
                chunk_index=int(meta.get("chunk_index", 0)),
                distance=float(dist),
            )
            for doc, meta, dist in zip(documents, metadatas, distances)
        ]

        record["result_chunks"] = len(chunks)
        record["sources_returned"] = sorted({c.source for c in chunks})

        return SearchDocumentsResult(
            query=inp.query,
            chunks=chunks,
            chunk_count=len(chunks),
        )