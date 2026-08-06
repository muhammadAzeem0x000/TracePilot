# TracePilot Architecture - Final five-day build

TracePilot remains one Next.js app, one FastAPI service, and one Supabase PostgreSQL database.
Day 4 places the existing deterministic investigation loop behind a durable PostgreSQL queue and
adds diagnosis evaluation; it does not add another service or orchestration framework.

## Responsibilities

### Next.js (`apps/web`)

`src/lib/api.ts` is the browser contract boundary. The incident detail view enqueues investigations
and polls every 1.5 seconds while status is `pending` or `in_progress`. It shows a disabled active
button and stage-specific progress, then refreshes investigation and Evidence state at termination.
It renders two distinct regions: `COLLECTED EVIDENCE` and `AI PRELIMINARY HYPOTHESIS`. Knowledge
cards label their original type (`RUNBOOK`, `ARCHITECTURE`, or `PAST INCIDENT`) and expose ranking
metadata in a details element. `HUMAN REVIEW` is a third, separate accept/reject record. The browser
has no database or provider secret.

### FastAPI (`apps/api`)

- `app/knowledge/chunking.py` produces deterministic bounded chunks without model calls.
- `app/ai/embeddings.py` owns the small Gemini embedding boundary and output validation.
- `app/services/knowledge_ingestion.py` hashes, skips, embeds, and replaces sources.
- `app/repositories/knowledge.py` owns PostgREST/RPC persistence and retrieval calls.
- `app/retrieval/service.py` runs semantic/lexical retrieval, RRF fusion, and safe rerank fallback.
- `app/retrieval/reranking.py` validates that the model returns every known candidate ID once.
- `app/retrieval/context.py` deduplicates and enforces the final approximate-token budget.
- `app/tools/knowledge.py` fixes scope from the Incident and persists chunks as Evidence.
- `app/services/investigations.py` retains the six-call deterministic tool loop and citation checks.
- `app/repositories/jobs.py` owns atomic enqueue/claim RPCs and durable job transitions.
- `app/services/worker.py` owns lease processing, retry classification, exponential backoff, and
  permanent failure behavior.
- `app/evaluation/` runs real orchestration and validation against fixed Evidence fixtures.
- `app/api/routes.py` exposes the product APIs and one read-only developer search endpoint.

### Supabase PostgreSQL

`knowledge_sources` stores repository scope, provenance, stable source reference, and content hash.
`knowledge_chunks` stores ordered text chunks, token counts, metadata, generated `tsvector`, and
`vector(768)` embeddings. PostgreSQL performs both retrieval channels:

- cosine-distance semantic search over pgvector, with an HNSW cosine index;
- `websearch_to_tsquery` lexical search over a generated weighted `tsvector`, with a GIN index.

Both server-only SQL functions require `filter_repository`. RLS is enabled and public roles have no
table or function access. The HNSW index demonstrates the scalable access path; this ten-document
corpus is too small to claim a speed benefit over an exact scan.

`investigation_jobs` stores queue state, attempts, eligibility time, locks, leases, terminal errors,
and completion time. `enqueue_investigation_job` locks the Incident and atomically returns an existing
active investigation or inserts one Investigation plus one job. `claim_investigation_job` uses
`FOR UPDATE SKIP LOCKED`, increments attempts, assigns an expiring lease, and also reclaims stale
running jobs. `investigation_reviews` stores one human decision per completed investigation. All
three queue RPCs are security-invoker functions executable only by `service_role`.

## Durable execution flow

```text
POST incident/{id}/investigations
  -> validate Incident repository scope
  -> atomic enqueue (duplicate active run returns same ID)
  -> HTTP 202 with queued Investigation

worker
  -> claim one eligible job with row lock + SKIP LOCKED
  -> run unchanged bounded evidence/model loop
  -> completed: terminal Investigation + job
  -> transient failure: retry_scheduled at database_now + base * 2^(attempt-1)
  -> permanent/exhausted failure: terminal Investigation + job
  -> process loss: running lease expires and becomes claimable
```

