# Architecture Decision Records

## ADR-001: Separate FastAPI backend from Next.js

**Status:** Accepted on Day 1

Next.js owns interaction; FastAPI owns validation, persistence, and investigations. This keeps all
server credentials outside the browser and makes one HTTP contract testable. The cost is two local
processes, CORS, and coordinated TypeScript/Python contracts.

## ADR-002: PostgreSQL/Supabase as the primary database

**Status:** Accepted on Day 1

Incidents, Evidence, Investigations, sources, and chunks have relational identities and constraints.
Supabase hosts PostgreSQL and exposes PostgREST for async server I/O. The trade-off is hosted-service
availability and careful service-key/RLS handling; ordinary tests therefore use repository doubles.

## ADR-003: Explicit Incident, Evidence, and Investigation entities

**Status:** Accepted on Day 1, extended on Day 2

Operational facts, collected material, and model conclusions have different provenance/lifecycles.
Separate records permit multiple investigations and inspectable evidence. A nullable repository name
is the smallest current scope; a Project/Service entity is deferred until multiple repositories need it.

## ADR-004: The LLM cannot execute tools directly

**Status:** Accepted on Day 2

The model proposes named calls; Python checks an allowlist and Pydantic arguments, performs I/O,
persists Evidence, and returns bounded results. This makes authority enforceable in code. The cost is
explicit orchestration/provider message plumbing.

## ADR-005: Model output and repository content are untrusted

**Status:** Accepted on Day 2, extended on Day 3

Tool JSON forbids extra fields. Final JSON is schema-validated and every evidence UUID is re-queried
within its incident/investigation. GitHub and knowledge text are labelled untrusted data because they
may contain instruction-like content. Prompts help, but hardcoded permissions and ownership checks
are the security boundary.

## ADR-006: Read-only GitHub tools

**Status:** Accepted on Day 2

Only GET-based commit and pull-request inspection exists. No create, merge, edit, push, close, or
delete path is implemented. This is enough for preliminary evidence collection and limits impact;
Actions logs, deployments, issues, and runtime telemetry remain unavailable.

## ADR-007: Structured Pydantic model output

**Status:** Accepted on Day 2

Pydantic enforces named conclusion fields, bounded confidence, UUIDs, and list constraints. One
correction attempt handles formatting mistakes; repeated failure marks the investigation failed.
Shape validation cannot prove truth, so database citation validation remains separate.

## ADR-008: Bounded deterministic loop instead of LangGraph or multiple agents

**Status:** Accepted on Day 2, execution extended on Day 4

One loop is enough for model, validated tool, persisted evidence, and validated conclusion. Six tool
calls bound latency/cost and make failure tests straightforward. Day 4 retained this explicit loop
inside a durable leased job; process loss now causes lease-based replay without introducing a graph
framework or additional agent authority.

## ADR-009: Store evidence and hypotheses separately

**Status:** Accepted on Day 2

Evidence contains collected facts and durable references; Investigation contains generated analysis
and citations. This prevents prose from being presented as fact and lets the UI show the distinction.
It adds joins and coordinated writes, justified by provenance being TracePilot's core concern.

## ADR-010: Keep vectors in PostgreSQL with pgvector

**Status:** Accepted on Day 3

Source metadata, chunks, repository scope, and embeddings share one transactional lifecycle. pgvector
adds cosine search without another database, synchronization job, or failure domain. The trade-off is
Postgres-specific SQL. HNSW demonstrates a scalable path, not a speed claim for this tiny corpus.

## ADR-011: Deterministic bounded chunking

**Status:** Accepted on Day 3

`DeterministicChunker` favors paragraphs, then sentences, then words, with configurable maximum and
overlap. It gives stable indexes without LLM cost/nondeterminism. Provider-specific token counting
would be more exact, but the current approximation is transparent and sufficient for this project.

## ADR-012: Semantic plus PostgreSQL lexical search with RRF

**Status:** Accepted on Day 3

Embeddings retrieve concepts, but investigations often depend on exact identifiers such as
`payment_status` and exception names. PostgreSQL full-text search adds that channel without
Elasticsearch. RRF combines ordinal positions instead of comparing incompatible cosine and text-rank
scores. It is explainable and deterministic, though it does not learn query-specific weights.

