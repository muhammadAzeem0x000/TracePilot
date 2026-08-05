import math
from enum import StrEnum
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class EmbeddingTask(StrEnum):
    DOCUMENT = "RETRIEVAL_DOCUMENT"
    QUERY = "RETRIEVAL_QUERY"


class EmbeddingProviderError(Exception):
    """Safe embedding-provider failure without raw payloads or credentials."""


class EmbeddingAuthenticationError(EmbeddingProviderError):
    pass


class EmbeddingRateLimitError(EmbeddingProviderError):
    pass


class EmbeddingUnavailableError(EmbeddingProviderError):
    pass


class EmbeddingDimensionError(EmbeddingProviderError):
    pass


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed(
        self,
        texts: list[str],
        *,
        task: EmbeddingTask,
    ) -> list[list[float]]: ...


class _GeminiEmbedding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    values: list[float]


class _GeminiBatchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    embeddings: list[_GeminiEmbedding] = Field(default_factory=list)


class GeminiEmbeddingProvider:
    """Gemini batch embedding client with strict output-dimension validation."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(
        self,
        texts: list[str],
        *,
        task: EmbeddingTask,
    ) -> list[list[float]]:
        if not texts:
            raise ValueError("At least one non-empty text is required for embedding")
        if any(not text.strip() for text in texts):
            raise ValueError("Embedding input cannot contain empty text")

        model_path = f"models/{self._model}"
        requests = [
            {
                "model": model_path,
                "content": {"parts": [{"text": text}]},
                "taskType": task.value,
                "outputDimensionality": self._dimensions,
            }
            for text in texts
        ]
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=45.0) as client:
                response = await client.post(
                    f"/v1beta/{model_path}:batchEmbedContents",
                    headers={
                        "x-goog-api-key": self._api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json={"requests": requests},
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise EmbeddingUnavailableError("Embedding provider is unavailable") from exc

        if response.status_code in {401, 403}:
            raise EmbeddingAuthenticationError("Embedding provider rejected the API key")
        if response.status_code == 429:
            raise EmbeddingRateLimitError("Embedding provider rate limit exceeded")
        if response.status_code >= 400:
            raise EmbeddingUnavailableError(
                f"Embedding provider request failed with status {response.status_code}"
            )

        try:
            parsed = _GeminiBatchResponse.model_validate_json(response.text)
        except ValidationError as exc:
            raise EmbeddingUnavailableError(
                "Embedding provider returned an invalid response"
            ) from exc
        if len(parsed.embeddings) != len(texts):
            raise EmbeddingUnavailableError("Embedding provider returned the wrong result count")
        return [self._validate_and_normalize(item.values) for item in parsed.embeddings]

    def _validate_and_normalize(self, values: list[float]) -> list[float]:
        if len(values) != self._dimensions:
            raise EmbeddingDimensionError(
                f"Embedding has {len(values)} dimensions; expected {self._dimensions}"
            )
        if any(not math.isfinite(value) for value in values):
            raise EmbeddingDimensionError("Embedding contains a non-finite value")
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            raise EmbeddingDimensionError("Embedding has zero magnitude")
        return [value / norm for value in values]