Terminal and retry timestamps use PostgreSQL `clock_timestamp()`. Live verification found the
worker host clock about three seconds behind the database; client-generated completion time could
otherwise precede database-generated start time and violate the relational constraint.

## Ingestion flow

1. `scripts/ingest_knowledge.py` maps files under `runbooks/`, `architecture/`, and
   `past_incidents/` to typed documents.
2. Content is newline-normalized and SHA-256 hashed.
3. An equal `(repository_full_name, source_reference, content_hash)` returns `skipped` before an
   embedding request.
4. Changed text is split into deterministic paragraph/sentence-aware chunks: 350 approximate
   tokens maximum and 50-token trailing overlap by default.
5. Gemini creates normalized 768-dimensional document embeddings; count and dimensions are checked.
6. `replace_knowledge_source` updates the source and replaces all chunks in one transaction.

Embedding happens before replacement, so provider failure leaves the last valid source intact.
The live corpus produced one chunk per concise document (10 total, 128-222 approximate tokens each).
The chunker is not hardcoded to that outcome; longer sources split at the configured 350-token bound.

## Retrieval and RAG flow

```text
query
  +-> Gemini RETRIEVAL_QUERY embedding -> repository-filtered cosine candidates
  +-> PostgreSQL full-text query       -> repository-filtered lexical candidates
       -> reciprocal rank fusion (RRF, k=60)
       -> optional rerank_v1 over bounded candidate IDs/text
       -> validated IDs or deterministic RRF fallback
       -> dedupe + top-k + 1,800 approximate-token context budget
       -> each selected chunk persisted as Evidence
       -> evidence IDs and bounded content returned to the investigation LLM
```

RRF combines ordinal ranks because cosine similarity and text-search rank have incompatible scales.
Raw component scores/ranks and hybrid/rerank ranks remain in typed results and Evidence metadata.

The LLM can provide only `query` and bounded `top_k` to `search_knowledge`; the Pydantic argument
model forbids a repository field. Python uses `Incident.repository_full_name`. Retrieved document
text is untrusted data and cannot add tools or alter permissions. The chunk exists as Evidence before
the model receives its citation UUID, so the Day 2 ownership check remains unchanged.

## Failure behavior

Embedding count/dimension errors stop ingestion before replacement. Provider failures are explicit.
Reranker provider/validation failures log a fallback and preserve hybrid results. Tool argument,
retrieval, persistence, or final-output failures mark an investigation failed rather than storing a
false completed result. Secrets and raw provider payloads are not logged.

## Live verification snapshot (2026-08-05)

- Supabase pgvector `0.8.2`, `vector(768)`, HNSW cosine index, GIN full-text index, and all three RPCs
  were queried directly.
- Ten fictional sources and ten chunks were stored under `muhammadAzeem0x000/TracePilot`; every
  vector reported 768 dimensions. The unchanged second ingestion skipped 10/10 sources.
- A 300-token override selected two chunks totaling 297 tokens, proving context budget enforcement.
- Investigation `3aa30109-98b0-46b9-9b1e-21eddcc5d59f` persisted Evidence before completion:
  13 total rows, 10 knowledge rows, and three cited knowledge rows with valid ownership.
- The browser rendered RUNBOOK, ARCHITECTURE, and PAST INCIDENT labels, retrieval diagnostics, and
  separate factual/model panels with no console warning or error.

The original replacement RPC used an unqualified `source_id` inside a `RETURNS TABLE (source_id ...)`
PL/pgSQL function. Live ingestion exposed the resulting ambiguous-column error. The forward repair
migration aliases `knowledge_chunks` and qualifies `knowledge_chunk.source_id`; migration history was
not rewritten.

## Day 4 live verification snapshot (2026-08-06)

- Two concurrent claim requests returned exactly one job; an expired lease was reclaimed at attempt
  two. Transient failure scheduled a database-clock retry and exhausted at attempt two; permanent
  failure stopped at attempt one.
