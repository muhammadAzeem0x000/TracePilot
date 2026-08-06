from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.db.supabase import StorageError, SupabaseRestClient
from app.repositories.incidents import RepositoryError
from app.schemas.investigation import (
    InvestigationReviewCreate,
    InvestigationReviewResponse,
)


class InvestigationReviewRepository(Protocol):
    async def upsert(
        self,
        investigation_id: UUID,
        review: InvestigationReviewCreate,
    ) -> InvestigationReviewResponse: ...

    async def get(self, investigation_id: UUID) -> InvestigationReviewResponse | None: ...


class SupabaseInvestigationReviewRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    async def upsert(
        self,
        investigation_id: UUID,
        review: InvestigationReviewCreate,
    ) -> InvestigationReviewResponse:
        try:
            records = await self._client.request(
                "POST",
                "/investigation_reviews",
                params={"select": "*", "on_conflict": "investigation_id"},
                json_body={
                    "investigation_id": str(investigation_id),
                    "decision": review.decision.value,
                    "note": review.note,
                },
                extra_headers={"Prefer": "resolution=merge-duplicates,return=representation"},
            )
            if len(records) != 1:
                raise RepositoryError("Investigation review upsert returned no record")
            return InvestigationReviewResponse.model_validate(records[0])
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to save investigation review") from exc

    async def get(self, investigation_id: UUID) -> InvestigationReviewResponse | None:
        try:
            records = await self._client.request(
                "GET",
                "/investigation_reviews",
                params={
                    "select": "*",
                    "investigation_id": f"eq.{investigation_id}",
                    "limit": "1",
                },
            )
            return InvestigationReviewResponse.model_validate(records[0]) if records else None
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to retrieve investigation review") from exc