## ADR-013: Embeddings are coordinates, not understanding

**Status:** Accepted on Day 3

Gemini maps text to validated 768-number vectors. Cosine proximity signals distributional similarity,
not relevance, causality, correctness, or "understanding." TracePilot retains source text/ranking
diagnostics and evaluates retrieval against fixed labels rather than treating similarity as truth.

## ADR-014: Optional, strictly validated reranking

**Status:** Accepted on Day 3

`rerank_v1` asks the existing chat provider to reorder a bounded candidate set. The result must contain
every known UUID exactly once. Invented, missing, duplicate, or malformed IDs fail validation; model
or validation failure falls back to RRF. This prevents an extra LLM call from becoming mandatory or
automatically trusted.

The live 12-query benchmark supports keeping this optional: reranking improved Hit@1 from 0.750 to
0.917 and MRR from 0.875 to 0.958, but average latency increased from 1,934.2 ms for RRF to 4,874.1 ms.
It improved two queries, left one Hit@1 error unchanged, and produced no measured reciprocal-rank
regression in this run. These results are evidence for this small corpus, not a general guarantee.

## ADR-015: Persist retrieved chunks as Evidence

**Status:** Accepted on Day 3

The vector index is retrieval infrastructure, not investigation provenance. Each selected chunk
becomes `knowledge_chunk` Evidence before the LLM receives its UUID, preserving the exact text/ranks
used and reusing citation ownership checks. Evidence duplicates selected text intentionally but never
stores the vector.

## ADR-016: Bound top-k and context independently

**Status:** Accepted on Day 3

Retrieval is capped at 12 candidates per channel, the tool can select at most six chunks, and context
defaults to 1,800 approximate tokens. More context can dilute relevant facts, increase cost/latency,
and enlarge the prompt-injection surface. The trade-off is measurable omission of lower-ranked facts.

## ADR-017: Evaluate retrieval separately from answer quality

**Status:** Accepted on Day 3

The fixed 12-query benchmark records source hit@1/3/5, MRR, latency, and per-query lists for semantic,
hybrid, and reranked modes. It does not judge final prose. This separates evidence-selection quality
from reasoning quality and prevents fluent answers from masking retrieval failures.

The first live run found semantic and RRF metrics identical. Therefore TracePilot does not claim
hybrid improved the checked-in benchmark. Exact-identifier lexical retrieval was still verified
directly, and retaining both channels remains justified for identifier-heavy engineering queries.

## ADR-018: PostgreSQL is the durable investigation queue

**Status:** Accepted on Day 4

The request creates an Investigation and job transactionally, returns `202`, and a worker claims the
job later. PostgreSQL already owns the related state and provides transactions, row locks, and crash
recovery, avoiding another Day-4 service. FastAPI `BackgroundTasks` is process-local and would lose
work on restart; an external queue may become appropriate when throughput or isolation demands it.

## ADR-019: Leases, `SKIP LOCKED`, and bounded error-specific retry

**Status:** Accepted on Day 4

Claims use `FOR UPDATE SKIP LOCKED`, an expiring lease, and an incremented attempt count so workers do
not double-claim and process loss is recoverable. Rate limits, timeouts, provider unavailability, and
storage failures retry with bounded exponential backoff. Authentication, permission/404, malformed
tools, invalid output/citations, dimension mismatch, and tool-limit failures stop immediately.
At-least-once execution means external side effects would need idempotency; today all tools are reads.

## ADR-020: One active investigation per Incident

**Status:** Accepted on Day 4

A partial unique index plus Incident-row locking makes duplicate enqueue safe under concurrency. A
repeat request returns the active Investigation ID rather than a conflict or duplicate job. Completed
or failed history remains immutable and permits a new run. This is a V1 product rule, not a claim that
parallel investigations are never useful.

## ADR-021: Fixed Evidence fixtures evaluate diagnosis, not retrieval drift

**Status:** Accepted on Day 4

The ten-scenario benchmark uses the real configured LLM, production orchestration, tool validation,
Evidence persistence, Pydantic output, and citation checks, but fixed tool results. Expected culprit
is the exact retrieved `source_reference`, making accuracy deterministic without an LLM judge. This
isolates reasoning/tool choice from changing GitHub state; Day 3's retrieval benchmark remains a
separate layer and is not replaced.

