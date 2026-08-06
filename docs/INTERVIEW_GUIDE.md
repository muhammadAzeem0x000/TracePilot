# TracePilot interview guide

## Two-minute walkthrough

Start with the trust boundary: the model proposes an allowlisted tool, Python validates its typed
arguments and fixes repository scope from the Incident, the application executes a read-only call,
and the result becomes Evidence before returning to the model. Finish with the second boundary:
Pydantic parses the conclusion and the database proves every cited UUID belongs to this run.

Then show the evolution: typed CRUD, controlled GitHub tools, hybrid knowledge retrieval, durable
PostgreSQL jobs, and final telemetry/security/holdout/delivery work. Emphasize that Evidence and the
preliminary hypothesis have separate schemas and separate UI panels.

## Design questions to expect

**Why FastAPI between Next.js and Supabase?** It centralizes validation, provider credentials,
tool authority, evidence provenance, and public-demo enforcement. Direct browser writes would split
business rules and expose too much database authority.

**Why no LangGraph or agents?** One bounded deterministic loop handles the actual workflow. A graph
framework would add state and failure semantics without solving a present branch. The six-call guard
is easy to test and audit.

**Why PostgreSQL as the queue?** Investigation state already lives there. Transactions, partial
unique indexes, row locks, leases, and `SKIP LOCKED` provide durable V1 ownership without another
service. Higher throughput or workload isolation could justify a dedicated queue later.

**How is hallucinated evidence stopped?** UUID shape is only the first check. The service queries
persisted Evidence and compares the complete cited set against the current incident/investigation;
unknown and cross-context IDs fail the run.

**Why hybrid retrieval?** Embeddings cover paraphrase while PostgreSQL FTS helps exact identifiers.
RRF combines ranks without pretending cosine and lexical scores share a scale. On the fixed benchmark,
semantic and hybrid tied; reranking improved top rank at a 2.9-second latency cost.

**How safe is fallback?** It is one optional provider boundary for rate-limit/unavailable errors
only. Auth, tool, citation, and output-validation failures never trigger it. Provider/reason is stored
in telemetry.

**Why is cost null?** Provider token counts were available, but no explicitly dated price registry
was configured. The system refuses to invent or silently hardcode cost.

**Why no cache?** The measured query embedding was 711 ms of a 41.7-second run. Chat and GitHub calls
dominated, and caching conclusions risks stale evidence. Unchanged corpus embeddings are already
skipped by content hash.

**Why Pydantic around model output?** Model JSON is untrusted input. Bounded confidence, UUID parsing,
required fields, and forbidden extras fail before persistence; database ownership is checked next.

**How does a tool call execute?** The provider returns a name and JSON arguments. Python finds that
name in a fixed registry, validates the matching argument model, injects the Incident repository,
executes the server-side client, normalizes the result, persists Evidence, and returns bounded data.

**Why persist Evidence before returning it to the model?** The model can cite only a UUID that already
exists. This creates provenance even if a later model call or worker fails.

**What did RRF contribute?** It merged semantic and lexical ordinal ranks without comparing
incompatible score magnitudes. On this corpus it tied semantic relevance metrics, so its value is
exact-term coverage and a stable fusion contract—not a claimed benchmark uplift.

**How does `SKIP LOCKED` prevent double claims?** Competing workers lock different eligible rows;
locked work is skipped inside the claim transaction. The live two-worker probe returned one claim.

**What problem does a lease solve?** A row lock ends at transaction commit. A persisted expiry lets a
new worker reclaim a job when the original process dies after claiming it.

**What does at-least-once execution imply?** A crash can replay work after lease expiry. Read tools
are safe today; future mutation tools would require operation-level idempotency keys and approval.

**Why is model confidence not probability?** It is a bounded self-report, not calibrated frequency.
The holdout had no incorrect outcomes, so confidence-on-incorrect is honestly undefined.

**How do normal tests differ from AI evaluations?** Pytest uses deterministic doubles and validates
contracts/failures. Retrieval, development diagnosis, holdout, and adversarial reports each measure a
different behavior and preserve per-case data.

**Why is the Day-4 10/10 result not a holdout?** Its first run exposed tool-budget behavior and the
prompt was improved afterward. It is useful development regression evidence, not unbiased accuracy.

**How is prompt injection contained?** System instructions label retrieved content as data, but the
hard boundary is application authority: content cannot register tools, change arguments, execute
HTTP/shell/database access, or bypass Pydantic and citation checks.

**How is cross-repository access prevented?** GitHub tool argument schemas have no repository field.
The executor takes `repository_full_name` only from the Incident; adversarial scope-switch arguments
are rejected as extras.

**How would this change at larger scale?** Separate API and worker deployments, add queue/worker
capacity metrics, retention/partitioning for operation rows, tenant-aware authorization/RLS, and only
then evaluate an external queue based on measured contention and throughput.

**How would mutation tools change security?** They would need explicit user identity, fine-grained
authorization, approval checkpoints, dry-run/diff views, idempotency, audit logs, narrow credentials,
and probably a separate execution policy. None can be inferred from today's read tools.

**How would you reduce latency?** First reduce/parallelize model turns and GitHub fan-out based on the
trace, choose task-specific models, and test immutable HTTP caching. Do not optimize the 711 ms query
embedding while 20.9 seconds are in chat calls.

**Why are Evidence and hypothesis separate entities and panels?** Evidence is collected fact with a
source reference; the hypothesis is probabilistic inference over that fact. Separate persistence and
presentation prevent fluent prose from acquiring false provenance.

**Why is human review immutable?** Accept/reject is a new judgment, not an edit to history. Keeping
the model result unchanged supports auditing and future comparison between AI and reviewer outcomes.

**Why does public demo mode exist?** Without authentication, anonymous investigation/review writes
would expose paid APIs and database state. FastAPI returns 403; disabled/hidden controls are only the
matching presentation layer.

## Numbers worth knowing

- Retrieval: semantic and RRF MRR 0.875; reranked MRR 0.958; rerank latency 4,874.1 ms.
- Day-4 development set: 10/10 completed/correct after prompt-budget iteration; 7,896.5 ms average.
- Frozen holdout: 7/7 completed/correct in exactly one official run; 10,335.0 ms and 6,733.7 tokens
  average; citation precision/recall 1.0/1.0.
- Security: 13/13 expected blocks and zero forbidden executions/cross-repo access/invalid citations.
- Live trace: 12 spans, 20,876 tokens, 18 Evidence rows, five knowledge Evidence, three valid cited
  knowledge UUIDs, 41,748 ms end to end.

## Be explicit about limitations

The benchmarks are small and fictional; perfect fixture accuracy is not production accuracy.
Confidence is uncalibrated because the final runs had no incorrect cases. No authentication,
tenant-level authorization, mutation-enabled public mode, distributed worker deployment, or hosted
alerting exists. GitHub/LLM/Gemini availability and cost remain external dependencies. The public
deployment was not attempted past the backend credential boundary, so there is no live URL.

## Files to open during a discussion

1. `apps/api/app/services/investigation.py` — deterministic tool loop and citation validation.
2. `apps/api/app/ai/tools.py` — the complete model authority surface.
3. `apps/api/app/services/retrieval.py` — concurrent semantic/lexical search, RRF, rerank fallback.
4. `apps/api/app/services/worker.py` — leases, retries, progress, and tracing.
5. `apps/api/app/observability/tracing.py` — safe provider-neutral operation records.
6. `apps/web/src/app/page.tsx` — evidence/hypothesis separation and public-demo controls.
7. `evaluation/incident_holdout_manifest.json` — frozen evaluation provenance.
