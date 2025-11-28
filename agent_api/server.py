"""FastAPI server for OpenAI-compatible Agent API."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from agent_manager import AgentManager
from config import settings
from converters import convert_adk_events_to_openai, format_sse, format_sse_done
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from google.genai import types

from agent_manager import AgentManager
from config import settings
from converters import convert_adk_events_to_openai, format_sse, format_sse_done
from models import (
    ChatCompletionRequest,
    HealthResponse,
    ModelInfo,
    ModelList,
)
from session_store import SessionStore

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    message_content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)]
    )

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


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(
        app=app,
        host=settings.agent_api_host,
        port=settings.agent_api_port,
        log_level="info",
        reload=os.getenv("DEV_RELOAD", "false").lower() == "true",  # Development hot reload flag
    )
