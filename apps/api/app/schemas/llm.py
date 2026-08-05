from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelToolCall(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=64)
    arguments: str


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None
    tool_call_id: str | None = None
    tool_calls: list[ModelToolCall] | None = None


class ToolFunctionDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, object]


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: ToolFunctionDefinition


class ModelTurn(BaseModel):
    content: str | None = None
    tool_calls: list[ModelToolCall] = Field(default_factory=list)


class ProviderToolFunction(BaseModel):
    name: str
    arguments: str


class ProviderToolCall(BaseModel):
    id: str
    type: Literal["function"]
    function: ProviderToolFunction


class ProviderMessage(BaseModel):
    content: str | None = None
    tool_calls: list[ProviderToolCall] = Field(default_factory=list)


class ProviderChoice(BaseModel):
    message: ProviderMessage


class ProviderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: list[ProviderChoice]
