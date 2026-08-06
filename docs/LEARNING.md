# TracePilot Engineering Notes - five-day build

These notes refer to concrete code and failures in this repository.

## Embeddings need a database-level dimensional contract

`app/ai/embeddings.py` requests `gemini-embedding-001` with 768 output dimensions, rejects a wrong
count, non-finite values, zero magnitude, or a wrong dimension, then L2-normalizes vectors. Settings
also refuses a configured dimension other than the migration's `vector(768)`. Without both checks, a
model/config change would surface later as an opaque database error. Cosine similarity ranks vector
direction; it does not prove relevance or that a model understands an incident.

## A document is usually too coarse and a sentence is often too small

`DeterministicChunker` uses paragraphs and sentences before falling back to words. A whole runbook
would retrieve unrelated sections and consume the context budget. Tiny chunks can lose the
condition/action relationship; huge chunks reduce precision and cost more context. Defaults of 350
approximate tokens with 50-token overlap preserve modest boundary context. Overlap costs storage and
can create near-duplicates, so final selection deduplicates chunk UUIDs.

## Semantic-only retrieval misses exact engineering identifiers

Queries use Gemini's separate `RETRIEVAL_QUERY` task. This helps paraphrases, while the generated
PostgreSQL `tsvector` is direct for `payment_status`, error codes, and function-like names. Hybrid
mode runs repository-filtered semantic and lexical RPCs concurrently. Scores remain inspectable, but
RRF uses ranks (`k=60`) because cosine similarity and `ts_rank_cd` are not on a shared scale.

## Reranking is an experiment with a safe off-ramp

`rerank_v1.py` gives the LLM only candidate UUIDs and bounded untrusted text. `RerankResult` and
`KnowledgeReranker` require exact set equality and reject invented, duplicate, or missing IDs.
Provider/validation failure keeps RRF order with `rerank_fallback=true`. This matters because a second
model call adds latency/cost and can still make retrieval worse.

## Top-k and a context budget solve different problems

The repository retrieves up to 12 candidates per channel, `search_knowledge` permits at most six
final chunks, and `ContextAssembler` enforces 1,800 approximate tokens. Top-k bounds source count;
the budget bounds prompt weight. Retrieving more can crowd out incident/GitHub facts and increases
exposure to instruction-like repository text.

## Retrieval evaluation must expose individual failures

`knowledge/retrieval_benchmark.json` fixes 12 queries and relevant source references. The evaluation
runner calculates source hit@1/3/5, MRR, latency, and retains every result list. That reveals semantic
wins, lexical rescues, and reranking regressions rather than hiding them in one average. It evaluates
evidence selection, not whether the final LLM hypothesis is correct.

## Retrieved text crosses the same trust boundary as GitHub text

`KnowledgeToolExecutor` gets repository scope only from `ToolExecutionContext`; strict arguments reject
a model-supplied repository. Selected chunks are stored as Evidence before their UUIDs reach the LLM.
The prompt labels knowledge as data, while the hardcoded allowlist and Python citation checks enforce
the boundary independently of model obedience.

## Pydantic validation occurs at every untrusted boundary

Tool arguments, embedding responses, Supabase rows, reranker JSON, and final conclusions use separate
models. A syntactically valid UUID is not enough: `InvestigationService` asks the Evidence repository
to prove the complete cited set belongs to the current incident and investigation.

## Python typing and TypeScript protect different compositions

Python `Protocol` boundaries let strict mypy check providers/repositories without coupling services to
concrete clients; Pydantic still validates runtime input. TypeScript contracts keep evidence and
hypothesis shapes separate in the browser, but do not runtime-validate server JSON. Generated browser
contracts may become worthwhile if the API grows beyond five days.

## FastAPI dependency injection keeps live providers out of tests

`api/dependencies.py` composes Supabase, GitHub, Gemini, DeepSeek, retrieval, tools, and services.
Tests replace those boundaries with typed in-memory doubles, so ordinary pytest makes no external
calls. One remaining trade-off from Day 2 is that investigation read routes build the full provider
graph; a separate query service would improve degraded-mode reads in a larger system.

## Async is valuable at I/O boundaries, not everywhere

