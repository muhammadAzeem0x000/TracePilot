# TracePilot

TracePilot is a five-day applied AI engineering project exploring how an incident investigator
can use model-generated hypotheses without confusing them with inspectable evidence. It is
learning/project software, not a production incident-response platform.

Day 3 adds repository-scoped retrieval over original runbooks, architecture notes, and past
incident reports. GitHub results and retrieved knowledge chunks are persisted as Evidence before
the LLM can cite them.

## Current capabilities

- Create, list, and retrieve validated incidents with optional `owner/repository` context.
- Run a synchronous preliminary investigation using allowlisted GitHub and knowledge tools.
- Ingest Markdown/text knowledge idempotently with deterministic chunking and Gemini embeddings.
- Store 768-dimensional vectors in Supabase PostgreSQL with pgvector cosine search.
- Search by semantic similarity, PostgreSQL full-text ranking, RRF hybrid ranking, or optional
  structured LLM reranking.
- Bound retrieved context by chunk count and approximate-token budget.
- Persist each retrieved knowledge chunk as `knowledge_chunk` Evidence with ranking diagnostics.
- Validate model output and prove every cited evidence UUID belongs to the current investigation.
- Evaluate semantic, hybrid, and reranked retrieval against a fixed 12-query benchmark.
- Display collected GitHub/knowledge Evidence separately from the AI preliminary hypothesis.

There is no LangChain, LangGraph, Redis, queue, background worker, multi-agent architecture,
file-upload pipeline, PDF parsing, or GitHub mutation capability.

## Architecture

```text
knowledge/*.md -> deterministic chunker -> Gemini embedding provider
              -> FastAPI repository -> Supabase knowledge_sources/knowledge_chunks

Incident -> bounded InvestigationService
         -> LLM proposes GitHub read tool or search_knowledge(query, top_k)
         -> Python validates tool and fixes repository scope from the Incident
         -> semantic + lexical retrieval -> RRF -> optional validated rerank
         -> bounded chunks persisted as Evidence -> returned to LLM
         -> Pydantic conclusion + database-backed citation ownership check
```

The browser never receives `SUPABASE_KEY`, `GITHUB_TOKEN`, `LLM_API_KEY`, or an embedding key,
and it never writes business data directly to Supabase. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/DECISIONS.md`](docs/DECISIONS.md).

## Prerequisites

- Node.js 20.9+ (verified with Node.js 24)
- Python 3.12+
- Supabase PostgreSQL with the four migrations below
- A server-only Supabase service-role/secret key
- A least-privilege GitHub token for investigation repositories
- An OpenAI-compatible chat model with tool calling and JSON output support
- A Gemini API key for `gemini-embedding-001`

For private GitHub repositories, grant only read access to Contents and Pull requests. Do not grant
write, administration, merge, issue mutation, or code-push permissions.

## Install

From the repository root in PowerShell:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\apps\api[dev]"
Copy-Item .env.example .env
```

Fill `.env`; it is ignored by Git. Apply migrations in order:

1. `supabase/migrations/202608040001_day1_foundation.sql`
2. `supabase/migrations/202608050001_day2_investigation_foundation.sql`
3. `supabase/migrations/202608050002_day2_investigation_runtime_metadata.sql`
4. `supabase/migrations/202608060001_day3_knowledge_retrieval.sql`

## Ingest and inspect knowledge

The repository contains ten original fictional documents and a fixed benchmark. Ingestion is
explicit so deploy/startup never silently calls a paid provider:

```powershell
$env:PYTHONPATH="apps/api"
.\.venv\Scripts\python.exe apps\api\scripts\ingest_knowledge.py `
  --repository owner/repository

.\.venv\Scripts\python.exe apps\api\scripts\search_knowledge.py `
  "database column missing after deploy" `
  --repository owner/repository --mode hybrid --top-k 5

.\.venv\Scripts\python.exe apps\api\scripts\evaluate_retrieval.py `
  --repository owner/repository
```

The evaluation writes `docs/evaluation/retrieval_evaluation.json` and `.md`. Running ingestion
again with unchanged content reports `skipped` and does not regenerate embeddings. Changed content
is embedded first, then the source and all its chunks are replaced atomically by a database RPC.

