# Secure AI Insights Assistant

An AI-powered internal analytics assistant for a fictional entertainment
company. Combines structured SQL data, unstructured PDF reports, and CSV
analytics behind a tool-based access layer.

## How it's organised
 
Five things sit on top of each other, each with a single job:
 
**The data layer.** Six CSVs and five PDFs. Generated synthetically with deliberate signals planted (Stellar Run's August spike, Comedy's slump, Mumbai's growth) so the example questions have actual answers in the data. CSVs are loaded into Postgres; PDFs are chunked, embedded with a local model, and stored in Chroma.
 
**The tool layer.** Three Python tools — `query_metrics` (SQL), `search_documents` (PDF retrieval), `compute_aggregate` (CSV analytics). Each one has a Pydantic input schema with allow-listed enums for everything the LLM can choose. Filter values are bound as parameters, never concatenated. The database connection runs in `READ ONLY` transaction mode, enforced by Postgres itself. Every call writes to an audit log.
 
**The orchestration layer.** A FastAPI service. The `/chat` endpoint sends the user's question to Claude with the tool definitions attached, runs the tool-calling loop until Claude produces a final answer, and returns the answer plus the full trace. Anthropic prompt caching is enabled on the system prompt and tool definitions to keep token costs down across a session.
 
**The persistence layer.** Conversations are stored in Postgres so users can browse and reload past chats. There's an admin-gated `/admin/ingest` endpoint that triggers re-ingestion of any stage of the data pipeline.
 
**The frontend.** React + Vite + Tailwind + Recharts. Three columns: history sidebar on the left, chat in the middle, insights panel on the right showing charts (auto-picked based on result shape), the tool trace, and the source list. Filters above the chat let you scope follow-up questions without retyping.


## Repository structure
 
```
secure-ai-insights/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, /chat, /conversations, /admin
│   │   ├── orchestrator.py    LLM tool-calling loop
│   │   ├── registry.py        Tool registry; the LLM-to-Python bridge
│   │   ├── tools/             Three tool implementations
│   │   ├── schemas.py         Pydantic types shared across tools and API
│   │   ├── db.py              Read-only DB session
│   │   ├── audit.py           Append-only audit log
│   │   ├── history.py         Conversation persistence
│   │   └── admin_ingest.py    Admin-gated re-ingestion endpoint
│   ├── tests/                 Pytest validation + integration suite
│   └── requirements.txt
├── data/
│   ├── raw/                   Generated CSVs and PDFs (committed)
│   ├── generated/             Vector index, audit log (gitignored)
│   ├── generate.py            CSV generator
│   ├── generate_pdfs.py       PDF generator
│   ├── load_db.py             CSV → Postgres loader
│   └── ingest_pdfs.py         PDF → Chroma ingestion
├── frontend/                  React + Vite + Tailwind app
├── .env                       Secrets (gitignored)
├── .gitignore
└── README.md
```