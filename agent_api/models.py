"""OpenAI-compatible Pydantic models for Agent API."""

from typing import Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """Single message in a chat conversation."""

    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Request model for chat completions endpoint."""

    model: str
    messages: list[ChatMessage]
    stream: Literal[True] = True  # Only streaming supported
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None  # User identifier for session management


class DeltaContent(BaseModel):
    """Delta content for streaming chunks."""

    role: str | None = None
    content: str | None = None
    tool_calls: list[dict] | None = None


class Choice(BaseModel):
    """Choice in a chat completion chunk."""

    index: int
    delta: DeltaContent
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """Streaming chat completion chunk in OpenAI format."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int  # Unix timestamp
    model: str
    choices: list[Choice]
    usage: dict | None = None


class ModelInfo(BaseModel):
    """Model information for /v1/models endpoint."""

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelList(BaseModel):
    """List of available models."""

    object: Literal["list"] = "list"
    data: list[ModelInfo]


class ErrorResponse(BaseModel):
    """Error response model."""

    error: dict[str, str]


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    mcp_server_connected: bool
    timestamp: str
