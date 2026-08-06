# TracePilot

TracePilot is a five-day applied AI engineering project exploring how an incident investigator
can use model-generated hypotheses without confusing them with inspectable evidence. It is
learning/project software, not a production incident-response platform.

Day 4 moves investigations onto a durable PostgreSQL queue and adds a fixed end-to-end diagnosis
benchmark. GitHub results and retrieved knowledge chunks remain persisted as Evidence before the
LLM can cite them.

## Current capabilities

- Create, list, and retrieve validated incidents with optional `owner/repository` context.
- Enqueue a preliminary investigation with HTTP `202`; a leased worker runs allowlisted GitHub and
  knowledge tools while the browser polls visible progress.
- Recover expired leases, retry transient provider/storage failures with bounded exponential
  backoff, and stop permanent failures without retrying.
- Prevent duplicate active investigations atomically while allowing a new run after completion.
- Ingest Markdown/text knowledge idempotently with deterministic chunking and Gemini embeddings.
- Store 768-dimensional vectors in Supabase PostgreSQL with pgvector cosine search.
- Search by semantic similarity, PostgreSQL full-text ranking, RRF hybrid ranking, or optional
  structured LLM reranking.
- Bound retrieved context by chunk count and approximate-token budget.
- Persist each retrieved knowledge chunk as `knowledge_chunk` Evidence with ranking diagnostics.
- Validate model output and prove every cited evidence UUID belongs to the current investigation.
- Evaluate semantic, hybrid, and reranked retrieval against a fixed 12-query benchmark.
- Evaluate full diagnosis quality against ten fixed incidents and controlled Evidence fixtures.
- Store an accept/reject human review separately without rewriting the AI conclusion.
- Display collected GitHub/knowledge Evidence separately from the AI preliminary hypothesis.

There is no LangChain, LangGraph, Redis, external queue, multi-agent architecture, file-upload
pipeline, PDF parsing, or GitHub mutation capability.

## Architecture

```text
knowledge/*.md -> deterministic chunker -> Gemini embedding provider
              -> FastAPI repository -> Supabase knowledge_sources/knowledge_chunks

Incident -> atomic PostgreSQL enqueue -> HTTP 202
         -> worker claims with FOR UPDATE SKIP LOCKED + expiring lease
         -> bounded InvestigationService
         -> LLM proposes GitHub read tool or search_knowledge(query, top_k)
         -> Python validates tool and fixes repository scope from the Incident
         -> semantic + lexical retrieval -> RRF -> optional validated rerank
         -> bounded chunks persisted as Evidence -> returned to LLM
         -> Pydantic conclusion + database-backed citation ownership check
         -> terminal job/investigation state -> browser polling + separate human review
```

