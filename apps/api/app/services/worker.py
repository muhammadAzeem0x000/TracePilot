import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.repositories.incidents import RepositoryError
from app.repositories.jobs import InvestigationJobRepository
from app.schemas.investigation import InvestigationJobResponse
from app.services.investigation_errors import (
    PermanentInvestigationError,
    RetryableInvestigationError,
)
from app.services.investigations import InvestigationService

logger = logging.getLogger(__name__)


class InvestigationWorker:
    def __init__(
        self,
        jobs: InvestigationJobRepository,
        investigations: InvestigationService,
        *,
        lease_seconds: int,
        poll_seconds: float,
        retry_base_seconds: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._jobs = jobs
        self._investigations = investigations
        self._lease_seconds = lease_seconds
        self._poll_seconds = poll_seconds
        self._retry_base_seconds = retry_base_seconds
        self._now = now or (lambda: datetime.now(UTC))
        self._stop = asyncio.Event()

    async def run_forever(self) -> None:
        logger.info("investigation_worker_started")
        while not self._stop.is_set():
            processed = await self.run_once()
            if processed:
                continue
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._poll_seconds)
            except TimeoutError:
                pass
        logger.info("investigation_worker_stopped")

    async def stop(self) -> None:
        self._stop.set()

    async def run_once(self) -> bool:
        try:
            job = await self._jobs.claim(self._lease_seconds)
        except RepositoryError:
            logger.exception("investigation_job_claim_failed")
            return False
        if job is None:
            return False

        logger.info(
            "investigation_job_claimed",
            extra={
                "job_id": str(job.id),
                "investigation_id": str(job.investigation_id),
                "attempt": job.attempt_count,
                "reclaimed_stale_lease": job.reclaimed_stale_lease,
            },
        )
        try:
            await self._investigations.execute(job.investigation_id)
            await self._jobs.complete(job.id)
            logger.info(
                "investigation_job_completed",
                extra={
                    "job_id": str(job.id),
                    "investigation_id": str(job.investigation_id),
                    "attempt": job.attempt_count,
                },
            )
        except RetryableInvestigationError as exc:
            await self._handle_retryable(job, exc)
        except PermanentInvestigationError as exc:
            await self._permanently_fail(job, str(exc))
        except RepositoryError:
            # Durable state may be temporarily unavailable. Leaving the job running lets
            # its lease expire so another worker can reclaim it safely.
            logger.exception(
                "investigation_job_state_persistence_failed",
                extra={"job_id": str(job.id), "investigation_id": str(job.investigation_id)},
            )
        except Exception as exc:
            logger.exception(
                "investigation_worker_unexpected_failure",
                extra={"job_id": str(job.id), "investigation_id": str(job.investigation_id)},
            )
            await self._permanently_fail(
                job,
                f"Unexpected {type(exc).__name__} stopped investigation",
            )
        return True

    async def _handle_retryable(
        self,
        job: InvestigationJobResponse,
        error: RetryableInvestigationError,
    ) -> None:
        if job.attempt_count >= job.max_attempts:
            await self._permanently_fail(job, f"Retry limit reached: {error}")
            return
        delay_seconds = self._retry_base_seconds * (2 ** (job.attempt_count - 1))
        next_attempt_at = self._now() + timedelta(seconds=delay_seconds)
        await self._jobs.schedule_retry(job.id, str(error), next_attempt_at)
        await self._investigations.mark_retry_scheduled(job.investigation_id)
        logger.warning(
            "investigation_retry_scheduled",
            extra={
                "job_id": str(job.id),
                "investigation_id": str(job.investigation_id),
                "attempt": job.attempt_count,
                "next_attempt_at": next_attempt_at.isoformat(),
            },
        )

    async def _permanently_fail(
        self,
        job: InvestigationJobResponse,
        error_message: str,
    ) -> None:
        await self._jobs.fail(job.id, error_message)
        await self._investigations.mark_failed(job.investigation_id, error_message)
        logger.warning(
            "investigation_job_permanently_failed",
            extra={
                "job_id": str(job.id),
                "investigation_id": str(job.investigation_id),
                "attempt": job.attempt_count,
            },
        )
