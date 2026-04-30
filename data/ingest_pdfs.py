"""
Ingest the five PDFs in data/raw/ into a persistent Chroma collection.

Each PDF is read with pypdf, split into overlapping chunks, embedded with
a local sentence-transformers model, and stored in Chroma at
data/generated/chroma/.

Run once after generate_pdfs.py, and again any time the PDFs change:
  python data/ingest_pdfs.py
"""

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader

ROOT = Path(__file__).parent
RAW = ROOT / "raw"
PERSIST = ROOT / "generated" / "chroma"
PERSIST.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking parameters. ~600 chars with 80 char overlap is a good default
# for short business documents - chunks land roughly per-paragraph and
# overlap preserves cross-sentence context at chunk boundaries.
CHUNK_CHARS = 600
CHUNK_OVERLAP = 80


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text: str) -> list[str]:
    """Simple character-window chunker. Good enough for short, well-formatted docs."""
    text = text.strip()
    if len(text) <= CHUNK_CHARS:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_CHARS
        chunk = text[start:end]
        # Snap end to nearest paragraph break to avoid cutting mid-sentence,
        # but only if we haven't already consumed most of the chunk looking.
        if end < len(text):
            last_break = chunk.rfind("\n\n")
            if last_break > CHUNK_CHARS * 0.6:
                end = start + last_break
                chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - CHUNK_OVERLAP
    return [c for c in chunks if c]


def main():
    print(f"Persist directory: {PERSIST}")
    client = chromadb.PersistentClient(path=str(PERSIST))

    # Drop and recreate so re-ingestion is idempotent.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
    )
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        raise SystemExit("No PDFs found in data/raw/. Run generate_pdfs.py first.")

    total_chunks = 0
    for pdf_path in pdfs:
        print(f"  {pdf_path.name}")
        text = extract_text(pdf_path)
        chunks = chunk_text(text)
        if not chunks:
            print("    (no extractable text, skipping)")
            continue

        ids = [f"{pdf_path.stem}::{i:03d}" for i in range(len(chunks))]
        metadatas = [
            {"source": pdf_path.name, "chunk_index": i, "doc_title": pdf_path.stem}
            for i in range(len(chunks))
        ]
        collection.add(ids=ids, documents=chunks, metadatas=metadatas)
        total_chunks += len(chunks)
        print(f"    {len(chunks)} chunks indexed")

    print(f"\ndone. {total_chunks} total chunks across {len(pdfs)} documents.")


if __name__ == "__main__":
    main()