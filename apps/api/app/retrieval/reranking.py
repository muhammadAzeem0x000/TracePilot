from pydantic import ValidationError

from app.ai.prompts.rerank_v1 import SYSTEM_PROMPT, build_rerank_prompt
from app.ai.provider import LLMProvider
from app.schemas.knowledge import KnowledgeSearchResult, RerankResult
from app.schemas.llm import ChatMessage


class RerankingValidationError(Exception):
    pass


class KnowledgeReranker:
    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    async def rerank(
        self,
        query: str,
        candidates: list[KnowledgeSearchResult],
    ) -> list[KnowledgeSearchResult]:
        if not candidates:
            return []
        turn = await self._llm.complete(
            [
                ChatMessage(role="system", content=SYSTEM_PROMPT),
                ChatMessage(role="user", content=build_rerank_prompt(query, candidates)),
            ],
            [],
        )
        if turn.content is None:
            raise RerankingValidationError("Reranker returned no structured content")
        try:
            parsed = RerankResult.model_validate_json(turn.content)
        except ValidationError as exc:
            raise RerankingValidationError("Reranker output failed validation") from exc

        expected = {candidate.chunk_id for candidate in candidates}
        returned = parsed.ranked_candidate_ids
        if len(set(returned)) != len(returned):
            raise RerankingValidationError("Reranker returned duplicate candidate IDs")
        if set(returned) != expected:
            raise RerankingValidationError("Reranker must return every known candidate ID once")

        by_id = {candidate.chunk_id: candidate for candidate in candidates}
        return [
            by_id[candidate_id].model_copy(update={"rerank_rank": rank})
            for rank, candidate_id in enumerate(returned, start=1)
        ]
