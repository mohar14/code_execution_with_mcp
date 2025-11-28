# OpenAI-Compatible Agent API Implementation Plan

**Project:** MCP Code Execution with Docker
**Date:** 2025-11-24
**Phase:** 4 - Agent API Integration
**Previous Phase:** [MCP Server Implementation](implementation-status-mcp-server.md)

---

## Executive Summary

This document outlines the implementation plan for building an OpenAI-compatible Agent API that wraps Google ADK agents with streaming chat completions endpoint. The API will integrate with the existing MCP server (Phase 3) to enable AI agents to execute code in isolated Docker containers through a familiar OpenAI SDK interface.

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────┐
│   Client            │
│   (OpenAI SDK)      │
└──────────┬──────────┘
           │ POST /v1/chat/completions (streaming)
           ▼
┌─────────────────────────────────────────┐
│  Agent API (FastAPI) - Port 8000        │
│  - OpenAI-compatible endpoints          │
│  - Session management                   │
│  - Event → OpenAI format conversion     │
└──────────┬──────────────────┬───────────┘
           │                  │
           │ Google ADK       │ MCP Client
           │ Runner           │ (streamable-http)
           ▼                  ▼
    ┌─────────────┐    ┌──────────────────┐
    │ ADK Agent   │    │ MCP Server       │
    │ (Gemini)    │───→│ (Port 8989)      │
    └─────────────┘    └──────────┬───────┘
                                  │
                                  ▼
                           ┌─────────────────┐
                           │ Docker          │
                           │ Containers      │
                           │ (Per-user)      │
                           └─────────────────┘
```

### Data Flow

1. **Client Request:** OpenAI SDK sends POST to `/v1/chat/completions` with streaming enabled
2. **Agent API:** Validates request, creates/retrieves session, initializes Google ADK Runner
3. **ADK Processing:** Runner executes agent with MCP tools, generates Event stream
4. **Event Conversion:** Each ADK Event converted to OpenAI ChatCompletionChunk format
5. **Streaming Response:** SSE stream sent back to client in OpenAI-compatible format
6. **Tool Execution:** When agent calls tools, MCP server routes to user's Docker container
7. **Response Completion:** Stream ends with `[DONE]` marker

---

## Current State Analysis

### Completed Components (Phase 3) ✅

**MCP Server** (`mcp_server/server.py`)
- FastMCP server on port 8989
- 4 tools: `execute_bash`, `write_file`, `read_file`, `read_docstring`
- User isolation via `x-user-id` header
- Streamable HTTP transport
- Health check endpoint
- 28 integration tests (100% passing)

**Docker Execution Client** (`mcp_server/docker_client.py`)
- Per-user container management
- Async command execution
- File operations with pagination
- Timeout handling
- Volume mounts for /tools and /skills

### Dependencies Already Available ✅

From `pyproject.toml`:
```toml
dependencies = [
    "docker>=7.1.0",           # Container management
    "fastapi[standard]>=0.121.3",  # ✅ API server framework
    "fastmcp>=2.13.1",         # MCP server
    "google-adk>=1.18.0",      # ✅ Agent framework
    "mcp>=1.22.0",             # ✅ MCP client
    "openai>=2.8.1",           # ✅ Type definitions
    "pydantic>=2.12.3",        # ✅ Data validation
    "httpx>=0.28.1",           # HTTP client
]
```

**No additional dependencies needed!**

---

## Implementation Phases

### Phase 1: Project Structure & Data Models (1-2 hours)

#### Files to Create

**`agent_api/models.py`** - OpenAI-compatible Pydantic models
```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: Literal[True] = True  # Only streaming supported
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    user: Optional[str] = None  # User identifier

class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int  # Unix timestamp
    model: str
    choices: list[dict]  # Delta format
    usage: Optional[dict] = None

