# TracePilot Engineering Notes - Day 3

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
synchronous. The investigation request still waits for completion; background execution is deferred.

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
