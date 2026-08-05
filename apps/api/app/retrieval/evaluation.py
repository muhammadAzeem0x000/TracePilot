import time

from pydantic import BaseModel, Field

from app.retrieval.service import KnowledgeRetrievalService
from app.schemas.knowledge import KnowledgeSearchMode


class RetrievalBenchmarkCase(BaseModel):
    query: str = Field(min_length=1)
    relevant_sources: list[str] = Field(min_length=1)
    notes: str | None = None


class QueryEvaluation(BaseModel):
    query: str
    relevant_sources: list[str]
    retrieved_sources: list[str]
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float
    latency_ms: float
    rerank_fallback: bool


class MethodEvaluation(BaseModel):
    mode: KnowledgeSearchMode
    source_hit_at_1: float
    source_hit_at_3: float
    source_hit_at_5: float
    mrr: float
    average_latency_ms: float
    cases: list[QueryEvaluation]


class RetrievalEvaluationReport(BaseModel):
    repository_full_name: str
    methods: list[MethodEvaluation]


async def evaluate_method(
    service: KnowledgeRetrievalService,
    repository_full_name: str,
    cases: list[RetrievalBenchmarkCase],
    mode: KnowledgeSearchMode,
) -> MethodEvaluation:
    results: list[QueryEvaluation] = []
    for case in cases:
        started = time.perf_counter()
        response = await service.search(case.query, repository_full_name, mode, top_k=5)
        latency_ms = (time.perf_counter() - started) * 1_000
        retrieved = [item.source_reference for item in response.items]
        relevant = set(case.relevant_sources)
        first_rank = next(
            (rank for rank, source in enumerate(retrieved, start=1) if source in relevant),
            None,
        )
        results.append(
            QueryEvaluation(
                query=case.query,
                relevant_sources=case.relevant_sources,
                retrieved_sources=retrieved,
                hit_at_1=bool(relevant.intersection(retrieved[:1])),
                hit_at_3=bool(relevant.intersection(retrieved[:3])),
                hit_at_5=bool(relevant.intersection(retrieved[:5])),
                reciprocal_rank=0.0 if first_rank is None else 1.0 / first_rank,
                latency_ms=latency_ms,
                rerank_fallback=response.rerank_fallback,
            )
        )

    count = len(results)
    if count == 0:
        raise ValueError("Retrieval benchmark must contain at least one case")
    return MethodEvaluation(
        mode=mode,
        source_hit_at_1=sum(item.hit_at_1 for item in results) / count,
        source_hit_at_3=sum(item.hit_at_3 for item in results) / count,
        source_hit_at_5=sum(item.hit_at_5 for item in results) / count,
        mrr=sum(item.reciprocal_rank for item in results) / count,
        average_latency_ms=sum(item.latency_ms for item in results) / count,
        cases=results,
    )
