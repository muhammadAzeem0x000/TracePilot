import asyncio
import json
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.ai.embeddings import (
    EmbeddingDimensionError,
    EmbeddingProviderError,
    EmbeddingTask,
    EmbeddingUnavailableError,
)
from app.ai.provider import LLMUnavailableError
from app.ai.tool_definitions import INVESTIGATION_TOOL_DEFINITIONS
from app.knowledge.chunking import DeterministicChunker
from app.retrieval.context import ContextAssembler
from app.retrieval.reranking import KnowledgeReranker, RerankingValidationError
from app.retrieval.service import KnowledgeRetrievalService
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceSourceType
from app.schemas.knowledge import (
    EmbeddedKnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionAction,
    KnowledgeSearchMode,
    KnowledgeSearchResult,
    KnowledgeSearchRow,
    KnowledgeSourceResponse,
    KnowledgeSourceType,
    RerankResult,
)
from app.schemas.llm import ChatMessage, ModelTurn, ToolDefinition
from app.services.knowledge_ingestion import KnowledgeIngestionService
from app.tools.github import MalformedToolArgumentsError, ToolExecutionContext
from app.tools.knowledge import KnowledgeToolExecutor

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
REPOSITORY = "example/checkout-service"


async def _await_value[T](value: Awaitable[T]) -> T:
    return await value


def run_async[T](value: Awaitable[T]) -> T:
    return asyncio.run(_await_value(value))


