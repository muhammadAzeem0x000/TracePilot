from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.db.supabase import StorageError, SupabaseRestClient
from app.repositories.incidents import RepositoryError
from app.schemas.knowledge import (
    EmbeddedKnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSearchRow,
    KnowledgeSourceResponse,
)


class KnowledgeRepository(Protocol):
    async def get_source(
        self,
        repository_full_name: str,
        source_reference: str,
    ) -> KnowledgeSourceResponse | None: ...

    async def replace_source(
        self,
        document: KnowledgeDocument,
        content_hash: str,
        chunks: list[EmbeddedKnowledgeChunk],
    ) -> KnowledgeSourceResponse: ...

    async def list_sources(self, repository_full_name: str) -> list[KnowledgeSourceResponse]: ...

    async def count_chunks(self, source_id: UUID) -> int: ...


class KnowledgeSearchRepository(Protocol):
    async def semantic_search(
        self,
        repository_full_name: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[KnowledgeSearchRow]: ...

    async def lexical_search(
        self,
        repository_full_name: str,
        query: str,
        limit: int,
    ) -> list[KnowledgeSearchRow]: ...


class SupabaseKnowledgeRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    async def get_source(
        self,
        repository_full_name: str,
        source_reference: str,
    ) -> KnowledgeSourceResponse | None:
        try:
            records = await self._client.request(
                "GET",
                "/knowledge_sources",
                params={
                    "select": "*",
                    "repository_full_name": f"eq.{repository_full_name}",
                    "source_reference": f"eq.{source_reference}",
                    "limit": "1",
                },
            )
            return KnowledgeSourceResponse.model_validate(records[0]) if records else None
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to retrieve knowledge source") from exc

    async def replace_source(
        self,
        document: KnowledgeDocument,
        content_hash: str,
        chunks: list[EmbeddedKnowledgeChunk],
    ) -> KnowledgeSourceResponse:
        payload: dict[str, object] = {
            "p_repository_full_name": document.repository_full_name,
            "p_source_type": document.source_type.value,
            "p_title": document.title,
            "p_source_reference": document.source_reference,
            "p_content_hash": content_hash,
            "p_metadata": document.metadata,
            "p_chunks": [chunk.model_dump(mode="json") for chunk in chunks],
        }
        try:
            records = await self._client.request(
                "POST",
                "/rpc/replace_knowledge_source",
                json_body=payload,
            )
            if len(records) != 1 or "source_id" not in records[0]:
                raise RepositoryError("Knowledge replacement returned no source")
            source_id = UUID(str(records[0]["source_id"]))
            stored = await self._get_source_by_id(source_id)
            if stored is None:
                raise RepositoryError("Knowledge replacement could not be reloaded")
            return stored
        except (StorageError, ValidationError, ValueError) as exc:
            raise RepositoryError("Unable to replace knowledge source") from exc

    async def list_sources(self, repository_full_name: str) -> list[KnowledgeSourceResponse]:
        try:
            records = await self._client.request(
                "GET",
                "/knowledge_sources",
                params={
                    "select": "*",
                    "repository_full_name": f"eq.{repository_full_name}",
                    "order": "source_reference.asc",
                },
            )
            return [KnowledgeSourceResponse.model_validate(record) for record in records]
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to list knowledge sources") from exc

    async def count_chunks(self, source_id: UUID) -> int:
        try:
            records = await self._client.request(
                "GET",
                "/knowledge_chunks",
                params={"select": "id", "source_id": f"eq.{source_id}"},
            )
            return len(records)
        except StorageError as exc:
            raise RepositoryError("Unable to count knowledge chunks") from exc

    async def semantic_search(
        self,
        repository_full_name: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[KnowledgeSearchRow]:
        return await self._search_rpc(
            "/rpc/search_knowledge_semantic",
            {
                "query_embedding": query_embedding,
                "filter_repository": repository_full_name,
                "match_count": limit,
            },
            "Unable to perform semantic knowledge search",
        )

    async def lexical_search(
        self,
        repository_full_name: str,
        query: str,
        limit: int,
    ) -> list[KnowledgeSearchRow]:
        return await self._search_rpc(
            "/rpc/search_knowledge_lexical",
            {
                "query_text": query,
                "filter_repository": repository_full_name,
                "match_count": limit,
            },
            "Unable to perform lexical knowledge search",
        )

    async def _get_source_by_id(self, source_id: UUID) -> KnowledgeSourceResponse | None:
        records = await self._client.request(
            "GET",
            "/knowledge_sources",
            params={"select": "*", "id": f"eq.{source_id}", "limit": "1"},
        )
        return KnowledgeSourceResponse.model_validate(records[0]) if records else None

    async def _search_rpc(
        self,
        path: str,
        payload: dict[str, object],
        error_message: str,
    ) -> list[KnowledgeSearchRow]:
        try:
            records = await self._client.request("POST", path, json_body=payload)
            return [KnowledgeSearchRow.model_validate(record) for record in records]
        except (StorageError, ValidationError) as exc:
            raise RepositoryError(error_message) from exc
