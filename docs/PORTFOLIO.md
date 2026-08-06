# TracePilot portfolio case study

## The engineering problem

Incident assistants can sound certain while citing nothing inspectable. TracePilot explores a
stronger contract: collect bounded evidence through server-owned read tools, persist it first,
validate structured conclusions and UUID ownership, and show facts separately from inference.

This is a five-day learning build, not production incident-response software. Its fixtures and demo
documents are fictional, authentication is absent, and public mutations are disabled.

**Recruiter summary:** TracePilot is a full-stack Applied AI portfolio system that demonstrates the
engineering around a model—not just the model call: typed APIs, read-only tool authority, durable
Evidence and jobs, hybrid retrieval, citation verification, human review, safe telemetry, adversarial
testing, frozen evaluation, containers, and CI. It makes every measured claim reproducible while
keeping synthetic results and production limitations explicit.

## Five-day evolution

1. **Foundation:** Next.js calls typed FastAPI routes; repositories persist incidents, Evidence, and
   Investigations in Supabase PostgreSQL.
2. **Controlled investigation:** an OpenAI-compatible model proposes only allowlisted read-only
   GitHub tools. Python validates/executes them and Pydantic validates the final hypothesis.
3. **Knowledge retrieval:** Gemini embeddings, pgvector cosine search, PostgreSQL full-text search,
   RRF, optional validated reranking, context budgets, and knowledge Evidence.
4. **Durable execution:** PostgreSQL jobs, leases, `SKIP LOCKED`, error-specific retry, progress,
   immutable human review, and a fixed development diagnosis benchmark.
5. **Trust and delivery:** safe operation telemetry, optional bounded fallback, adversarial tests, a
   frozen holdout, public-demo enforcement, Docker, and CI.

## Measured results kept separate

| Evaluation | Dataset | Primary result | Important limitation |
| --- | --- | --- | --- |
| Retrieval | 12 fixed queries, 10 demo docs | Semantic/RRF MRR 0.875; reranked MRR 0.958 | Same tiny corpus used during development |
| Development diagnosis | 10 fixed Evidence fixtures | 10/10 complete and correct; 7.90 s average | Prompt was improved after an initial 2/10 completion run |
| Final holdout | 7 newly frozen fixtures, one run | 7/7 complete/correct; 10.34 s average; citation P/R 1.0/1.0 | Synthetic, small, no incorrect cases for calibration |
| Adversarial | 13 deterministic attacks | 13/13 expected blocks; zero forbidden side effects | Validates local boundaries, not every possible attack |

Reranking improved retrieval Hit@1 from 0.750 to 0.917 and MRR from 0.875 to 0.958, while average
latency increased from 1,934.2 ms to 4,874.1 ms. The final holdout averaged 6,733.7
provider-reported tokens. Cost is intentionally unknown because no dated pricing registry was set.

## Evidence-grounding protections

- The Incident fixes repository scope; tool arguments cannot select another repository.
- The model never owns HTTP, shell, filesystem, database, or GitHub credentials.
- GitHub and knowledge text are untrusted data, not instructions.
- Every selected knowledge chunk is persisted before its UUID returns to the model.
- Final UUIDs must exist and belong to the current incident/investigation.
- Unknown/malformed tools, loops beyond six calls, invalid JSON, out-of-range confidence, and
  cross-context citations fail explicitly.
- Public demo mode blocks mutations at FastAPI, independently of browser controls.

## What the final trace showed

One real investigation took 41,748 ms. Three LLM calls accounted for 20,935 ms, four GitHub tools
7,414 ms, knowledge retrieval 6,263 ms, reranking 2,381 ms, and embedding 711 ms. The model invoked
`search_knowledge`; five chunks became Evidence and three owned UUIDs were cited. This measurement
rejected a speculative cache: the easy embedding target was only 1.7% of latency, while conclusion
caching would introduce stale-evidence risk.

## Delivery and remaining risk

The backend image is non-root, health-checked, and dependency-pinned. CI checks Python lint/types/tests,
frontend lint/types/build, and the image without secrets. A public deployment was not created because
backend host credentials were unavailable; publishing only the authenticated Vercel frontend would
have produced a broken demo. The largest production gaps are authentication/authorization,
multi-tenant policies, dedicated worker topology, operational alerting, larger real-world evaluation,
and provider/data-governance review.

## CV bullet candidates

- Built a five-day Next.js/FastAPI/Supabase incident-investigation system with allowlisted read-only
  GitHub/knowledge tools, durable Evidence, bounded model execution, citation ownership checks, and
  a leased PostgreSQL job worker.
- Implemented and measured pgvector + PostgreSQL FTS + RRF retrieval; validated LLM reranking raised
  Hit@1 from 0.750 to 0.917 and MRR from 0.875 to 0.958 on a fixed synthetic 12-query benchmark.
- Added provider-neutral AI telemetry, read-only public-demo enforcement, a non-root Docker image,
  CI, and a 13-case deterministic adversarial suite with zero forbidden executions, cross-repository
  accesses, invalid citations accepted, or unsafe mutations.