## Run

Backend, from `apps/api` with the virtual environment active:

```powershell
uvicorn app.main:app --reload --port 8000 --env-file ..\..\.env
```

Frontend, from the repository root in another terminal:

```powershell
npm run dev:web
```

Open `http://localhost:3000`. API health, OpenAPI, and the developer retrieval endpoint are at:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`
- `GET http://localhost:8000/api/v1/knowledge/search?q=...&repository=owner/repo&mode=hybrid`

## Quality checks

```powershell
.\.venv\Scripts\python.exe -m pytest apps\api\tests
.\.venv\Scripts\python.exe -m ruff check apps\api\app apps\api\tests
.\.venv\Scripts\python.exe -m mypy apps\api\app apps\api\tests
npm run lint:web
npm run typecheck:web
npm run build:web
```

Ordinary tests use typed in-memory doubles and make no Supabase, GitHub, embedding, or LLM calls.
After ingesting the corpus, the opt-in live workflow asserts that the model actually executes
`search_knowledge`, persists knowledge Evidence, cites at least one knowledge UUID, and passes the
database ownership check:

```powershell
$env:PYTHONPATH="apps/api"
.\.venv\Scripts\python.exe apps\api\scripts\live_day3_verification.py `
  --repository owner/repository
```

## Environment variables

| Variable | Required | Scope | Purpose |
| --- | --- | --- | --- |
| `SUPABASE_URL` | yes | FastAPI/scripts | Supabase project URL |
| `SUPABASE_KEY` | yes | FastAPI/scripts | Server-only service-role/secret key |
| `GITHUB_TOKEN` | investigations | FastAPI | Read-only GitHub REST authentication |
| `GITHUB_API_URL` | no | FastAPI | Default `https://api.github.com` |
| `LLM_API_KEY` | investigations/rerank | FastAPI | OpenAI-compatible provider key |
| `DEEPSEEK_API` | alias | FastAPI | Accepted alias for `LLM_API_KEY` |
| `LLM_MODEL` | no | FastAPI | Default `deepseek-chat` |
| `LLM_BASE_URL` | no | FastAPI | Default `https://api.deepseek.com` |
| `EMBEDDING_API_KEY` | ingestion/search | server/scripts | Gemini API key |
| `GEMINI_API_KEY` | alias | server/scripts | Accepted alias for `EMBEDDING_API_KEY` |
| `EMBEDDING_MODEL` | no | server/scripts | Default `gemini-embedding-001` |
| `EMBEDDING_DIMENSIONS` | no | server/scripts | Must equal database dimension `768` |
| `EMBEDDING_BASE_URL` | no | server/scripts | Gemini API base URL |
| `KNOWLEDGE_CHUNK_MAX_TOKENS` | no | ingestion | Default `350` approximate tokens |
| `KNOWLEDGE_CHUNK_OVERLAP_TOKENS` | no | ingestion | Default `50` approximate tokens |
| `KNOWLEDGE_CONTEXT_BUDGET_TOKENS` | no | retrieval | Default `1800` approximate tokens |
| `KNOWLEDGE_CANDIDATE_LIMIT` | no | retrieval | Default `12` per retrieval channel |
| `KNOWLEDGE_RERANK_ENABLED` | no | retrieval | Default `true`; safe RRF fallback |
| `MAX_TOOL_CALLS` | no | investigation | Default `6`, bounded `1..20` |
| `FINAL_OUTPUT_RETRIES` | no | investigation | Default one correction attempt |
| `CORS_ORIGINS` | no | FastAPI | Default `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | no | browser | Default `http://localhost:8000` |

Never prefix server secrets with `NEXT_PUBLIC_`. Authentication and tenant authorization remain
absent, so do not expose this service publicly.

## Roadmap

- **Days 1-3:** implemented foundation, evidence-grounded GitHub investigation, and evaluated RAG.
- **Day 4:** durable execution and operational visibility without weakening evidence controls.
- **Day 5:** security hardening, deployment readiness, and end-to-end delivery.

Future directions are not current capabilities.
