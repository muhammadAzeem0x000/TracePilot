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

**Status:** Accepted on Day 2

One loop is enough for model, validated tool, persisted evidence, and validated conclusion. Six tool
calls bound latency/cost and make failure tests straightforward. It is synchronous and cannot resume
after process loss; durable execution is deferred until the workflow proves it needs it.

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
