import asyncio
import logging
from uuid import UUID

from app.ai.embeddings import EmbeddingProvider, EmbeddingTask
from app.ai.provider import LLMProviderError
from app.repositories.knowledge import KnowledgeSearchRepository
from app.retrieval.context import ContextAssembler
from app.retrieval.reranking import KnowledgeReranker, RerankingValidationError
from app.schemas.knowledge import (
    KnowledgeSearchMode,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    KnowledgeSearchRow,
)

logger = logging.getLogger(__name__)
RRF_K = 60


class KnowledgeRetrievalService:
    def __init__(
        self,
        repository: KnowledgeSearchRepository,
        embedding_provider: EmbeddingProvider,
        context_assembler: ContextAssembler,
        *,
        candidate_limit: int = 12,
        reranker: KnowledgeReranker | None = None,
    ) -> None:
        self._repository = repository
        self._embeddings = embedding_provider
        self._context = context_assembler
        self._candidate_limit = candidate_limit
        self._reranker = reranker

    async def search(
        self,
        query: str,
        repository_full_name: str,
        mode: KnowledgeSearchMode,
        top_k: int,
    ) -> KnowledgeSearchResponse:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Knowledge search query cannot be empty")
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be between 1 and 10")

        rerank_fallback = False
        if mode is KnowledgeSearchMode.SEMANTIC:
            ordered = await self._semantic(clean_query, repository_full_name)
        else:
            semantic, lexical = await asyncio.gather(
                self._semantic(clean_query, repository_full_name),
                self._lexical(clean_query, repository_full_name),
            )
            ordered = self.fuse(semantic, lexical)
            if mode is KnowledgeSearchMode.RERANKED and self._reranker is not None:
                try:
                    ordered = await self._reranker.rerank(clean_query, ordered)
                except (LLMProviderError, RerankingValidationError):
                    rerank_fallback = True
                    logger.warning("knowledge_rerank_fallback")

        selected, context_tokens = self._context.select(ordered, top_k)
        return KnowledgeSearchResponse(
            query=clean_query,
            repository_full_name=repository_full_name,
            mode=mode,
            items=selected,
            count=len(selected),
            rerank_fallback=rerank_fallback,
            context_tokens=context_tokens,
        )

    async def _semantic(
        self,
        query: str,
        repository_full_name: str,
    ) -> list[KnowledgeSearchResult]:
        vectors = await self._embeddings.embed([query], task=EmbeddingTask.QUERY)
        rows = await self._repository.semantic_search(
            repository_full_name,
            vectors[0],
            self._candidate_limit,
        )
        return [self._from_semantic(row, rank) for rank, row in enumerate(rows, start=1)]

    async def _lexical(
        self,
        query: str,
        repository_full_name: str,
    ) -> list[KnowledgeSearchResult]:
        rows = await self._repository.lexical_search(
            repository_full_name,
            query,
            self._candidate_limit,
        )
        return [self._from_lexical(row, rank) for rank, row in enumerate(rows, start=1)]

    @staticmethod
    def fuse(
        semantic: list[KnowledgeSearchResult],
        lexical: list[KnowledgeSearchResult],
    ) -> list[KnowledgeSearchResult]:
        by_id: dict[UUID, KnowledgeSearchResult] = {}
        scores: dict[UUID, float] = {}
        for candidate in [*semantic, *lexical]:
            existing = by_id.get(candidate.chunk_id)
            if existing is None:
                by_id[candidate.chunk_id] = candidate
                scores[candidate.chunk_id] = 0.0
            else:
                by_id[candidate.chunk_id] = existing.model_copy(
                    update={
                        "semantic_score": (
                            existing.semantic_score
                            if existing.semantic_score is not None
                            else candidate.semantic_score
                        ),
                        "semantic_rank": (
                            existing.semantic_rank
                            if existing.semantic_rank is not None
                            else candidate.semantic_rank
                        ),
                        "lexical_score": (
                            existing.lexical_score
                            if existing.lexical_score is not None
                            else candidate.lexical_score
                        ),
                        "lexical_rank": (
                            existing.lexical_rank
                            if existing.lexical_rank is not None
                            else candidate.lexical_rank
                        ),
                    }
                )
            rank = candidate.semantic_rank or candidate.lexical_rank
            if rank is not None:
                scores[candidate.chunk_id] += 1.0 / (RRF_K + rank)

        ordered_ids = sorted(scores, key=lambda item: (-scores[item], str(item)))
        return [
            by_id[item].model_copy(
                update={"hybrid_score": scores[item], "hybrid_rank": rank}
            )
            for rank, item in enumerate(ordered_ids, start=1)
        ]

    @staticmethod
    def _from_semantic(row: KnowledgeSearchRow, rank: int) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            **row.model_dump(exclude={"score"}),
            semantic_score=row.score,
            semantic_rank=rank,
        )

    @staticmethod
    def _from_lexical(row: KnowledgeSearchRow, rank: int) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            **row.model_dump(exclude={"score"}),
            lexical_score=row.score,
            lexical_rank=rank,
        )
