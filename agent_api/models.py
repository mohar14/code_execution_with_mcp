from typing import Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: Literal[True] = True
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None


class DeltaContent(BaseModel):
    role: str | None = None
    content: str | None = None
    tool_calls: list[dict] | None = None


class Choice(BaseModel):
    index: int
    delta: DeltaContent
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[Choice]
    usage: dict | None = None


class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelInfo]


class HealthResponse(BaseModel):
    status: str
    service: str
    mcp_server_connected: bool
    timestamp: str