- A real HTTP request returned `202` in 1,322.58 ms; the worker completed in 46,031 ms with four
  tools, 17 Evidence rows, and valid citations. Queued, collecting, retrieving, reasoning,
  finalizing, and completed stages were observed.
- Live Day-2 GitHub verification completed with 13 Evidence rows and four valid citations. Live
  Day-3 verification used 768-dimensional Gemini embeddings, stored five knowledge Evidence rows,
  and cited three.
- Browser polling displayed an active background-worker stage and then completion. RUNBOOK,
  ARCHITECTURE, and PAST INCIDENT remained visually separate from the model conclusion; console
  warnings/errors were empty.
- Supabase advisors reported only informational no-policy notices (intentional server-only RLS) and
  unused indexes expected for this small development dataset.

## Async boundaries

Supabase, GitHub, Gemini, and chat-model operations are async network I/O. The HTTP request no longer
owns the model call; the lifespan-managed worker does. Semantic and lexical
database calls run concurrently in hybrid modes. Hashing, deterministic chunking, RRF, Pydantic
validation, context selection, and evidence/citation set comparisons remain synchronous because
making CPU-local transformations async would add complexity without concurrency benefit.

## Day 5 operation telemetry

`ai_operations` stores provider-neutral spans linked by trace, span, and optional parent IDs. The
worker and provider/tool boundaries record status, start/end time, duration, provider/model,
prompt/tool identifier, provider-reported token counts, fallback metadata, and bounded diagnostic
metadata. It never stores prompts, GitHub bodies, knowledge text, provider keys, or raw responses.

```text
queue_wait -> investigation
                  +-> llm_call
                  +-> github_tool
                  +-> knowledge_retrieval
                         +-> embedding
                         +-> rerank
```

`GET /api/v1/investigations/{id}/metrics` aggregates only rows for that Investigation. Failed spans
are retained with a stable error class. A telemetry write failure is logged but cannot falsify the
investigation result; the normal Evidence/citation state remains authoritative.

Token counts come only from provider response usage. Cost remains `null` unless both
`AI_PRICING_JSON` and `AI_PRICING_SOURCE_DATE` provide explicit provenance. The optional fallback is
attempted only for rate-limit or provider-unavailable failures; authentication, validation,
authority, and malformed-output failures never cross providers.

## Public demo boundary

With `PUBLIC_DEMO_MODE=true`, FastAPI rejects incident creation, investigation enqueue, and human
review with HTTP 403. The frontend reads `/api/v1/config`, shows a read-only banner, disables the
incident form, and hides investigation/review mutations. This is defense in depth: browser controls
are presentation, while the API is the authority. Reads still pass through FastAPI; no client talks
directly to Supabase.

Production startup rejects wildcard/non-HTTPS CORS, a missing public-demo guard, or an invalid
anonymous-write combination. Authentication is still absent, so a public deployment must remain
read-only.

## Final live trace (2026-08-06)

Investigation `ecc6f4e5-8273-4169-a5c4-a394d16abc00` completed in 41,748 ms with 12 stored operation
rows spanning queue wait, investigation, three LLM calls, four GitHub tools, embedding, knowledge
retrieval, and rerank. It persisted 18 Evidence rows, including five knowledge chunks, before the
model cited three owned knowledge UUIDs. Usage was 18,759 input and 2,117 output tokens; cost stayed
unknown because pricing was not configured and no fallback ran.

The database clock was about two seconds ahead of the worker during the first live attempt. Queue
telemetry now clamps the local queue-start estimate to the database-created timestamp, preserving
the operation time constraint without pretending clocks are synchronized.

## Delivery shape

The backend Docker image pins Python dependencies, runs as the unprivileged `tracepilot` user, has a
`/health` health check, and starts one Uvicorn worker. PostgreSQL is the durable queue, but the
lifespan worker is process-local, so horizontal replicas need a dedicated worker deployment or
worker-disabled API replicas. GitHub Actions runs Ruff, strict mypy, pytest, ESLint, TypeScript,
Next.js production build, and the backend image build without live secrets.