class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str
```

**`agent_api/config.py`** - Configuration management
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Server
    agent_api_host: str = "0.0.0.0"
    agent_api_port: int = 8000

    # MCP Server Connection
    mcp_server_url: str = "http://localhost:8989"

    # Google ADK
    default_model: str = "gemini-2.0-flash-exp"
    agent_name: str = "code_executor_agent"

    # Session Management
    session_timeout_seconds: int = 3600  # 1 hour

    class Config:
        env_file = ".env"

settings = Settings()
```

**`agent_api/session_store.py`** - Session/conversation management
```python
from google.adk.sessions import InMemorySessionService
from datetime import datetime, timedelta

class SessionStore:
    """Manages user sessions and conversation history."""

    def __init__(self):
        self.session_service = InMemorySessionService()
        self.user_sessions: dict[str, dict] = {}
        # Maps user_id -> {"session_id": str, "last_access": datetime}

    def get_or_create_session(self, user_id: str) -> str:
        """Get existing session or create new one for user."""
        # Check if user has active session
        # Create new session if needed or expired
        # Return session_id

    def cleanup_expired_sessions(self):
        """Remove sessions older than timeout."""
        # Background task to cleanup
```

**`agent_api/__init__.py`** - Package initialization
```python
"""OpenAI-compatible Agent API with Google ADK and MCP integration."""

__version__ = "0.1.0"
```

#### Deliverables
- ✅ Data models matching OpenAI API specification
- ✅ Configuration system with environment variable support
- ✅ Session storage using Google ADK's InMemorySessionService
- ✅ Type hints and docstrings throughout

---

### Phase 2: Agent Manager (2-3 hours)

#### File to Create

**`agent_api/agent_manager.py`** - Google ADK Agent lifecycle management

**Key Components:**

1. **MCP Toolset Connection**
```python
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

class AgentManager:
    def __init__(self, mcp_server_url: str):
        self.mcp_server_url = mcp_server_url
        self.runners: dict[str, Runner] = {}  # user_id -> Runner

    def _create_mcp_toolset(self, user_id: str) -> McpToolset:
        """Create MCP toolset with per-user routing."""
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=self.mcp_server_url,
            ),
            header_provider=lambda ctx: {"x-user-id": user_id}
        )
```

2. **Agent Creation**
```python
from google.adk import Agent

def _create_agent(self, user_id: str) -> Agent:
    """Create Google ADK agent with MCP tools."""
    toolset = self._create_mcp_toolset(user_id)

    agent = Agent(
        model=settings.default_model,
        name=settings.agent_name,
        instruction=self._get_instruction_prompt(),
        tools=[toolset],
    )

    return agent
```

3. **Runner Management**
```python
from google.adk import Runner
from google.adk.sessions import InMemorySessionService

def get_or_create_runner(
    self,
    user_id: str,
    session_service: InMemorySessionService
) -> Runner:
    """Get existing runner or create new one for user."""
    if user_id not in self.runners:
        agent = self._create_agent(user_id)

        runner = Runner(
            app_name='code-execution-app',
            agent=agent,
            session_service=session_service,
        )

        self.runners[user_id] = runner

    return self.runners[user_id]
```

4. **Instruction Prompt**
```python
def _get_instruction_prompt(self) -> str:
    """Get agent instruction/system prompt."""
    return """You are a code execution assistant with access to secure Docker containers.

You can:
- Execute bash commands and Python scripts
- Write files to the workspace
- Read file contents with pagination
- Inspect function documentation

Guidelines:
- Always validate user code before execution
- Use appropriate timeouts for long-running tasks
- Handle errors gracefully and provide clear feedback
- Keep the workspace organized

Available tools:
- execute_bash: Run commands in isolated container
- write_file: Create/overwrite files in workspace
- read_file: Read file contents (supports pagination)
- read_docstring: Extract function documentation

Be helpful, secure, and efficient!"""
```

#### Integration Pattern
```python
# In server.py
agent_manager = AgentManager(mcp_server_url=settings.mcp_server_url)

# For each request
runner = agent_manager.get_or_create_runner(user_id, session_service)
```

