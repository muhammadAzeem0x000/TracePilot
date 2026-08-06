from app.ai.embeddings import (
    EmbeddingAuthenticationError,
    EmbeddingDimensionError,
    EmbeddingRateLimitError,
    EmbeddingUnavailableError,
)
from app.ai.provider import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMUnavailableError,
)
from app.integrations.github import (
    GitHubAuthenticationError,
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubResponseError,
    GitHubUnavailableError,
)
from app.repositories.incidents import RepositoryError
from app.tools.github import MalformedToolArgumentsError, UnknownToolError


class InvalidModelOutputError(Exception):
    pass


class EvidenceReferenceValidationError(Exception):
    pass


class ToolCallLimitError(Exception):
    pass


class InvestigationFailure(Exception):
    """A safe, classified workflow failure suitable for durable job state."""


class RetryableInvestigationError(InvestigationFailure):
    pass


class PermanentInvestigationError(InvestigationFailure):
    pass


RETRYABLE_FAILURES = (
    LLMRateLimitError,
    LLMUnavailableError,
    GitHubRateLimitError,
    GitHubUnavailableError,
    EmbeddingRateLimitError,
    EmbeddingUnavailableError,
    RepositoryError,
)

PERMANENT_FAILURES = (
    LLMAuthenticationError,
    GitHubAuthenticationError,
    GitHubPermissionError,
    GitHubNotFoundError,
    GitHubResponseError,
    EmbeddingAuthenticationError,
    EmbeddingDimensionError,
    UnknownToolError,
    MalformedToolArgumentsError,
    InvalidModelOutputError,
    EvidenceReferenceValidationError,
    ToolCallLimitError,
    ValueError,
)


def classify_investigation_error(error: Exception) -> InvestigationFailure:
    if isinstance(error, InvestigationFailure):
        return error
    if isinstance(error, RETRYABLE_FAILURES):
        return RetryableInvestigationError(_safe_detail(error))
    if isinstance(error, PERMANENT_FAILURES):
        return PermanentInvestigationError(_safe_detail(error))
    return PermanentInvestigationError(f"Unhandled {type(error).__name__} stopped investigation")


def _safe_detail(error: Exception) -> str:
    if isinstance(error, (InvalidModelOutputError, ToolCallLimitError)):
        return str(error)
    return f"{type(error).__name__} stopped investigation"
