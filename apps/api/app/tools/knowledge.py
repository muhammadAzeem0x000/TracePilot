import json

from pydantic import ValidationError

from app.repositories.evidence import EvidenceRepository
from app.retrieval.service import KnowledgeRetrievalService
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceSourceType
from app.schemas.knowledge import KnowledgeSearchMode, SearchKnowledgeArguments
from app.tools.github import MalformedToolArgumentsError, ToolExecutionContext


class KnowledgeToolExecutor:
    TOOL_NAME = "search_knowledge"

    def __init__(
        self,
        retrieval_service: KnowledgeRetrievalService,
        evidence_repository: EvidenceRepository,
    ) -> None:
        self._retrieval = retrieval_service
        self._evidence = evidence_repository

    async def execute(
        self,
        raw_arguments: str,
        context: ToolExecutionContext,
    ) -> list[EvidenceResponse]:
        try:
            raw: object = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise MalformedToolArgumentsError("Tool arguments are not valid JSON") from exc
        try:
            arguments = SearchKnowledgeArguments.model_validate(raw)
        except ValidationError as exc:
            raise MalformedToolArgumentsError("Tool arguments failed validation") from exc

        response = await self._retrieval.search(
            arguments.query,
            context.repository_full_name,
            KnowledgeSearchMode.RERANKED,
            arguments.top_k,
        )
        persisted: list[EvidenceResponse] = []
        for item in response.items:
            metadata: dict[str, str | int | float | bool | None] = {
                "tool_name": self.TOOL_NAME,
                "repository": context.repository_full_name,
                "knowledge_source_type": item.source_type.value,
                "source_id": str(item.source_id),
                "chunk_id": str(item.chunk_id),
                "semantic_score": item.semantic_score,
                "semantic_rank": item.semantic_rank,
                "lexical_score": item.lexical_score,
                "lexical_rank": item.lexical_rank,
                "hybrid_score": item.hybrid_score,
                "hybrid_rank": item.hybrid_rank,
                "rerank_rank": item.rerank_rank,
                "rerank_fallback": response.rerank_fallback,
                "query": response.query,
            }
            evidence = EvidenceCreate(
                incident_id=context.incident_id,
                investigation_id=context.investigation_id,
                source_type=EvidenceSourceType.KNOWLEDGE_CHUNK,
                source_reference=f"{item.source_reference}#chunk-{item.chunk_id}",
                content=json.dumps(
                    {
                        "title": item.title,
                        "source_type": item.source_type.value,
                        "source_reference": item.source_reference,
                        "chunk_id": str(item.chunk_id),
                        "content": item.content,
                    },
                    separators=(",", ":"),
                ),
                metadata=metadata,
            )
            persisted.append(await self._evidence.create(evidence))
        return persisted