#### Deliverables
- ✅ Agent initialization with MCP toolset
- ✅ Per-user Runner management
- ✅ Header-based user routing to MCP server
- ✅ Instruction prompt for agent behavior
- ✅ Runner lifecycle management

---

### Phase 3: Event Converters (2-3 hours)

#### File to Create

**`agent_api/converters.py`** - Convert Google ADK Events to OpenAI format

**Key Challenges:**
1. ADK uses Event-based streaming
2. OpenAI uses ChatCompletionChunk with delta updates
3. Different representations for tool calls and responses

**Event Types to Handle:**

1. **Text Content Events**
```python
from google.adk import Event
from agent_api.models import ChatCompletionChunk
import time
import uuid

def convert_content_event(event: Event, request_id: str, model: str) -> ChatCompletionChunk:
    """Convert text content from ADK event to OpenAI chunk."""
    return ChatCompletionChunk(
        id=request_id,
        created=int(time.time()),
        model=model,
        choices=[{
            "index": 0,
            "delta": {
                "role": "assistant",
                "content": event.content  # Text content from event
            },
            "finish_reason": None
        }]
    )
```

2. **Tool Call Events**
```python
def convert_tool_call_event(event: Event, request_id: str, model: str) -> ChatCompletionChunk:
    """Convert tool call from ADK event to OpenAI chunk."""
    # ADK tool call format -> OpenAI tool_calls format
    return ChatCompletionChunk(
        id=request_id,
        created=int(time.time()),
        model=model,
        choices=[{
            "index": 0,
            "delta": {
                "tool_calls": [{
                    "id": event.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": event.tool_name,
                        "arguments": event.tool_args
                    }
                }]
            },
            "finish_reason": None
        }]
    )
```

3. **Completion Events**
```python
def convert_completion_event(request_id: str, model: str) -> ChatCompletionChunk:
    """Generate final chunk with finish_reason."""
    return ChatCompletionChunk(
        id=request_id,
        created=int(time.time()),
        model=model,
        choices=[{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    )
```

4. **Main Converter**
```python
async def convert_adk_events_to_openai(
    events: AsyncGenerator[Event, None],
    model: str
) -> AsyncGenerator[ChatCompletionChunk, None]:
    """Convert stream of ADK events to OpenAI chunks."""
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    async for event in events:
        # Determine event type and convert accordingly
        if hasattr(event, 'content') and event.content:
            yield convert_content_event(event, request_id, model)

        elif hasattr(event, 'tool_call'):
            yield convert_tool_call_event(event, request_id, model)

        # Add more event type handlers as needed

    # Send final completion chunk
    yield convert_completion_event(request_id, model)
```

**SSE Formatting:**
```python
import json

def format_sse(chunk: ChatCompletionChunk) -> str:
    """Format chunk as Server-Sent Event."""
    return f"data: {chunk.model_dump_json()}\n\n"

def format_sse_done() -> str:
    """Format done marker."""
    return "data: [DONE]\n\n"
```

#### Deliverables
- ✅ Event type detection and routing
- ✅ ADK Event → OpenAI ChatCompletionChunk conversion
- ✅ Tool call format translation
- ✅ SSE formatting utilities
- ✅ Unique ID and timestamp generation

---

### Phase 4: FastAPI Server (3-4 hours)

#### File to Create

**`agent_api/server.py`** - Main FastAPI application

**Core Components:**

1. **Application Setup**
```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting Agent API server...")
    logger.info(f"MCP Server URL: {settings.mcp_server_url}")

    yield

    # Shutdown
    logger.info("Shutting down Agent API server...")
    # Cleanup runners, sessions, etc.

app = FastAPI(
    title="Code Execution Agent API",
    description="OpenAI-compatible API for code execution agents",
    version="0.1.0",
    lifespan=lifespan
)
```

