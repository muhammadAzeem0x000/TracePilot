# TracePilot

TracePilot is a five-day applied AI engineering project exploring how an incident
investigation system can remain grounded in inspectable evidence. Day 1 is deliberately
only the software and data foundation: no LLMs, RAG, embeddings, agents, queues, or fake
AI features are present.

This is learning/project software, not a production incident-management service.

## Day-1 capabilities

- Create a validated incident in a Next.js UI.
- Persist it through FastAPI into Supabase PostgreSQL.
- List incidents and retrieve one incident's details.
- Return typed `201`, `404`, `422`, and `503` responses.
- Maintain relational foundations for future evidence and investigation work.
- Test API behavior without relying on remote Supabase state.

## Architecture

```text
Next.js browser UI  ->  FastAPI  ->  Supabase PostgREST  ->  PostgreSQL
    typed fetch         schemas       async repository       constraints
```

The frontend never performs incident business writes against Supabase. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/DECISIONS.md`](docs/DECISIONS.md) for the rationale and trade-offs.

## Prerequisites

- Node.js 20.9 or later (verified with Node.js 24)
- Python 3.12 or later
- A Supabase project with the migration applied

## Local setup

From the repository root:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\apps\api[dev]"
Copy-Item .env.example .env
```

Set the real Supabase values in `.env`. The file is ignored by Git. Apply
`supabase/migrations/202608040001_day1_foundation.sql` with the Supabase CLI or MCP.

## Run the backend

From `apps/api` with the virtual environment active:

```powershell
uvicorn app.main:app --reload --port 8000 --env-file ..\..\.env
```

Useful URLs:

- Health: `http://localhost:8000/health`
- OpenAPI: `http://localhost:8000/docs`

## Run the frontend

In another terminal from the repository root:

```powershell
npm run dev:web
```

Open `http://localhost:3000`.

## Test and verify

```powershell
cd apps\api
python -m pytest
ruff check .
mypy app tests
cd ..\..
npm run lint:web
npm run typecheck:web
npm run build:web
```

## Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | FastAPI | Supabase project URL |
| `SUPABASE_KEY` | FastAPI | Server-only Supabase service-role key; never expose as `NEXT_PUBLIC_*` |
| `CORS_ORIGINS` | FastAPI | Comma-separated allowed web origins; defaults to `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | Next.js | Browser-visible FastAPI base URL; defaults to `http://localhost:8000` |

The backend requires a service-role key because RLS blocks direct table access for
anonymous and ordinary authenticated roles. Keep this credential server-side and out of
source control. Add API authentication and tenant-scoped authorization before treating
the system as production-capable.

## Roadmap

- **Day 2:** Real evidence ingestion and normalized source provenance.
- **Day 3:** Evidence retrieval and grounding experiments with explicit citations.
- **Day 4:** Investigation orchestration and evaluated AI-assisted summaries.
- **Day 5:** Hardening, observability, security, evaluation, and end-to-end delivery.

These are planned directions, not current capabilities.