Supabase, GitHub, Gemini, and chat calls are async. Semantic and lexical searches run concurrently in
hybrid mode. Hashing, chunking, RRF, parsing, context selection, and citation set comparison remain
synchronous. On Day 4 the investigation request transfers ownership to a durable job and returns
`202`; async provider I/O now runs in the worker rather than holding the HTTP request open.

## Failure-driven fixes during implementation

The first remote migration failed because its functions set `search_path=''` while the pgvector
operator lives in `extensions`. PostgreSQL rolled back the transaction; qualifying it as
`OPERATOR(extensions.<=>)` fixed the forward migration. Tests then caught a duplicate `metadata`
keyword while converting chunks and Python truthiness discarding a valid `0.0` RRF component score.
Both defects were fixed before live ingestion.

Live ingestion later exposed a third SQL defect: `replace_knowledge_source` returns a column named
`source_id`, making an unqualified `delete ... where source_id = stored_source_id` ambiguous in
PL/pgSQL. PostgreSQL rejected the RPC atomically, so no partial source was stored. The forward
`202608060002_day3_fix_knowledge_replacement.sql` migration aliases and qualifies the table column;
the retry created all 10 sources and the next pass skipped all 10.

The Day 2 live verifier also advertised the new `search_knowledge` definition while wiring only the
GitHub executor. A live model correctly selected the advertised tool and exposed the mismatch.
`InvestigationService` now accepts an explicit definition set, and the GitHub-only verifier passes
only the five GitHub definitions. A regression test checks that advertised authority matches the
executor.

## What the fixed benchmark actually measured

| Mode | Hit@1 | Hit@3 | Hit@5 | MRR | Average latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Semantic | 0.750 | 1.000 | 1.000 | 0.875 | 2,110.8 ms |
| Hybrid RRF | 0.750 | 1.000 | 1.000 | 0.875 | 1,934.2 ms |
| Hybrid + rerank | 0.917 | 1.000 | 1.000 | 0.958 | 4,874.1 ms |

Semantic and hybrid returned the same relevance ranks for all 12 cases, so there is no benchmark case
where either beat the other. A separate exact-identifier probe (`payment_status UndefinedColumn`)
proved lexical SQL worked and moved the past incident ahead of the runbook, but it did not improve the
aggregate benchmark. Reranking promoted the relevant external-timeout runbook and checkout
architecture cases from reciprocal rank 0.5 to 1.0. It made no relevant source rank worse in this run.
The job-redelivery query still ranked the duplicate-refund incident above the expected general job
architecture source in all modes, leaving the sole reranked Hit@1 failure. Per-query lists remain in
`docs/evaluation/retrieval_evaluation.json`; the ground truth was not changed.

The latency result is the clearest trade-off: reranking improved top-rank relevance but added roughly
2.9 seconds compared with RRF. Hit@3 and Hit@5 were already perfect, so the extra call improved only
ordering, not whether relevant material reached the five-chunk context.

## A `202` response needs durable ownership transfer

The route in `app/api/routes.py` now validates the Incident and calls an atomic enqueue RPC; it never
starts an untracked coroutine. `app/services/worker.py` owns execution after the response. This is the
meaningful boundary: the request is fast relative to the 46-second live investigation, while the job
survives request cancellation and process restart through its database state.

## Row locking solves claim contention; leases solve worker death

`claim_investigation_job` combines `FOR UPDATE SKIP LOCKED` with `lease_expires_at`. A row lock alone
prevents simultaneous claims only during the transaction; it cannot show that a worker died after
commit. The live check issued two concurrent claims and got one job, then expired that lease and
reclaimed the same job at attempt two.

## Retry policy is domain policy, not a blanket exception handler

`investigation_errors.py` separates transient provider/storage failures from permanent authority,
validation, citation, dimension, and tool-loop failures. The worker uses `base * 2^(attempt-1)` and
the job's persisted maximum. Live verification scheduled a transient retry, exhausted it at attempt
two, and stopped a permanent error at attempt one. An unexpected programming error is terminal and
logged rather than replayed indefinitely.

## Durable timestamps must share a clock

The first live queue run exposed a PostgreSQL integrity error: the worker clock was about three
seconds behind Supabase, so `completed_at` could be earlier than database-generated `started_at`.
`20260806093000_day4_server_timestamps.sql` moved terminal stamps and retry eligibility to
`clock_timestamp()`. The Supabase client now also preserves bounded HTTP error detail internally,
which made the violated constraint diagnosable without exposing a secret to API clients.

