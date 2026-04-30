# Secure AI Insights Assistant

An AI-powered internal analytics assistant for a fictional entertainment
company. Combines structured SQL data, unstructured PDF reports, and CSV
analytics behind a tool-based access layer.

Work in progress. Full setup instructions and architecture overview will be
added once the system is feature-complete.

## Progress

- [x] Phase 1 — Synthetic data - csv, PDF documents, Postgres schema and loader
- [ ] Phase 2 — Tool layer (SQL, document retrieval, CSV analytics)
- [ ] Phase 3 — AI orchestration (FastAPI + LLM tool calling)
- [ ] Phase 4 — Frontend (React + Vite)
- [ ] Phase 5 — Hardening, Docker, documentation

## Phase 1 summary

Three scripts under `data/` produce a reproducible data layer:

- `generate.py` writes six CSVs (movies, viewers, watch activity, reviews,
  marketing spend, regional performance) with deterministic seeding and
  deliberate signals planted to support the example questions.
- `generate_pdfs.py` writes five short business documents (quarterly report,
  campaign summary, content roadmap, policy guidelines, audience behavior)
  whose prose provides the qualitative context the structured data alone
  cannot.
- `load_db.py` loads the CSVs into a Postgres schema defined via SQLAlchemy,
  with indexes placed where the phase 2 tools will need them.