2. **Chat Completions Endpoint**
```python
from agent_api.models import ChatCompletionRequest, ChatCompletionChunk
from agent_api.converters import convert_adk_events_to_openai, format_sse, format_sse_done
from agent_api.agent_manager import AgentManager
from agent_api.session_store import SessionStore

agent_manager = AgentManager(mcp_server_url=settings.mcp_server_url)
session_store = SessionStore()

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint (streaming only)."""

    # Validate streaming is enabled
    if not request.stream:
        raise HTTPException(
            status_code=400,
            detail="Only streaming responses are supported. Set stream=true"
        )

    # Get or generate user ID
    user_id = request.user or f"user-{uuid.uuid4().hex[:8]}"

    # Get or create session
    session_id = session_store.get_or_create_session(user_id)

    # Get runner for user
    runner = agent_manager.get_or_create_runner(
        user_id=user_id,
        session_service=session_store.session_service
    )

    # Extract user message (last message in conversation)
    user_message = request.messages[-1].content

    # Stream events
    async def event_generator():
        try:
            # Get ADK event stream
            adk_events = runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            )

            # Convert to OpenAI format
            openai_chunks = convert_adk_events_to_openai(
                events=adk_events,
                model=request.model
            )

            # Stream as SSE
            async for chunk in openai_chunks:
                yield format_sse(chunk)

            # Send done marker
            yield format_sse_done()

        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            # Send error as SSE
            error_data = {
                "error": {
                    "message": str(e),
                    "type": "internal_error"
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

3. **Models Endpoint**
```python
from agent_api.models import ModelInfo

@app.get("/v1/models")
async def list_models():
    """List available models."""
    return {
        "object": "list",
        "data": [
            ModelInfo(
                id=settings.default_model,
                created=int(time.time()),
                owned_by="google"
            ).model_dump()
        ]
    }
```

4. **Health Check**
```python
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check MCP server connectivity
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.mcp_server_url}/health",
                timeout=5.0
            )
            mcp_healthy = response.status_code == 200
    except Exception:
        mcp_healthy = False

    return {
        "status": "healthy" if mcp_healthy else "degraded",
        "service": "agent-api",
        "mcp_server_connected": mcp_healthy,
        "timestamp": datetime.utcnow().isoformat()
    }
```

5. **Server Entry Point**
```python
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent_api.server:app",
        host=settings.agent_api_host,
        port=settings.agent_api_port,
        log_level="info",
        reload=True  # Development only
    )
```

#### Error Handling
```python
from fastapi import status
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": exc.detail}}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"message": "Internal server error"}}
    )
```

#### Deliverables
- ✅ `/v1/chat/completions` streaming endpoint
- ✅ `/v1/models` list endpoint
- ✅ `/health` status endpoint
- ✅ SSE streaming with proper headers
- ✅ User and session management
- ✅ Error handling and logging
- ✅ CORS support (if needed)

---

### Phase 5: Testing & Integration (2-3 hours)

#### Test Structure

**`tests/test_agent_api/conftest.py`** - Pytest fixtures

```python
import pytest
from httpx import AsyncClient
from agent_api.server import app

@pytest.fixture
async def client():
    """HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def sample_chat_request():
    """Sample OpenAI chat completion request."""
    return {
        "model": "gemini-2.0-flash-exp",
        "messages": [
            {"role": "user", "content": "Execute: print('Hello, World!')"}
        ],
        "stream": True
    }
```

**`tests/test_agent_api/test_server.py`** - Integration tests

```python
import pytest
from openai import AsyncOpenAI

class TestHealthCheck:
    """Test health and status endpoints."""

    async def test_health_endpoint(self, client):
        """Test health check returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "agent-api"

class TestModelsEndpoint:
    """Test models listing."""

    async def test_list_models(self, client):
        """Test models endpoint returns available models."""
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0

