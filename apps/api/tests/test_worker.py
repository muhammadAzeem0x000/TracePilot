import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.integrations.github import GitHubNotFoundError
from app.schemas.investigation import (
    InvestigationJobStatus,
    InvestigationStage,
    InvestigationStatus,
)
from app.services.investigation_errors import (
    PermanentInvestigationError,
    RetryableInvestigationError,
)
from app.services.worker import InvestigationWorker
from tests.test_investigations import (
    FailingLLM,
    FakeGitHubClient,
    MemoryInvestigationRepository,
    MemoryJobRepository,
    ToolThenConclusionLLM,
    make_incident,
    make_service,
)


class StubExecutionService:
    def __init__(
        self,
        investigations: MemoryInvestigationRepository,
        outcomes: list[Exception | None],
    ) -> None:
        self.investigations = investigations
        self.outcomes = outcomes
        self.executed: list[UUID] = []
        self.retry_scheduled: list[UUID] = []
        self.failed: list[UUID] = []

    async def execute(
        self,
        investigation_id: UUID,
        _job_id: UUID | None = None,
        _queued_at: datetime | None = None,
    ) -> object:
        self.executed.append(investigation_id)
        outcome = self.outcomes.pop(0)
        if outcome is not None:
            raise outcome
        return object()

    async def mark_retry_scheduled(self, investigation_id: UUID) -> object:
        self.retry_scheduled.append(investigation_id)
        return await self.investigations.update_progress(
            investigation_id,
            InvestigationStatus.PENDING,
            InvestigationStage.RETRY_SCHEDULED,
        )

    async def mark_failed(self, investigation_id: UUID, error_message: str) -> object:
        self.failed.append(investigation_id)
        return await self.investigations.fail(investigation_id, error_message)


async def _await_value[T](awaitable: Awaitable[T]) -> T:
    return await awaitable


def run_async[T](awaitable: Awaitable[T]) -> T:
    return asyncio.run(_await_value(awaitable))


async def enqueue(
    jobs: MemoryJobRepository,
    *,
    max_attempts: int = 3,
) -> UUID:
    accepted = await jobs.enqueue(
        UUID("10000000-0000-0000-0000-000000000001"),
        "investigation_v1",
        "test-model",
        max_attempts,
    )
    return accepted.investigation_id


def make_worker(
    jobs: MemoryJobRepository,
    service: StubExecutionService,
    *,
    now: datetime | None = None,
) -> InvestigationWorker:
    fixed_now = now or datetime.now(UTC)
    return InvestigationWorker(
        jobs,
        service,
        lease_seconds=60,
        poll_seconds=0.01,
        retry_base_seconds=5,
        now=lambda: fixed_now,
    )


def test_atomic_claim_allows_only_one_of_two_workers_to_claim() -> None:
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    run_async(enqueue(jobs))

    async def claim_twice() -> list[object]:
        return list(await asyncio.gather(jobs.claim(60), jobs.claim(60)))

    claims = run_async(claim_twice())

    assert sum(item is not None for item in claims) == 1


def test_expired_lease_is_reclaimed_and_attempt_increments() -> None:
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    run_async(enqueue(jobs))
    first = run_async(jobs.claim(60))
    assert first is not None
    jobs.items[first.id] = first.model_copy(
        update={"lease_expires_at": datetime.now(UTC) - timedelta(seconds=1)}
    )

    reclaimed = run_async(jobs.claim(60))

    assert reclaimed is not None
    assert reclaimed.id == first.id
    assert reclaimed.attempt_count == 2
    assert reclaimed.reclaimed_stale_lease is True


def test_successful_job_completes() -> None:
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    run_async(enqueue(jobs))
    service = StubExecutionService(investigations, [None])

    assert run_async(make_worker(jobs, service).run_once()) is True

    stored = next(iter(jobs.items.values()))
    assert stored.status is InvestigationJobStatus.COMPLETED
    assert stored.attempt_count == 1