class FakeEmbeddingProvider:
    model_name = "test-embedding"

    def __init__(
        self,
        dimensions: int = 3,
        *,
        failure: EmbeddingProviderError | None = None,
        returned_dimensions: int | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.failure = failure
        self.returned_dimensions = returned_dimensions or dimensions
        self.calls: list[tuple[list[str], EmbeddingTask]] = []

    async def embed(
        self,
        texts: list[str],
        *,
        task: EmbeddingTask,
    ) -> list[list[float]]:
        self.calls.append((texts, task))
        if self.failure is not None:
            raise self.failure
        return [[1.0] * self.returned_dimensions for _ in texts]


class MemoryKnowledgeRepository:
    def __init__(self) -> None:
        self.sources: dict[tuple[str, str], KnowledgeSourceResponse] = {}
        self.chunks: dict[UUID, list[EmbeddedKnowledgeChunk]] = {}
        self.replacements = 0

    async def get_source(
        self,
        repository_full_name: str,
        source_reference: str,
    ) -> KnowledgeSourceResponse | None:
        return self.sources.get((repository_full_name, source_reference))

    async def replace_source(
        self,
        document: KnowledgeDocument,
        content_hash: str,
        chunks: list[EmbeddedKnowledgeChunk],
    ) -> KnowledgeSourceResponse:
        self.replacements += 1
        key = (document.repository_full_name, document.source_reference)
        existing = self.sources.get(key)
        source = KnowledgeSourceResponse(
            id=existing.id if existing else uuid4(),
            repository_full_name=document.repository_full_name,
            source_type=document.source_type,
            title=document.title,
            source_reference=document.source_reference,
            content_hash=content_hash,
            metadata=document.metadata,
            created_at=existing.created_at if existing else NOW,
            updated_at=NOW,
        )
        self.sources[key] = source
        self.chunks[source.id] = chunks
        return source

    async def list_sources(
        self,
        repository_full_name: str,
    ) -> list[KnowledgeSourceResponse]:
        return [
            source
            for (repository, _), source in self.sources.items()
            if repository == repository_full_name
        ]

    async def count_chunks(self, source_id: UUID) -> int:
        return len(self.chunks.get(source_id, []))


class FakeSearchRepository:
    def __init__(
        self,
        semantic: list[KnowledgeSearchRow] | None = None,
        lexical: list[KnowledgeSearchRow] | None = None,
    ) -> None:
        self.semantic = semantic or []
        self.lexical = lexical or []
        self.semantic_calls: list[tuple[str, list[float], int]] = []
        self.lexical_calls: list[tuple[str, str, int]] = []

    async def semantic_search(
        self,
        repository_full_name: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[KnowledgeSearchRow]:
        self.semantic_calls.append((repository_full_name, query_embedding, limit))
        return self.semantic

    async def lexical_search(
        self,
        repository_full_name: str,
        query: str,
        limit: int,
    ) -> list[KnowledgeSearchRow]:
        self.lexical_calls.append((repository_full_name, query, limit))
        return self.lexical


class MemoryEvidenceRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, EvidenceResponse] = {}

    async def create(self, evidence: EvidenceCreate) -> EvidenceResponse:
        stored = EvidenceResponse(
            id=uuid4(),
            **evidence.model_dump(),
            collected_at=NOW,
        )
        self.items[stored.id] = stored
        return stored

    async def list_for_incident(self, incident_id: UUID) -> list[EvidenceResponse]:
        return [item for item in self.items.values() if item.incident_id == incident_id]

    async def list_for_investigation(self, investigation_id: UUID) -> list[EvidenceResponse]:
        return [item for item in self.items.values() if item.investigation_id == investigation_id]

    async def ids_for_context(
        self,
        incident_id: UUID,
        investigation_id: UUID,
        evidence_ids: set[UUID],
    ) -> set[UUID]:
        return {
            evidence_id
            for evidence_id in evidence_ids
            if (item := self.items.get(evidence_id)) is not None
            and item.incident_id == incident_id
            and item.investigation_id == investigation_id
        }


class StaticRerankLLM:
    model_name = "test-reranker"

    def __init__(self, content: str | None = None, *, fail: bool = False) -> None:
        self.content = content
        self.fail = fail

    async def complete(
        self,
        _messages: list[ChatMessage],
        _tools: list[ToolDefinition],
    ) -> ModelTurn:
        if self.fail:
            raise LLMUnavailableError("reranker unavailable")
        return ModelTurn(content=self.content)


def make_document(
    content: str = "Rollback the deployment when checkout errors spike.",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        repository_full_name=REPOSITORY,
        source_type=KnowledgeSourceType.RUNBOOK,
        title="Deployment rollback",
        source_reference="knowledge/runbooks/deployment-rollback.md",
        content=content,
        metadata={"owner": "platform"},
    )


def make_row(
    *,
    chunk_id: UUID | None = None,
    score: float = 0.8,
    content: str = "Rollback the checkout deployment.",
    token_count: int = 5,
) -> KnowledgeSearchRow:
    return KnowledgeSearchRow(
        chunk_id=chunk_id or uuid4(),
        source_id=uuid4(),
        source_type=KnowledgeSourceType.RUNBOOK,
        source_reference="knowledge/runbooks/deployment-rollback.md",
        title="Deployment rollback",
        content=content,
        token_count=token_count,
        metadata={"owner": "platform"},
        score=score,
    )


def from_row(
    row: KnowledgeSearchRow,
    *,
    semantic_rank: int | None = None,
    lexical_rank: int | None = None,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        **row.model_dump(exclude={"score"}),
        semantic_score=row.score if semantic_rank is not None else None,
        semantic_rank=semantic_rank,
        lexical_score=row.score if lexical_rank is not None else None,
        lexical_rank=lexical_rank,
    )


def make_ingestion_service(
    repository: MemoryKnowledgeRepository,
    embeddings: FakeEmbeddingProvider,
) -> KnowledgeIngestionService:
    return KnowledgeIngestionService(
        repository,
        embeddings,
        DeterministicChunker(max_tokens=12, overlap_tokens=2),
    )


def test_ingestion_creates_source_and_chunks() -> None:
    repository = MemoryKnowledgeRepository()
    embeddings = FakeEmbeddingProvider()

    result = run_async(make_ingestion_service(repository, embeddings).ingest(make_document()))

    assert result.action is KnowledgeIngestionAction.CREATED
    assert result.chunk_count > 0
    assert repository.replacements == 1
    assert embeddings.calls[0][1] is EmbeddingTask.DOCUMENT
    assert all(len(chunk.embedding) == 3 for chunk in repository.chunks[result.source_id])


def test_unchanged_ingestion_skips_embedding_regeneration() -> None:
    repository = MemoryKnowledgeRepository()
    embeddings = FakeEmbeddingProvider()
    service = make_ingestion_service(repository, embeddings)
    document = make_document()

    first = run_async(service.ingest(document))
    second = run_async(service.ingest(document))

    assert first.source_id == second.source_id
    assert second.action is KnowledgeIngestionAction.SKIPPED
    assert repository.replacements == 1
    assert len(embeddings.calls) == 1


def test_changed_document_reindexes_same_source() -> None:
    repository = MemoryKnowledgeRepository()
    embeddings = FakeEmbeddingProvider()
    service = make_ingestion_service(repository, embeddings)

    first = run_async(service.ingest(make_document()))
    second = run_async(service.ingest(make_document("Use the rollback checklist immediately.")))

    assert second.action is KnowledgeIngestionAction.UPDATED
    assert second.source_id == first.source_id
    assert repository.replacements == 2
    assert len(embeddings.calls) == 2


def test_chunking_is_deterministic_bounded_and_never_empty() -> None:
    chunker = DeterministicChunker(max_tokens=10, overlap_tokens=2)
    content = (
        "Checkout failures increased after the database migration. "
        "The payment status column was missing.\n\n"
        "Rollback the deployment and verify the schema before restoring traffic."
    )

    first = chunker.chunk(content)
    second = chunker.chunk(content)

    assert first == second
    assert [chunk.chunk_index for chunk in first] == list(range(len(first)))
    assert all(chunk.content.strip() for chunk in first)
    assert all(0 < chunk.token_count <= 10 for chunk in first)


def test_embedding_dimension_mismatch_prevents_storage() -> None:
    repository = MemoryKnowledgeRepository()
    embeddings = FakeEmbeddingProvider(dimensions=3, returned_dimensions=2)

    with pytest.raises(EmbeddingDimensionError):
        run_async(make_ingestion_service(repository, embeddings).ingest(make_document()))

    assert repository.replacements == 0


def test_embedding_provider_failure_prevents_storage() -> None:
    repository = MemoryKnowledgeRepository()
    embeddings = FakeEmbeddingProvider(
        failure=EmbeddingUnavailableError("provider unavailable")
    )

    with pytest.raises(EmbeddingUnavailableError):
        run_async(make_ingestion_service(repository, embeddings).ingest(make_document()))

    assert repository.replacements == 0


def test_semantic_search_is_repository_scoped_and_uses_query_embedding() -> None:
    search_repository = FakeSearchRepository(semantic=[make_row()])
    embeddings = FakeEmbeddingProvider()
    service = KnowledgeRetrievalService(
        search_repository,
        embeddings,
        ContextAssembler(100),
        candidate_limit=7,
    )

    response = run_async(
        service.search("checkout error", REPOSITORY, KnowledgeSearchMode.SEMANTIC, 3)
    )

    assert response.count == 1
    assert embeddings.calls == [(["checkout error"], EmbeddingTask.QUERY)]
    assert search_repository.semantic_calls == [(REPOSITORY, [1.0, 1.0, 1.0], 7)]
    assert search_repository.lexical_calls == []


def test_hybrid_search_scopes_semantic_and_lexical_queries() -> None:
    search_repository = FakeSearchRepository(semantic=[make_row()], lexical=[make_row()])
    service = KnowledgeRetrievalService(
        search_repository,
        FakeEmbeddingProvider(),
        ContextAssembler(100),
        candidate_limit=4,
    )

    run_async(service.search("missing column", REPOSITORY, KnowledgeSearchMode.HYBRID, 2))

    assert search_repository.semantic_calls[0][0] == REPOSITORY
    assert search_repository.lexical_calls == [(REPOSITORY, "missing column", 4)]


def test_rrf_fuses_duplicates_and_rewards_results_in_both_lists() -> None:
    shared = make_row(chunk_id=uuid4(), score=0.0)
    semantic_only = make_row(chunk_id=uuid4(), score=0.9)
    lexical_only = make_row(chunk_id=uuid4(), score=0.7)
    semantic = [from_row(shared, semantic_rank=1), from_row(semantic_only, semantic_rank=2)]
    lexical = [from_row(shared, lexical_rank=1), from_row(lexical_only, lexical_rank=2)]

    fused = KnowledgeRetrievalService.fuse(semantic, lexical)

    assert len(fused) == 3
    assert fused[0].chunk_id == shared.chunk_id
    assert fused[0].semantic_score == 0.0
    assert fused[0].lexical_score == 0.0
    assert fused[0].semantic_rank == 1
    assert fused[0].lexical_rank == 1


def test_reranker_accepts_exact_known_candidate_set() -> None:
    rows = [make_row(), make_row()]
    candidates = [from_row(row, semantic_rank=index) for index, row in enumerate(rows, start=1)]
    requested_order = [rows[1].chunk_id, rows[0].chunk_id]
    llm = StaticRerankLLM(RerankResult(ranked_candidate_ids=requested_order).model_dump_json())

    reranked = run_async(KnowledgeReranker(llm).rerank("rollback", candidates))

    assert [item.chunk_id for item in reranked] == requested_order
    assert [item.rerank_rank for item in reranked] == [1, 2]


def test_reranker_rejects_invented_candidate_id() -> None:
    row = make_row()
    candidate = from_row(row, semantic_rank=1)
    llm = StaticRerankLLM(
        RerankResult(ranked_candidate_ids=[uuid4()]).model_dump_json()
    )

    with pytest.raises(RerankingValidationError, match="every known candidate"):
        run_async(KnowledgeReranker(llm).rerank("rollback", [candidate]))


def test_reranker_failure_falls_back_to_rrf() -> None:
    row = make_row()
    search_repository = FakeSearchRepository(semantic=[row], lexical=[row])
    service = KnowledgeRetrievalService(
        search_repository,
        FakeEmbeddingProvider(),
        ContextAssembler(100),
        reranker=KnowledgeReranker(StaticRerankLLM(fail=True)),
    )

    response = run_async(service.search("rollback", REPOSITORY, KnowledgeSearchMode.RERANKED, 1))

    assert response.rerank_fallback is True
    assert response.items[0].hybrid_rank == 1
    assert response.items[0].rerank_rank is None


def test_context_assembler_enforces_budget_and_deduplicates() -> None:
    first = from_row(make_row(token_count=6), semantic_rank=1)
    duplicate = first.model_copy(update={"semantic_rank": 2})
    too_large = from_row(make_row(token_count=7), semantic_rank=3)
    fitting = from_row(make_row(token_count=4), semantic_rank=4)

    selected, tokens = ContextAssembler(10).select(
        [first, duplicate, too_large, fitting],
        top_k=4,
    )

    assert [item.chunk_id for item in selected] == [first.chunk_id, fitting.chunk_id]
    assert tokens == 10


def test_search_knowledge_is_the_only_non_github_allowlisted_tool() -> None:
    tool_names = [definition.function.name for definition in INVESTIGATION_TOOL_DEFINITIONS]

    assert tool_names.count("search_knowledge") == 1
    assert "shell" not in tool_names
    assert "http_request" not in tool_names


@pytest.mark.parametrize(
    "arguments",
    [
        "not-json",
        "[]",
        '{"query":"ok"}',
        '{"query":"find rollback","repository":"attacker/selected"}',
        '{"query":"find rollback","top_k":20}',
    ],
)
def test_search_knowledge_rejects_malformed_or_repository_arguments(arguments: str) -> None:
    executor = KnowledgeToolExecutor(
        KnowledgeRetrievalService(
            FakeSearchRepository(),
            FakeEmbeddingProvider(),
            ContextAssembler(100),
        ),
        MemoryEvidenceRepository(),
    )
    context = ToolExecutionContext(uuid4(), uuid4(), REPOSITORY)

    with pytest.raises(MalformedToolArgumentsError):
        run_async(executor.execute(arguments, context))


def test_retrieved_knowledge_is_persisted_as_incident_investigation_evidence() -> None:
    row = make_row(content="Use the verified rollback procedure.")
    search_repository = FakeSearchRepository(semantic=[row], lexical=[row])
    evidence = MemoryEvidenceRepository()
    executor = KnowledgeToolExecutor(
        KnowledgeRetrievalService(
            search_repository,
            FakeEmbeddingProvider(),
            ContextAssembler(100),
        ),
        evidence,
    )
    context = ToolExecutionContext(uuid4(), uuid4(), REPOSITORY)

    persisted = run_async(
        executor.execute('{"query":"checkout rollback","top_k":1}', context)
    )

    assert len(persisted) == 1
    stored = persisted[0]
    assert stored.source_type is EvidenceSourceType.KNOWLEDGE_CHUNK
    assert stored.incident_id == context.incident_id
    assert stored.investigation_id == context.investigation_id
    assert stored.metadata["repository"] == REPOSITORY
    assert stored.metadata["chunk_id"] == str(row.chunk_id)
    assert json.loads(stored.content)["content"] == row.content


def test_rerank_result_rejects_empty_candidate_list() -> None:
    with pytest.raises(ValidationError):
        RerankResult(ranked_candidate_ids=[])


def test_replacement_migration_qualifies_source_id_column() -> None:
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "202608060002_day3_fix_knowledge_replacement.sql"
    ).read_text(encoding="utf-8")

    assert "delete from public.knowledge_chunks as knowledge_chunk" in migration
    assert "where knowledge_chunk.source_id = stored_source_id" in migration
