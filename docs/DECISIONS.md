# Architecture Decision Records

## ADR-001: Separate FastAPI backend from Next.js

**Status:** Accepted on Day 1

Next.js owns interaction and FastAPI owns validation, persistence, and investigation behavior.
This creates a testable HTTP contract and keeps server credentials outside the browser. The cost is
two local processes, CORS, and duplicated TypeScript/Python contract declarations.

## ADR-002: PostgreSQL/Supabase as the primary database

**Status:** Accepted on Day 1

Incident, Evidence, and Investigation have relational identities, constraints, and lifecycles.
PostgreSQL supplies those directly; Supabase hosts it and provides PostgREST for async server I/O.
The cost is hosted-service availability and careful service-key/RLS handling. Tests use repository
doubles rather than production state.

## ADR-003: Explicit Incident / Evidence / Investigation entities

**Status:** Accepted on Day 1, extended on Day 2

Operational facts, collected source material, and an analysis attempt have different provenance and
lifecycle. Separate entities permit multiple investigations and keep evidence independently
inspectable. Day 2 adds nullable `repository_full_name` to Incident as the smallest useful context;
it can become a normalized Project/Service entity if multiple repositories/services are needed.

## ADR-004: The LLM cannot execute tools directly

**Status:** Accepted on Day 2

The model may propose only named function calls. Python checks the allowlist, validates arguments,
executes GitHub REST, persists the result, and returns bounded evidence. This makes permissions
enforceable in code and auditable in tests. The trade-off is an orchestration loop and provider
message plumbing, but the alternative would give untrusted output authority over external I/O.

## ADR-005: Model output and repository content are untrusted

**Status:** Accepted on Day 2

Tool-call JSON is Pydantic-validated and forbids extra arguments. Final JSON must satisfy a strict
Pydantic schema, then every evidence UUID is re-queried within the current incident/investigation.
GitHub text is labelled untrusted evidence in the prompt and tool response because commit messages,
PR bodies, and patches can contain instruction-like text. This boundary reduces, but does not claim
to eliminate, prompt-injection risk.

## ADR-006: Read-only GitHub tools

**Status:** Accepted on Day 2

The registered operations list/get commits, list/get pull requests, and list PR files. The client
implements only HTTP `GET`; there is no create, edit, merge, push, close, or delete path. Read-only
scope is sufficient for preliminary investigation and substantially limits consequences if a model
requests the wrong operation. It cannot gather issues, Actions logs, deployment data, or runtime
telemetry yet.

## ADR-007: Structured Pydantic output

**Status:** Accepted on Day 2

The conclusion has named fields for summary, bounded confidence, suspected change, supporting UUIDs,
missing information, and next steps. Pydantic makes malformed JSON, missing fields, invalid UUIDs,
out-of-range confidence, duplicate citations, and unsupported high confidence explicit failures.
One correction attempt handles minor model mistakes; repeated failure marks the investigation failed.
The schema constrains shape, not factual truth, so citation ownership checks remain separate.

## ADR-008: Bounded deterministic loop instead of LangGraph or multiple agents

**Status:** Accepted on Day 2

One service loop is enough for the current sequence: model, validated tool, persisted evidence, model,
validated conclusion. Six total tool calls prevent unbounded cost/latency; one output correction is
allowed. This is easy to trace and test. It is synchronous and cannot resume after process failure;
durable/background orchestration is deferred until the workflow proves it needs it.

## ADR-009: Store evidence and hypotheses separately

**Status:** Accepted on Day 2

Evidence rows contain normalized GitHub facts and durable source references. Investigation rows
contain model-generated conclusions and citations. Separation prevents generated prose from being
presented as collected fact and lets the UI reinforce the distinction. It adds joins and coordinated
writes, which are justified by provenance being the project’s central engineering concern.
