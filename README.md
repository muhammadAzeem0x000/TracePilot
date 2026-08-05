# TracePilot

TracePilot is a five-day applied AI engineering project exploring a practical problem:
how can an incident investigator use an LLM without confusing model inference with
inspectable evidence? It is project/learning software, not a production incident platform.

Day 2 implements the first synchronous, evidence-grounded investigation. FastAPI—not the
model—executes a small allowlist of read-only GitHub REST operations, persists normalized
results, validates the model's structured conclusion, and rejects invented citations.

## Current capabilities

- Create, list, and retrieve validated incidents, including optional `owner/repository` context.
- Run one preliminary investigation synchronously for an incident with repository context.
- Let an OpenAI-compatible model request five controlled, read-only GitHub tools.
- Normalize and persist commit, pull-request, and changed-file evidence in Supabase PostgreSQL.
- Validate the final hypothesis with Pydantic, including confidence bounds and UUID syntax.
- Confirm every cited UUID belongs to the current incident and investigation before completion.
- Persist failed investigations when GitHub, model, tool, or output validation fails.
- Display factual evidence separately from the AI preliminary hypothesis in Next.js.

There is no RAG, embedding search, pgvector, LangChain, LangGraph, Redis, queue, background
worker, multi-agent system, or GitHub mutation capability.

## Architecture

```text
Next.js browser
  -> FastAPI route
  -> deterministic InvestigationService (maximum 6 tool calls)
     -> OpenAI-compatible LLM proposes an allowlisted tool call
     -> Python validates arguments and calls GitHub REST read-only endpoints
     -> normalized tool output is persisted as Evidence in Supabase PostgreSQL
     -> evidence IDs and bounded content return to the model
     -> Pydantic validates final JSON and the repository validates every citation
  -> completed/failed Investigation returns to the browser
```

The frontend never receives `GITHUB_TOKEN`, `LLM_API_KEY`, or `SUPABASE_KEY` and never writes
directly to Supabase. See [ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[DECISIONS.md](docs/DECISIONS.md).

## Prerequisites

- Node.js 20.9+ (verified with Node.js 24)
- Python 3.12+
- A Supabase project with both SQL migrations applied
- A server-side GitHub token that can read the repository under investigation
- An OpenAI-compatible chat model with function/tool calling and JSON output support

For public GitHub repositories, an unauthenticated request can work at lower rate limits, but
TracePilot intentionally requires `GITHUB_TOKEN` so configuration failures are explicit. For
private repositories, grant only the repository read permissions actually needed (Contents and
Pull requests); do not grant write administration, issue, or code permissions.

## Install

From the repository root in PowerShell:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\apps\api[dev]"
Copy-Item .env.example .env
```

Fill `.env` with server credentials. It is ignored by Git. Apply migrations in order:

1. `supabase/migrations/202608040001_day1_foundation.sql`
2. `supabase/migrations/202608050001_day2_investigation_foundation.sql`
3. `supabase/migrations/202608050002_day2_investigation_runtime_metadata.sql`

## Run

Backend, from `apps/api` with the virtual environment active:

```powershell
uvicorn app.main:app --reload --port 8000 --env-file ..\..\.env
```

Frontend, from the repository root in a second terminal:

```powershell
npm run dev:web
```

Open `http://localhost:3000`. FastAPI health and OpenAPI are available at
`http://localhost:8000/health` and `http://localhost:8000/docs`.

## Quality checks

```powershell
.\.venv\Scripts\python.exe -m pytest apps\api\tests
.\.venv\Scripts\python.exe -m ruff check apps\api
.\.venv\Scripts\python.exe -m mypy apps\api\app apps\api\tests
npm run lint:web
npm run typecheck:web
npm run build:web
```

Normal tests use typed in-memory doubles and never call Supabase, GitHub, or an LLM. The opt-in
live verification creates a real incident and investigation, so run it only against a project
where test rows are acceptable:

```powershell
$env:PYTHONPATH="apps/api"
.\.venv\Scripts\python.exe apps\api\scripts\live_day2_verification.py --repository openai/openai-python
```

## Environment variables

| Variable | Required | Scope | Purpose |
| --- | --- | --- | --- |
| `SUPABASE_URL` | yes | FastAPI | Supabase project URL |
| `SUPABASE_KEY` | yes | FastAPI | Server-only service-role/secret key |
| `GITHUB_TOKEN` | for investigations | FastAPI | Read-only GitHub REST authentication |
| `GITHUB_API_URL` | no | FastAPI | Defaults to `https://api.github.com` |
| `LLM_API_KEY` | for investigations | FastAPI | OpenAI-compatible provider key |
| `DEEPSEEK_API` | alias | FastAPI | Accepted alias for `LLM_API_KEY` |
| `LLM_MODEL` | no | FastAPI | Defaults to `deepseek-chat` |
| `LLM_BASE_URL` | no | FastAPI | Defaults to `https://api.deepseek.com` |
| `MAX_TOOL_CALLS` | no | FastAPI | Defaults to 6; hard bounded to 1–20 |
| `FINAL_OUTPUT_RETRIES` | no | FastAPI | Defaults to one correction attempt |
| `CORS_ORIGINS` | no | FastAPI | Defaults to `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | no | browser | FastAPI URL, default `http://localhost:8000` |

Never prefix server secrets with `NEXT_PUBLIC_`. API authentication and tenant authorization
are still absent, so do not expose this service publicly.

## Roadmap

- **Day 3:** Evidence retrieval/grounding experiments and explicit evaluation cases.
- **Day 4:** More durable execution and operational visibility, without weakening evidence controls.
- **Day 5:** Security hardening, evaluation, deployment readiness, and end-to-end delivery.

These are planned directions, not implemented capabilities.