class TestChatCompletions:
    """Test chat completions endpoint."""

    async def test_streaming_chat_completion(self, client, sample_chat_request):
        """Test streaming chat completion with simple message."""
        response = await client.post(
            "/v1/chat/completions",
            json=sample_chat_request
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

        # Read SSE stream
        chunks = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data != "[DONE]":
                    chunks.append(json.loads(data))

        assert len(chunks) > 0
        assert chunks[0]["object"] == "chat.completion.chunk"

    async def test_non_streaming_rejected(self, client):
        """Test that non-streaming requests are rejected."""
        request = {
            "model": "gemini-2.0-flash-exp",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        }

        response = await client.post("/v1/chat/completions", json=request)
        assert response.status_code == 400

class TestOpenAISDKIntegration:
    """Test with actual OpenAI SDK client."""

    async def test_openai_sdk_streaming(self):
        """Test streaming with OpenAI SDK."""
        client = AsyncOpenAI(
            base_url="http://localhost:8000/v1",
            api_key="dummy-key"  # Not used but required by SDK
        )

        stream = await client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[
                {"role": "user", "content": "Write a Python script that prints 'Hello'"}
            ],
            stream=True
        )

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert len(chunks) > 0

        # Verify chunk structure
        first_chunk = chunks[0]
        assert first_chunk.id is not None
        assert first_chunk.object == "chat.completion.chunk"

class TestToolExecution:
    """Test end-to-end tool execution via agent."""

    async def test_execute_bash_tool(self):
        """Test agent executes bash command via MCP."""
        client = AsyncOpenAI(
            base_url="http://localhost:8000/v1",
            api_key="dummy"
        )

        stream = await client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[{
                "role": "user",
                "content": "Execute this bash command: echo 'Test output'"
            }],
            stream=True
        )

        full_response = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content

        assert "Test output" in full_response or "executed" in full_response.lower()

    async def test_write_and_execute_workflow(self):
        """Test write file -> execute -> read result workflow."""
        client = AsyncOpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

        # Request agent to write and execute Python script
        stream = await client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[{
                "role": "user",
                "content": """
                1. Write a Python script to /workspace/test.py that calculates 2+2
                2. Execute the script
                3. Tell me the result
                """
            }],
            stream=True
        )

        response = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content

        assert "4" in response  # Result should be mentioned

class TestSessionManagement:
    """Test conversation session handling."""

    async def test_multi_turn_conversation(self):
        """Test that sessions maintain context across turns."""
        client = AsyncOpenAI(base_url="http://localhost:8000/v1", api_key="dummy")
        user_id = "test-user-123"

        # Turn 1: Set a variable
        await client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[{
                "role": "user",
                "content": "Write a file /workspace/data.txt with content 'Session test'"
            }],
            stream=True,
            user=user_id
        )

        # Turn 2: Reference previous context
        stream = await client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[{
                "role": "user",
                "content": "Read the file you just created"
            }],
            stream=True,
            user=user_id
        )

        response = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content

        assert "Session test" in response
```

#### Test Execution

```bash
# Run all agent API tests
uv run pytest tests/test_agent_api/ -v

# Run with coverage
uv run pytest tests/test_agent_api/ --cov=agent_api --cov-report=term