## A diagnosis benchmark is not a retrieval benchmark

`evaluation/incident_benchmark.json` fixes ten incident inputs, available tool Evidence, expected
culprit references, and relevant citation sets. `app/evaluation/harness.py` still uses the production
investigation loop and real DeepSeek output. Culprit accuracy and citation metrics therefore measure
tool choice plus reasoning, while Day 3 Hit@k/MRR measures only retrieval ordering.

The first live diagnosis run completed 2/10: eight cases kept requesting tools until the six-call
guard rejected them. The benchmark was not changed and the limit was not raised. Adding explicit
budget/stop guidance to `investigation_v2` produced 10/10 completion and accuracy, precision, and
recall in the committed run, with 4.2 tool calls and 7.90 seconds average latency. This is a useful
prompt regression result, not evidence of broad generalization.

## Confidence analysis needs incorrect cases

Average confidence was 0.615 and every final diagnosis was correct, leaving confidence-on-incorrect
undefined. Reporting `n/a` is more honest than treating zero or omitting the field. Confidence is a
model claim; the deterministic culprit and citation checks are the correctness measurements.

## Human review should not edit history

The browser can accept or reject a completed Investigation, but `investigation_reviews` is separate
from model output. Live API verification accepted and then rejected the same conclusion and confirmed
the summary, confidence, suspected change, and citation IDs were byte-for-byte unchanged.

## Tracing must preserve causality without preserving sensitive content

`app/observability/tracing.py` propagates trace/span context through the worker, provider, GitHub,
embedding, retrieval, and rerank boundaries. `OperationCreate` deliberately has no prompt or response
field. The real trace still answers where 41.7 seconds went and which providers ran, while a database
reader cannot recover incident text from telemetry.

## Provider token usage and model identity are observations, not configuration

The configured alias was `deepseek-chat`, while live provider responses identified
`deepseek-v4-flash`. `app/ai/provider.py` records both rather than overwriting one. The same responses
reported 20,876 tokens for the final live trace. Because no dated price registry was configured,
`estimated_cost_usd` correctly stayed null.

## Fallback must not hide an authority or validation defect

`FallbackLLMProvider` catches only `LLMRateLimitError` and `LLMUnavailableError`. Tests prove auth
and validation errors return directly. A broad `except` here would make security failures harder to
diagnose and could send sensitive context to an unintended provider.

## Cross-system clocks fail at surprisingly small skew

Day 4 moved durable job timestamps to PostgreSQL, but the first Day-5 trace still derived queue start
from a local wall clock. Supabase was about two seconds ahead, violating `ended_at >= started_at`.
`clamp_queue_started_at` now bounds the local estimate by the database-created timestamp; a regression
test captures the exact skew case.

## Native optional packages matter in a Linux frontend build

The Windows Next.js build passed while the first Linux container build could not resolve
`lightningcss`, then Tailwind's oxide binary. Root optional dependencies now lock the Linux glibc
artifacts and Next.js SWC variants. The rebuilt Linux production frontend compiled and type-checked;
this was a portability defect, not an application-code failure.

## A security evaluation should count forbidden side effects

`app/security/evaluation.py` uses production Pydantic tool/citation validators against 13 fixed
attacks. The primary metric is not an LLM's opinion: forbidden tool executions, cross-repository
access, invalid citations, and unsafe mutations must each remain zero. Prompt-injection strings are
treated as data, and no HTML bypass exists in the browser.

## Holdout discipline is part of the implementation

`incident_holdout_manifest.json` hashes the seven cases, prompt, rerank prompt, tool definitions, and
tool-call limits. The only official run completed 7/7 with perfect fixture-based culprit/citation
scores, but that result does not calibrate confidence or estimate production accuracy. Preserving the
cases and per-scenario output is more useful than rerunning until a preferred number appears.

## Measure before caching

The query embedding consumed 711 ms, about 1.7% of a 41,748 ms trace. Chat and GitHub I/O dominated.
Adding cache keys, expiry, and stale-evidence semantics would create more correctness risk than the
measured latency benefit. The one existing cache-like optimization—content hashes that skip unchanged
corpus ingestion—has clear identity and invalidation rules.
