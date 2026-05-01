## Assumptions

- No external dataset was provided, so I generated synthetic CSVs and PDFs with planted patterns (Stellar Run's August trend, Mumbai's growth, Comedy's slump) using Faker library - every example question has a real answer to find.
- Single-reviewer scale: anonymous sessions, dev-default Postgres credentials, audit log on local disk. Architecture extends cleanly to multi-user but isn't deployed for large scale user in any domain.
- Person reviewing this is using the provided Anthropic key on the created .env file

## Tradeoffs

- **Security over flexibility.** The Claude LLM can only call three typed tools with allow-listed inputs - it can't write arbitrary SQL or pick its own columns. Less flexible than free-form access, far easier to defend.
- **Defense in depth over single-layer trust.** Pydantic validation at the gate, allow-lists in the tool, read-only at the database. Three layers means a bug in any one of them doesn't break the security story.
- **Persistence over caching.** Every chat turn writes to Postgres for audit and history. Caching could save tokens but introduces stale-answer risk on changing data, which is worse than slightly higher cost.
- **Synchronous orchestration over streaming.** Returns a complete answer rather than token-streaming. Simpler state, easier to audit, slightly worse felt latency. But this approach is better for analytics-style answers or to prepare the charts.
- **Three specialised tools over one general tool.** SQL, vector search, and pandas live in separate tools because each access pattern wants different validation and a different allow-list. More files, narrower attack surface.
- **Functional capability over auth at this stage.** Skipped login since the requirement weights architecture and reasoning heavily. The schema and dispatcher are designed to accept a `user_id` cleanly when authentication is added.