# Run specific test class
uv run pytest tests/test_agent_api/test_server.py::TestOpenAISDKIntegration -v
```

#### Deliverables
- ✅ Unit tests for converters
- ✅ Integration tests with FastAPI TestClient
- ✅ OpenAI SDK compatibility tests
- ✅ End-to-end workflow tests (write → execute → read)
- ✅ Session management tests
- ✅ Error handling tests
- ✅ 90%+ code coverage

---

## Technical Specifications

### API Endpoints

#### POST /v1/chat/completions

**Request:**
```json
{
    "model": "gemini-2.0-flash-exp",
    "messages": [
        {"role": "user", "content": "Execute: print('Hello')"}
    ],
    "stream": true,
    "user": "optional-user-id"
}
```

**Response (SSE Stream):**
```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"gemini-2.0-flash-exp","choices":[{"index":0,"delta":{"role":"assistant","content":"I'll"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"gemini-2.0-flash-exp","choices":[{"index":0,"delta":{"content":" execute"},"finish_reason":null}]}

data: [DONE]
```

#### GET /v1/models

**Response:**
```json
{
    "object": "list",
    "data": [
        {
            "id": "gemini-2.0-flash-exp",
            "object": "model",
            "created": 1234567890,
            "owned_by": "google"
        }
    ]
}
```

#### GET /health

**Response:**
```json
{
    "status": "healthy",
    "service": "agent-api",
    "mcp_server_connected": true,
    "timestamp": "2025-11-24T12:00:00"
}
```

### Event Conversion Mapping

| Google ADK Event | OpenAI ChatCompletionChunk | Notes |
|-----------------|---------------------------|-------|
| Text content event | `delta.content` | Incremental text |
| Tool call event | `delta.tool_calls` | Function call info |
| Tool result event | `delta.content` | Tool execution result |
| Completion event | `finish_reason: "stop"` | End of response |
| Error event | `finish_reason: "error"` | With error details |

### Session Management

**Session Lifecycle:**
1. User sends first message → Create new session
2. Session ID stored with user ID mapping
3. Subsequent messages use same session (context maintained)
4. Sessions expire after 1 hour of inactivity
5. Background task cleans up expired sessions

**Session Storage:**
- In-memory: `InMemorySessionService` from Google ADK
- Production upgrade: Redis or database

### User Isolation

**Per-User Resources:**
- Unique Docker container via MCP server
- Dedicated session with conversation history
- Separate Runner instance (optional optimization)

**User Identification:**
1. `user` field in request → Use as user ID
2. No `user` field → Generate random ID
3. Production: Extract from auth token

---

## Deployment Guide

### Local Development

**1. Start MCP Server (Terminal 1):**
```bash
cd /home/jonathankadowaki/mcp-hackathon-v2/code-execution-with-mcp
uv run python -m mcp_server.server
# Server runs on http://0.0.0.0:8989
```

**2. Start Agent API (Terminal 2):**
```bash
cd /home/jonathankadowaki/mcp-hackathon-v2/code-execution-with-mcp
uv run python -m agent_api.server
# Server runs on http://0.0.0.0:8000
```

**3. Test with OpenAI SDK (Terminal 3):**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy-key"
)

stream = client.chat.completions.create(
    model="gemini-2.0-flash-exp",
    messages=[
        {"role": "user", "content": "Write and execute: print('Hello, World!')"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Environment Variables

Create `.env` file:
```bash
# Agent API
AGENT_API_HOST=0.0.0.0
AGENT_API_PORT=8000

# MCP Server
MCP_SERVER_URL=http://localhost:8989

# Google ADK
DEFAULT_MODEL=gemini-2.0-flash-exp
AGENT_NAME=code_executor_agent

# Session
SESSION_TIMEOUT_SECONDS=3600

# Logging
LOG_LEVEL=INFO
```

### Docker Compose (Production)

**`docker-compose.yml`:**
```yaml
version: '3.8'

services:
  mcp-server:
    build:
      context: .
      dockerfile: mcp_server/docker/Dockerfile
    ports:
      - "8989:8989"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./tools:/tools:ro
      - ./skills:/skills:ro
    environment:
      - MCP_EXECUTOR_IMAGE=mcp-code-executor:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8989/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  agent-api:
    build:
      context: .
      dockerfile: agent_api/Dockerfile
    ports:
      - "8000:8000"
    depends_on:
      - mcp-server
    environment:
      - MCP_SERVER_URL=http://mcp-server:8989
      - AGENT_API_PORT=8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  default:
    name: code-execution-network
```

**Run:**
```bash
docker-compose up -d
docker-compose logs -f agent-api
```

---

## File Structure Summary

```
agent_api/
├── __init__.py                # Package initialization
├── server.py                  # FastAPI app, endpoints (150-200 lines)
├── agent_manager.py           # ADK Agent/Runner management (100-150 lines)
├── models.py                  # OpenAI Pydantic models (80-100 lines)
├── converters.py              # Event → OpenAI conversion (120-150 lines)
├── session_store.py           # Session management (80-100 lines)
└── config.py                  # Configuration settings (50-70 lines)

tests/test_agent_api/
├── __init__.py
├── conftest.py                # Pytest fixtures
└── test_server.py             # Integration tests (300-400 lines)

Total: ~1,000-1,200 lines of code
```

---

## Success Criteria

### Functional Requirements ✅
- [ ] OpenAI SDK can connect and stream responses
- [ ] Agent executes bash commands via MCP tools
- [ ] Agent writes and reads files via MCP tools
- [ ] Multi-turn conversations maintain context
- [ ] Proper SSE streaming format
- [ ] Error handling with graceful degradation

### Non-Functional Requirements ✅
- [ ] <200ms latency for first chunk
- [ ] 90%+ test coverage
- [ ] Comprehensive logging
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Type hints throughout
- [ ] Clean separation of concerns

### Integration Requirements ✅
- [ ] Works with OpenAI Python SDK
- [ ] Works with curl/httpx directly
- [ ] Compatible with LangChain/LlamaIndex
- [ ] Health checks pass
- [ ] MCP server communication reliable

---

## Performance Characteristics

### Expected Latencies

| Operation | Expected Time |
|-----------|--------------|
| First chunk (cold) | 1-2 seconds |
| First chunk (warm) | 200-500ms |
| Streaming chunks | 50-100ms each |
| Tool execution | 500ms-2s (depends on command) |
| Session creation | 100-200ms |

### Resource Usage

**Agent API:**
- Memory: ~100-200 MB baseline
- CPU: <5% idle, 20-40% under load
- Concurrent requests: 50-100 (single instance)

**Total System (MCP + Agent + Docker):**
- Memory: ~500MB-1GB (with 5-10 active users)
- Docker containers: 1 per user (lazy creation)

---

## Security Considerations

### Already Implemented (from MCP Server) ✅
- Per-user container isolation
- Non-root execution in containers
- Read-only tool/skill mounts
- Timeout protection

### To Implement in Agent API
1. **Authentication** (Production)
   - API key validation
   - JWT token support
   - Rate limiting per user

2. **Input Validation**
   - Request size limits
   - Message count limits
   - Content filtering (optional)

3. **Session Security**
   - Session token validation
   - CSRF protection
   - Secure cookie handling

4. **Network Security**
   - CORS configuration
   - HTTPS/TLS in production
   - Firewall rules

---

## Known Limitations & Future Work

### Current Limitations
1. **No non-streaming mode** - Only streaming responses supported
2. **In-memory sessions** - Lost on server restart
3. **Single model** - Only Gemini 2.0 Flash
4. **No function calling** - OpenAI-style function definitions not mapped
5. **Basic error handling** - No retry logic or circuit breakers

### Future Enhancements

**Phase 6 (Gradio UI):**
- Web interface for chat
- File upload/download
- Execution history viewer
- Container management UI

**Production Features:**
- Redis session storage
- Distributed tracing (OpenTelemetry)
- Metrics (Prometheus)
- Logging aggregation (ELK stack)
- Load balancing across multiple instances
- WebSocket support for bidirectional streaming

**Additional Models:**
- Support for GPT-4, Claude, etc. via LiteLLM
- Model selection in UI
- Cost tracking per model

---

## Timeline & Effort Estimation

| Phase | Estimated Time | Priority |
|-------|---------------|----------|
| Phase 1: Structure & Models | 1-2 hours | High |
| Phase 2: Agent Manager | 2-3 hours | High |
| Phase 3: Event Converters | 2-3 hours | High |
| Phase 4: FastAPI Server | 3-4 hours | High |
| Phase 5: Testing | 2-3 hours | High |
| **Total** | **10-15 hours** | - |
| Documentation | 1-2 hours | Medium |
| Deployment Setup | 1-2 hours | Medium |
| **Grand Total** | **12-19 hours** | - |

**Realistic Timeline:** 2-3 days for complete implementation and testing

---

## Testing Strategy

### Unit Tests
- `test_converters.py` - Event conversion logic
- `test_session_store.py` - Session management
- `test_agent_manager.py` - Agent lifecycle

### Integration Tests
- `test_server.py` - API endpoints with TestClient
- Full request/response cycle
- Error handling scenarios

### End-to-End Tests
- OpenAI SDK compatibility
- Real tool execution workflows
- Multi-turn conversations
- Performance benchmarks

### Load Tests (Optional)
- Concurrent user simulation
- Streaming performance under load
- Container scaling behavior

---

## Monitoring & Observability

### Logging
```python
import logging
import structlog

logger = structlog.get_logger(__name__)

# Log levels
logger.debug("Request received", request_id=req_id)
logger.info("Agent created", user_id=user_id)
logger.warning("Session expired", session_id=session_id)
logger.error("Tool execution failed", error=str(e))
```

### Metrics (Future)
- Request count by endpoint
- Streaming duration histogram
- Tool execution latency
- Error rate by type
- Active sessions count

### Health Checks
- `/health` endpoint
- MCP server connectivity
- Docker daemon status
- Session service status

---

## Migration Path

### From Existing MCP Usage
If you have existing MCP client code:
```python
# Old: Direct MCP client
from mcp import Client
client = Client(...)
result = await client.call_tool("execute_bash", {...})

# New: OpenAI SDK (agent handles tool calls)
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1")
response = client.chat.completions.create(
    messages=[{"role": "user", "content": "Execute bash: ls -la"}],
    stream=True
)
```

### Backward Compatibility
- MCP server continues to run independently
- Direct MCP access still possible
- Agent API is additional layer, not replacement

---

## Appendix: Example Workflows

### Example 1: Simple Code Execution
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

stream = client.chat.completions.create(
    model="gemini-2.0-flash-exp",
    messages=[{
        "role": "user",
        "content": "Calculate the factorial of 5 using Python"
    }],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Example 2: Data Analysis Workflow
```python
response = client.chat.completions.create(
    model="gemini-2.0-flash-exp",
    messages=[{
        "role": "user",
        "content": """
        1. Create a CSV file with sample sales data (10 rows)
        2. Use pandas to calculate total sales
        3. Create a simple bar chart
        4. Show me the results
        """
    }],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Example 3: Multi-Turn Debugging
```python
# Turn 1: Initial code
client.chat.completions.create(
    messages=[{
        "role": "user",
        "content": "Write a function to reverse a string"
    }],
    stream=True,
    user="debug-session-1"
)

# Turn 2: Add tests
client.chat.completions.create(
    messages=[{
        "role": "user",
        "content": "Add unit tests for that function"
    }],
    stream=True,
    user="debug-session-1"  # Same session
)

# Turn 3: Fix bug
client.chat.completions.create(
    messages=[{
        "role": "user",
        "content": "The tests are failing, fix the bug"
    }],
    stream=True,
    user="debug-session-1"  # Maintains context
)
```

---

## Conclusion

This implementation plan provides a complete roadmap for building an OpenAI-compatible Agent API that leverages Google ADK and the existing MCP server infrastructure. The architecture is:

✅ **Clean** - Clear separation of concerns across layers
✅ **Testable** - Comprehensive test coverage planned
✅ **Scalable** - Can handle concurrent users with session management
✅ **Compatible** - Works with OpenAI SDK and other clients
✅ **Secure** - Inherits container isolation from MCP server

**Next Steps:**
1. Begin with Phase 1 (Structure & Models)
2. Implement sequentially through Phase 5
3. Deploy locally and test with OpenAI SDK
4. Document any deviations or discoveries
5. Prepare for Phase 6 (Gradio UI integration)

**Status:** ✅ Ready for Implementation

---

*Generated: 2025-11-24*
*Phase: 4 - Agent API Integration*
*Previous Phase: [MCP Server Implementation](implementation-status-mcp-server.md)*