## ADR-022: Confidence is reported, not calibrated

**Status:** Accepted on Day 4

TracePilot records bounded model confidence and compares correct versus incorrect cases, but never
presents it as probability. The live benchmark had no incorrect final cases, so incorrect-confidence
is `n/a`; ten fictional scenarios cannot establish calibration. Invalid evidence references still
fail independently of confidence.

## ADR-023: Human review is a separate immutable judgment

**Status:** Accepted on Day 4

An accept/reject decision and note live in `investigation_reviews`; they do not overwrite the model
summary, confidence, culprit, or citations. This preserves provenance and makes disagreement visible.
The V1 has one upserted review and no reviewer identity because authentication is deferred.

## ADR-024: Database clocks own durable timestamps

**Status:** Accepted on Day 4 after live verification

Live Supabase testing found enough host/database clock skew for a client completion timestamp to
precede the database start timestamp. Triggers now stamp terminal transitions and the retry RPC
computes eligibility with PostgreSQL's clock. Durable ordering no longer assumes synchronized worker
clocks; application timers remain suitable only for local latency measurement.

## ADR-025: Internal provider-neutral operation telemetry

**Status:** Accepted on Day 5

TracePilot persists its own typed spans instead of adding a hosted observability platform. This
keeps evidence, jobs, and measurements in one database and makes provider replacement possible
without changing the UI contract. The trade-off is fewer visualization and sampling features.
Telemetry contains identifiers, timing, counts, status, and bounded metadata only; raw prompts,
evidence bodies, and secrets are excluded.

## ADR-026: Provider usage is trusted narrowly; pricing must be explicit

**Status:** Accepted on Day 5

Token counts are recorded only when a provider returns them. TracePilot does not estimate missing
tokens and does not silently substitute a model price. A cost is calculated only from a configured
model entry plus a dated pricing source. This leaves honest `null` values in the live run, but avoids
presenting invented precision as engineering evidence.

## ADR-027: Fallback is conditional, observable, and bounded

**Status:** Accepted on Day 5

An optional secondary provider receives one attempt only after a rate-limit or unavailable-provider
error. Authentication, permission, schema, citation, tool, and other validation failures are not
fallback candidates. Every switch records the provider/model and reason. Availability improves
without turning deterministic defects into hidden cross-provider retries.

## ADR-028: Anonymous public demos are read-only at the API

**Status:** Accepted on Day 5

Authentication and tenant authorization were intentionally out of scope. Public demo mode therefore
rejects all three business mutations server-side while the UI disables/hides the same actions. A
read-only portfolio can display real persisted artifacts without granting anonymous users access to
paid model calls, GitHub scope, or human-review writes.

## ADR-029: Freeze the final holdout before one official run

**Status:** Accepted on Day 5

Seven unseen fictional scenarios, the production prompt, tool definitions, and tool budget were
hashed and committed before the only official run. Results retain every scenario, including
failures. The set is deliberately separate from the Day-4 development benchmark so prompt tuning
cannot leak into the claimed final evaluation. Seven synthetic fixtures remain too small for a
general accuracy claim.

## ADR-030: Do not add a speculative investigation cache

**Status:** Accepted on Day 5 after measurement

The live trace spent 20,935 ms in chat calls and 7,414 ms in GitHub tools; query embedding was only
711 ms of 41,748 ms. Caching conclusions risks stale incident evidence, while caching mutable GitHub
lists needs invalidation policy not justified by this workload. Existing content-hash ingestion
already skips unchanged document embeddings. Future immutable commit-detail or content-addressed
embedding caches require workload evidence first.

## ADR-031: Ship a non-root image and CI, but avoid a broken partial deployment

**Status:** Accepted on Day 5

The API has a pinned Python 3.12 image and the repository has secret-free CI for both applications.
Vercel authentication was available during verification, but Koyeb/backend credentials were not.
Deploying the frontend with no reachable API would misrepresent the system, so no partial production
URL was created. Deployment remains an explicit environment operation documented in `DEPLOYMENT.md`.