def test_retryable_failure_schedules_exponential_backoff_then_succeeds() -> None:
    now = datetime.now(UTC)
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    investigation_id = run_async(enqueue(jobs, max_attempts=3))
    service = StubExecutionService(
        investigations,
        [RetryableInvestigationError("temporary provider failure"), None],
    )
    worker = make_worker(jobs, service, now=now)

    run_async(worker.run_once())
    scheduled = next(iter(jobs.items.values()))
    assert scheduled.status is InvestigationJobStatus.RETRY_SCHEDULED
    assert scheduled.attempt_count == 1
    assert scheduled.next_attempt_at == now + timedelta(seconds=5)
    assert service.retry_scheduled == [investigation_id]

    jobs.items[scheduled.id] = scheduled.model_copy(
        update={"next_attempt_at": datetime.now(UTC) - timedelta(seconds=1)}
    )
    run_async(worker.run_once())

    completed = jobs.items[scheduled.id]
    assert completed.status is InvestigationJobStatus.COMPLETED
    assert completed.attempt_count == 2


def test_permanent_failure_does_not_retry() -> None:
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    investigation_id = run_async(enqueue(jobs))
    service = StubExecutionService(
        investigations,
        [PermanentInvestigationError("invalid tool arguments")],
    )

    run_async(make_worker(jobs, service).run_once())

    stored = next(iter(jobs.items.values()))
    assert stored.status is InvestigationJobStatus.FAILED
    assert stored.attempt_count == 1
    assert service.retry_scheduled == []
    assert service.failed == [investigation_id]


def test_maximum_attempts_are_enforced() -> None:
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    investigation_id = run_async(enqueue(jobs, max_attempts=1))
    service = StubExecutionService(
        investigations,
        [RetryableInvestigationError("provider unavailable")],
    )

    run_async(make_worker(jobs, service).run_once())

    stored = next(iter(jobs.items.values()))
    assert stored.status is InvestigationJobStatus.FAILED
    assert stored.attempt_count == 1
    assert service.failed == [investigation_id]


def test_worker_processes_a_new_job_after_one_permanent_failure() -> None:
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    first_id = run_async(enqueue(jobs))
    service = StubExecutionService(
        investigations,
        [PermanentInvestigationError("bad request"), None],
    )
    worker = make_worker(jobs, service)
    run_async(worker.run_once())

    second_id = run_async(enqueue(jobs))
    run_async(worker.run_once())

    assert first_id != second_id
    statuses = {job.investigation_id: job.status for job in jobs.items.values()}
    assert statuses[first_id] is InvestigationJobStatus.FAILED
    assert statuses[second_id] is InvestigationJobStatus.COMPLETED


def test_real_service_classifies_llm_unavailability_as_retryable() -> None:
    incident = make_incident()
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    service, _evidence, _ = make_service(
        incident,
        FailingLLM(),
        investigations=investigations,
        jobs=jobs,
    )
    run_async(service.enqueue(incident.id))

    run_async(
        InvestigationWorker(
            jobs,
            service,
            lease_seconds=60,
            poll_seconds=0.01,
            retry_base_seconds=5,
        ).run_once()
    )

    stored = next(iter(jobs.items.values()))
    assert stored.status is InvestigationJobStatus.RETRY_SCHEDULED
    assert investigations.items[stored.investigation_id].stage is InvestigationStage.RETRY_SCHEDULED


def test_real_service_classifies_github_404_as_permanent() -> None:
    incident = make_incident()
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    service, _evidence, _ = make_service(
        incident,
        ToolThenConclusionLLM(),
        github=FakeGitHubClient(GitHubNotFoundError("missing")),
        investigations=investigations,
        jobs=jobs,
    )
    run_async(service.enqueue(incident.id))

    run_async(
        InvestigationWorker(
            jobs,
            service,
            lease_seconds=60,
            poll_seconds=0.01,
            retry_base_seconds=5,
        ).run_once()
    )

    stored = next(iter(jobs.items.values()))
    assert stored.status is InvestigationJobStatus.FAILED
    assert investigations.items[stored.investigation_id].status is InvestigationStatus.FAILED
