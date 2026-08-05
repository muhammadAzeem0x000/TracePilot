# Day-2 Engineering Notes

These notes refer to decisions and failures encountered in this repository.

## Pydantic validation must cover both model calls

`schemas/github.py` gives each tool an argument model with `extra="forbid"`; valid JSON with a
hallucinated field is still rejected. `schemas/investigation.py` separately validates final JSON,
including required fields, UUID syntax, confidence `0..1`, duplicate citations, bounded list items,
and the rule that confidence above `0.7` requires cited evidence. Schema validation alone cannot
prove a UUID is real, so `InvestigationService._validate_evidence_references` performs the database
ownership check.

## Python typing and TypeScript protect different compositions

Python `Protocol` boundaries let strict mypy check that the GitHub client, LLM provider, and three
repositories compose without importing concrete implementations into the service. Pydantic is still
needed at runtime for HTTP, GitHub, provider, and PostgREST data. TypeScript interfaces in
`web/src/lib/api.ts` prevent components from mixing Evidence and Investigation shapes, but they do
not runtime-validate the server. A generated/runtime browser contract could become worthwhile if the
API grows beyond this five-day project.

## FastAPI dependency injection exposed a configuration trade-off

`api/dependencies.py` constructs one Supabase client per request dependency graph and injects
repository protocols into services. Tests override repositories or the investigation service, so 26
tests exercise HTTP/orchestration without remote calls. The current investigation read routes share
the same full service dependency as the run route, so GitHub/LLM configuration is resolved for reads;
splitting a query service would improve degraded-mode reads if the API grows.

## Async adds value only around actual waiting

Supabase, GitHub, and provider calls use `httpx.AsyncClient`, allowing FastAPI to serve other work
while each request waits on I/O. Tool validation, prompt building, Pydantic parsing, allowlist checks,
and evidence/citation set comparison are synchronous. Making those helpers async would not improve
concurrency. Day 2 still holds the HTTP request open for the full workflow; long-running resilience
requires a future background design.

## Repository/service separation earned its cost through safety checks

Repositories know PostgREST filters and remote response shapes. `InvestigationService` knows that a
missing repository is a use-case conflict, a failed dependency must mark state failed, a tool loop is
bounded, and citations must belong to one context. `GitHubToolExecutor` sits between them because its
single job—validate tool authority, execute, and persist before returning—is security-sensitive and
independently testable. A generic tool framework would add no value today.

## Stable HTTP errors must not pretend a failed investigation completed

Input errors remain FastAPI `422`; missing incidents/investigations are `404`; missing repository
context is `409`; storage errors are `503`; and a created investigation that fails during GitHub,
provider, tool, or output processing is persisted as `failed` and returned as `502` with its UUID.
Provider payloads and tokens are never returned. The failure state update is attempted separately so
the original error is not silently swallowed if that second database write also fails.

## Migration history is append-only once remote state exists

During verification, the Day-2 foundation migration was already recorded remotely. A local edit had
added runtime columns to that historical file, which would have created drift. The fix restored the
applied migration exactly and added `202608050002_day2_investigation_runtime_metadata.sql` as a new
forward migration. The remote schema was then checked for eight Day-2 investigation columns, two
indexes, and the update trigger.

## GitHub content needs both size and instruction boundaries

`integrations/github.py` selects application-owned fields, caps list sizes, limits files, truncates
messages/descriptions/patches, and never sends raw API payloads to the model. The versioned prompt and
tool response label repository text as untrusted data. This does not make repository content safe in
an absolute sense; it ensures content cannot expand the hardcoded tool allowlist or directly execute
anything.
