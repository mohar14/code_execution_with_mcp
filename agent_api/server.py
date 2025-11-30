"""FastAPI server for OpenAI-compatible Agent API."""

import base64
import os
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from agent_manager import AgentManager
from config import settings
from converters import convert_adk_events_to_openai, format_sse, format_sse_done
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from loguru import logger
from models import (
    ChatCompletionRequest,
    HealthResponse,
    ModelInfo,
    ModelList,
)
from session_store import SessionStore

# Global instances
agent_manager: AgentManager | None = None
session_store: SessionStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application.

    Args:
        app: FastAPI application instance
    """
    # Startup
    global agent_manager, session_store

    logger.info("Starting Agent API server...")
    logger.info(f"MCP Server URL: {settings.mcp_server_url}")
    logger.info(f"Default Model: {settings.default_model}")

    # Initialize managers
    agent_manager = AgentManager(mcp_server_url=settings.mcp_server_url)
    session_store = SessionStore()

    logger.info("Agent API server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Agent API server...")
    logger.info(
        f"Active sessions: {session_store.get_active_session_count() if session_store else 0}"
    )
    logger.info(
        f"Active runners: {agent_manager.get_active_runner_count() if agent_manager else 0}"
    )


# Create FastAPI app
app = FastAPI(
    title="Code Execution Agent API",
    description="OpenAI-compatible API for code execution agents with Google ADK and MCP",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions.

    Args:
        request: The incoming request
        exc: The HTTP exception

    Returns:
        JSON response with error details
    """
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions.

    Args:
        request: The incoming request
        exc: The exception

    Returns:
        JSON response with error details
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"message": "Internal server error"}},
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns:
        Health status including MCP server connectivity
    """
    # Check MCP server connectivity
    mcp_healthy = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(settings.mcp_server_health_endpoint, timeout=5.0)
            mcp_healthy = response.status_code == 200
    except Exception as e:
        logger.warning(f"MCP server health check failed: {e}")

    return HealthResponse(
        status="healthy" if mcp_healthy else "degraded",
        service="agent-api",
        mcp_server_connected=mcp_healthy,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/v1/models", response_model=ModelList)
async def list_models():
    """List available models.

    Returns:
        List of available models in OpenAI format
    """
    return ModelList(
        data=[
            ModelInfo(
                id=settings.default_model,
                created=int(time.time()),
                owned_by=settings.get_model_owner(),
            )
        ]
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint (streaming only).

    Args:
        request: Chat completion request

    Returns:
        Streaming response with Server-Sent Events

    Raises:
        HTTPException: If streaming is not enabled or other errors occur
    """
    # Validate streaming is enabled - this should be handled at the pydantic layer
    if not request.stream:
        raise HTTPException(
            status_code=400,
            detail="Only streaming responses are supported. Set stream=true",
        )

    # Get or generate user ID
    user_id = request.user or f"user-{uuid.uuid4().hex[:8]}"
    logger.info(f"Chat completion request from user {user_id}")

    # Get or create session
    if session_store is None:
        raise HTTPException(status_code=500, detail="Session store not initialized")

    # Use "agents" app_name to match the agent module path
    session_id = await session_store.get_or_create_session(user_id, app_name="agents")
    logger.debug(f"Using session {session_id} for user {user_id}")

    # Get runner for user
    if agent_manager is None:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")

    runner = await agent_manager.get_or_create_runner(
        user_id=user_id, session_service=session_store.session_service
    )

    # Extract user message (last message in conversation)
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    user_message = request.messages[-1].content
    logger.debug(f"User message: {user_message[:100]}...")

    # Convert string message to google.genai.types.Content
    message_content = types.Content(role="user", parts=[types.Part(text=user_message)])

    # Stream events
    async def event_generator():
        """Generate Server-Sent Events from ADK agent stream."""
        try:
            # Get ADK event stream
            logger.debug("Starting ADK agent stream")
            adk_events = runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message_content,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE)
            )

            # Convert to OpenAI format
            openai_chunks = convert_adk_events_to_openai(events=adk_events, model=request.model)

            # Stream as SSE
            async for chunk in openai_chunks:
                yield format_sse(chunk)

            # Send done marker
            yield format_sse_done()
            logger.info(f"Chat completion finished for user {user_id}")

        except Exception as e:
            logger.error(f"Error in chat completion: {e}", exc_info=True)
            # Send error as SSE
            error_data = {"error": {"message": str(e), "type": "internal_error"}}
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.get("/")
async def root():
    """Root endpoint with API information.

    Returns:
        API information and available endpoints
    """
    return {
        "name": "Code Execution Agent API",
        "version": "0.1.0",
        "description": "OpenAI-compatible API for code execution agents",
        "endpoints": {
            "health": "/health",
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
        },
        "mcp_server": settings.mcp_server_url,
        "default_model": settings.default_model,
    }


@app.get("/artifacts/{user_id}")
async def list_artifacts(user_id: str):
    """List all artifacts for a specific user.

    Args:
        user_id: User identifier

    Returns:
        JSON response with list of artifact paths

    Example Response:
        {
            "artifacts": ["report.pdf", "analysis.py", "chart.png"],
            "count": 3
        }

    Raises:
        HTTPException: If MCP server request fails
    """
    try:
        # Get MCP server base URL from health endpoint config
        mcp_base = settings.mcp_server_health_endpoint.replace("/health", "")

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_base}/{user_id}/artifacts", timeout=10.0)
            response.raise_for_status()

            # Return the artifacts list from MCP response
            data = response.json()
            return {"artifacts": data.get("artifacts", []), "count": data.get("count", 0)}

    except httpx.HTTPError as e:
        logger.error(f"Failed to list artifacts for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list artifacts: {e!s}")


@app.get("/artifacts/{user_id}/{artifact_id}")
async def download_artifact(user_id: str, artifact_id: str, background_tasks: BackgroundTasks):
    """Download a specific artifact file.

    Args:
        user_id: User identifier
        artifact_id: Artifact filename
        background_tasks: FastAPI background tasks for cleanup

    Returns:
        FileResponse with decoded artifact data

    Raises:
        HTTPException: If artifact not found or retrieval fails
    """
    temp_path = None
    try:
        # Get MCP server base URL from health endpoint config
        mcp_base = settings.mcp_server_health_endpoint.replace("/health", "")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{mcp_base}/{user_id}/artifacts/{artifact_id}", timeout=30.0
            )
            response.raise_for_status()

            # Extract base64 data from MCP response
            data = response.json()
            base64_data = data.get("data", "")

            # Decode base64 to bytes
            decoded_bytes = base64.b64decode(base64_data)

            # Write to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{artifact_id}") as temp_file:
                temp_file.write(decoded_bytes)
                temp_path = temp_file.name

            # Schedule cleanup after response is sent
            background_tasks.add_task(os.unlink, temp_path)

            # Return as downloadable file
            return FileResponse(
                path=temp_path, filename=artifact_id, media_type="application/octet-stream"
            )

    except httpx.HTTPStatusError as e:
        # Clean up temp file if error occurs
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
        elif e.response.status_code == 400:
            raise HTTPException(status_code=400, detail=str(e))
        else:
            logger.error(f"Failed to download artifact {artifact_id} for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to download artifact")

    except Exception as e:
        # Clean up temp file if error occurs
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

        logger.error(f"Error downloading artifact {artifact_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download artifact: {e!s}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app=app,
        host=settings.agent_api_host,
        port=settings.agent_api_port,
        log_level="info",
        reload=os.getenv("DEV_RELOAD", "false").lower() == "true",  # Development hot reload flag
    )
