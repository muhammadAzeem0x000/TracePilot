# TracePilot Architecture - Day 3

TracePilot remains one Next.js app, one FastAPI service, and one Supabase PostgreSQL database.
Day 3 extends the existing deterministic investigation loop with repository-scoped knowledge
retrieval; it does not add another service or orchestration framework.

## Responsibilities

### Next.js (`apps/web`)

`src/lib/api.ts` is the browser contract boundary. The incident detail view runs investigations
and renders two distinct regions: `COLLECTED EVIDENCE` and `AI PRELIMINARY HYPOTHESIS`. Knowledge
cards label their original type (`RUNBOOK`, `ARCHITECTURE`, or `PAST INCIDENT`) and expose ranking
metadata in a details element. The browser has no database or provider secret.

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

## Async boundaries

Supabase, GitHub, Gemini, and chat-model operations are async network I/O. Semantic and lexical
database calls run concurrently in hybrid modes. Hashing, deterministic chunking, RRF, Pydantic
validation, context selection, and evidence/citation set comparisons remain synchronous because
making CPU-local transformations async would add complexity without concurrency benefit.
