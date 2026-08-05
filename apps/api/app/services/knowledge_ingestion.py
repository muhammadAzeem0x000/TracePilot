import hashlib

from app.ai.embeddings import EmbeddingDimensionError, EmbeddingProvider, EmbeddingTask
from app.knowledge.chunking import DeterministicChunker
from app.repositories.knowledge import KnowledgeRepository
from app.schemas.knowledge import (
    EmbeddedKnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionAction,
    KnowledgeIngestionResult,
)


class EmptyKnowledgeDocumentError(Exception):
    pass


class KnowledgeIngestionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider,
        chunker: DeterministicChunker,
    ) -> None:
        self._repository = repository
        self._embeddings = embedding_provider
        self._chunker = chunker

    async def ingest(self, document: KnowledgeDocument) -> KnowledgeIngestionResult:
        normalized_content = document.content.replace("\r\n", "\n").strip()
        if not normalized_content:
            raise EmptyKnowledgeDocumentError("Knowledge document content is empty")
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
        existing = await self._repository.get_source(
            document.repository_full_name,
            document.source_reference,
        )
        if existing is not None and existing.content_hash == content_hash:
            return KnowledgeIngestionResult(
                source_id=existing.id,
                source_reference=existing.source_reference,
                action=KnowledgeIngestionAction.SKIPPED,
                chunk_count=await self._repository.count_chunks(existing.id),
            )

        chunks = self._chunker.chunk(normalized_content)
        if not chunks:
            raise EmptyKnowledgeDocumentError("Knowledge document produced no chunks")
        vectors = await self._embeddings.embed(
            [chunk.content for chunk in chunks],
            task=EmbeddingTask.DOCUMENT,
        )
        if len(vectors) != len(chunks):
            raise EmbeddingDimensionError("Embedding count does not match chunk count")

        embedded_chunks: list[EmbeddedKnowledgeChunk] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            if len(vector) != self._embeddings.dimensions:
                raise EmbeddingDimensionError(
                    f"Embedding has {len(vector)} dimensions; "
                    f"expected {self._embeddings.dimensions}"
                )
            embedded_chunks.append(
                EmbeddedKnowledgeChunk(
                    **chunk.model_dump(exclude={"metadata"}),
                    embedding=vector,
                    metadata={
                        **chunk.metadata,
                        "embedding_model": self._embeddings.model_name,
                        "embedding_dimensions": self._embeddings.dimensions,
                    },
                )
            )

        stored = await self._repository.replace_source(
            document.model_copy(update={"content": normalized_content}),
            content_hash,
            embedded_chunks,
        )
        return KnowledgeIngestionResult(
            source_id=stored.id,
            source_reference=stored.source_reference,
            action=(
                KnowledgeIngestionAction.CREATED
                if existing is None
                else KnowledgeIngestionAction.UPDATED
            ),
            chunk_count=len(embedded_chunks),
        )

    async def ingest_many(
        self,
        documents: list[KnowledgeDocument],
    ) -> list[KnowledgeIngestionResult]:
        results: list[KnowledgeIngestionResult] = []
        for document in documents:
            results.append(await self.ingest(document))
        return results