The browser never receives `SUPABASE_KEY`, `GITHUB_TOKEN`, `LLM_API_KEY`, or an embedding key,
and it never writes business data directly to Supabase. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/DECISIONS.md`](docs/DECISIONS.md).

## Prerequisites

- Node.js 20.9+ (verified with Node.js 24)
- Python 3.12+
- Supabase PostgreSQL with the seven migrations below
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
5. `supabase/migrations/202608060002_day3_fix_knowledge_replacement.sql`
6. `supabase/migrations/20260806084343_day4_async_investigations.sql`
7. `supabase/migrations/20260806093000_day4_server_timestamps.sql`

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

## Measured Day 3 results

The fixed 12-query benchmark was executed on 2026-08-05 against the real TracePilot Supabase project,
Gemini `gemini-embedding-001` at 768 dimensions, and DeepSeek `deepseek-chat` reranking:

| Retrieval mode | Hit@1 | Hit@3 | Hit@5 | MRR | Average latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Semantic | 0.750 | 1.000 | 1.000 | 0.875 | 2,110.8 ms |
| Hybrid (RRF) | 0.750 | 1.000 | 1.000 | 0.875 | 1,934.2 ms |
| Hybrid + rerank | 0.917 | 1.000 | 1.000 | 0.958 | 4,874.1 ms |

Hybrid did not improve a fixed-benchmark relevance metric over semantic-only on this small corpus.
Lexical search was nevertheless verified independently: `payment_status UndefinedColumn` returned
the missing-column incident and migration runbook. Reranking improved two Hit@1 failures (provider
timeouts and asynchronous email/analytics) and made no benchmark reciprocal rank worse, but added
about 2.9 seconds average latency. The worker-redelivery query remained a Hit@1 failure in every mode.
See the committed [summary](docs/evaluation/retrieval_evaluation.md) and
[per-query JSON](docs/evaluation/retrieval_evaluation.json).

Live ingestion created 10 sources/10 chunks; a second pass skipped all 10. Supabase reported every
stored vector as exactly 768 dimensions. The live RAG verifier completed investigation
`3aa30109-98b0-46b9-9b1e-21eddcc5d59f`, persisted 13 Evidence rows (10 knowledge), cited three
knowledge Evidence UUIDs, and passed the incident/investigation ownership check.

## Measured Day 4 results

The unchanged ten-scenario incident benchmark was executed on 2026-08-06 with real DeepSeek
`deepseek-chat` calls and fixed GitHub/knowledge tool fixtures. The production six-call limit stayed
in force; `investigation_v2` tells the model to stop once it has a plausible culprit and corroboration.

| Metric | Result |
| --- | ---: |
| Completion rate | 1.000 (10/10) |
| Culprit accuracy | 1.000 |
| Citation precision / recall | 1.000 / 1.000 |
| Invalid citation rate | 0.000 |
| Average tool calls | 4.20 |
| Average investigation latency | 7,896.5 ms |
| Average model confidence | 0.615 |
| High-confidence incorrect diagnoses | 0 |

All ten final cases completed correctly, so confidence-on-incorrect is `n/a`; this does not establish
general model accuracy or calibrate confidence as a probability. The first live run completed only
2/10 because the model repeatedly used the full tool budget. Tightening only the production prompt's
budget guidance—without changing fixtures, expected answers, or the six-call limit—produced the
committed final run. See the [summary](docs/evaluation/incident_evaluation.md) and
[per-scenario JSON](docs/evaluation/incident_evaluation.json).

Live Supabase verification proved one claim under two concurrent workers, idempotent duplicate
enqueue, stale-lease reclamation on attempt two, one-second retry scheduling, exhaustion at attempt
two, and permanent failure on attempt one. The real HTTP flow returned `202` in 1,322.58 ms and then
completed in 46,031 ms after four tools and 17 persisted Evidence rows. Browser polling showed the
active stage and completed with no console warnings/errors.

## Run

Backend, from `apps/api` with the virtual environment active:

```powershell
$env:INVESTIGATION_WORKER_ENABLED="true"
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
.\.venv\Scripts\python.exe -m ruff check apps\api\app apps\api\tests apps\api\scripts
.\.venv\Scripts\python.exe -m mypy --strict apps\api\app apps\api\tests apps\api\scripts
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

.\.venv\Scripts\python.exe apps\api\scripts\live_day4_verification.py `
  --mode queue --repository owner/repository

.\.venv\Scripts\python.exe apps\api\scripts\evaluate_incidents.py `
  --benchmark evaluation\incident_benchmark.json --output-dir docs\evaluation
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
| `INVESTIGATION_WORKER_ENABLED` | no | FastAPI | Default `false`; set `true` for a processing worker |
| `INVESTIGATION_WORKER_POLL_SECONDS` | no | worker | Default `1.0` |
| `INVESTIGATION_JOB_LEASE_SECONDS` | no | worker | Default `240` |
| `INVESTIGATION_JOB_MAX_ATTEMPTS` | no | worker | Default `3` |
| `INVESTIGATION_RETRY_BASE_SECONDS` | no | worker | Default `5`; exponential backoff base |
| `CORS_ORIGINS` | no | FastAPI | Default `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | no | browser | Default `http://localhost:8000` |

Never prefix server secrets with `NEXT_PUBLIC_`. Authentication and tenant authorization remain
absent, so do not expose this service publicly.

## Roadmap

- **Days 1-3:** implemented foundation, evidence-grounded GitHub investigation, and evaluated RAG.
- **Day 4:** implemented durable execution, progress/review UI, and fixed diagnosis evaluation.
- **Day 5:** security hardening, deployment readiness, and end-to-end delivery.

Future directions are not current capabilities.
