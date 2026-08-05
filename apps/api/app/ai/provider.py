from typing import Protocol

import httpx
from pydantic import ValidationError

from app.schemas.llm import (
    ChatMessage,
    ModelToolCall,
    ModelTurn,
    ProviderResponse,
    ToolDefinition,
)


class LLMProviderError(Exception):
    """Safe provider failure that does not include credentials or raw payloads."""


class LLMAuthenticationError(LLMProviderError):
    pass


class LLMRateLimitError(LLMProviderError):
    pass


class LLMUnavailableError(LLMProviderError):
    pass


class LLMProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ModelTurn: ...


class OpenAICompatibleLLMProvider:
    """Small provider boundary for OpenAI-compatible chat-completion APIs."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ModelTurn:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [self._serialize_message(message) for message in messages],
            "tools": [tool.model_dump(exclude_none=True) for tool in tools],
            "tool_choice": "auto",
            "temperature": 0.1,
            "max_tokens": 2_000,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=45.0) as client:
                response = await client.post(
                    "/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise LLMUnavailableError("LLM provider is unavailable") from exc

        if response.status_code == 401:
            raise LLMAuthenticationError("LLM provider rejected the API key")
        if response.status_code == 429:
            raise LLMRateLimitError("LLM provider rate limit exceeded")
        if response.status_code >= 400:
            raise LLMUnavailableError(
                f"LLM provider request failed with status {response.status_code}"
            )

        try:
            parsed = ProviderResponse.model_validate_json(response.text)
            if not parsed.choices:
                raise ValueError("missing choices")
            message = parsed.choices[0].message
        except (ValidationError, ValueError) as exc:
            raise LLMUnavailableError("LLM provider returned an invalid response") from exc

        return ModelTurn(
            content=message.content,
            tool_calls=[
                ModelToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=call.function.arguments,
                )
                for call in message.tool_calls
            ],
        )

    @staticmethod
    def _serialize_message(message: ChatMessage) -> dict[str, object]:
        serialized: dict[str, object] = {"role": message.role, "content": message.content}
        if message.tool_call_id is not None:
            serialized["tool_call_id"] = message.tool_call_id
        if message.tool_calls is not None:
            serialized["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in message.tool_calls
            ]
        return serialized
