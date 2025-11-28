"""Convert Google ADK Events to OpenAI ChatCompletionChunk format."""

import json
import time
import uuid
from collections.abc import AsyncGenerator

from google.adk.events import Event
from loguru import logger
from models import ChatCompletionChunk, Choice, DeltaContent


def convert_content_event(event: Event, request_id: str, model: str) -> ChatCompletionChunk:
    """Convert text content from ADK event to OpenAI chunk.

    Args:
        event: Google ADK Event with text content
        request_id: Unique request identifier
        model: Model name

    Returns:
        OpenAI-compatible ChatCompletionChunk
    """
    # Extract content from the event
    content = ""
    if hasattr(event, "content") and event.content:
        content = str(event.content)

    delta = DeltaContent(content=content)
    choice = Choice(index=0, delta=delta, finish_reason=None)

    return ChatCompletionChunk(
        id=request_id, created=int(time.time()), model=model, choices=[choice]
    )


def convert_tool_call_event(event: Event, request_id: str, model: str) -> ChatCompletionChunk:
    """Convert tool call from ADK event to OpenAI chunk.

    Args:
        event: Google ADK Event with tool call
        request_id: Unique request identifier
        model: Model name

    Returns:
        OpenAI-compatible ChatCompletionChunk
    """
    # Extract tool call information from the event
    tool_calls = []

    if hasattr(event, "tool_call") and event.tool_call:
        tool_call = event.tool_call
        tool_calls.append(
            {
                "id": getattr(tool_call, "id", f"call_{uuid.uuid4().hex[:12]}"),
                "type": "function",
                "function": {
                    "name": getattr(tool_call, "name", "unknown"),
                    "arguments": json.dumps(getattr(tool_call, "args", {})),
                },
            }
        )

    delta = DeltaContent(tool_calls=tool_calls)
    choice = Choice(index=0, delta=delta, finish_reason=None)

    return ChatCompletionChunk(
        id=request_id, created=int(time.time()), model=model, choices=[choice]
    )


def convert_completion_event(request_id: str, model: str) -> ChatCompletionChunk:
    """Generate final chunk with finish_reason.

    Args:
        request_id: Unique request identifier
        model: Model name

    Returns:
        OpenAI-compatible ChatCompletionChunk with finish_reason
    """
    delta = DeltaContent()
    choice = Choice(index=0, delta=delta, finish_reason="stop")

    return ChatCompletionChunk(
        id=request_id, created=int(time.time()), model=model, choices=[choice]
    )


def convert_error_event(request_id: str, model: str, error: str) -> ChatCompletionChunk:
    """Generate error chunk.

    Args:
        request_id: Unique request identifier
        model: Model name
        error: Error message

    Returns:
        OpenAI-compatible ChatCompletionChunk with error
    """
    delta = DeltaContent(content=f"Error: {error}")
    choice = Choice(index=0, delta=delta, finish_reason="error")

    return ChatCompletionChunk(
        id=request_id, created=int(time.time()), model=model, choices=[choice]
    )


async def convert_adk_events_to_openai(
    events: AsyncGenerator[Event, None], model: str
) -> AsyncGenerator[ChatCompletionChunk, None]:
    """Convert stream of ADK events to OpenAI chunks.

    Args:
        events: Async generator of Google ADK Events
        model: Model name

    Yields:
        OpenAI-compatible ChatCompletionChunk objects
    """
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    logger.info(f"[NEW CONVERTER] Starting event conversion for request {request_id}")

    first_chunk = True
    previous_event_has_tool_calls = False

    try:
        async for event in events:
            logger.info(f"[NEW CONVERTER] Processing event: {type(event).__name__}")

            # Send role in first chunk
            if first_chunk:
                delta = DeltaContent(role="assistant")
                choice = Choice(index=0, delta=delta, finish_reason=None)
                yield ChatCompletionChunk(
                    id=request_id, created=int(time.time()), model=model, choices=[choice]
                )
                first_chunk = False

            # Extract function calls from event
            function_calls = []
            if hasattr(event, "get_function_calls"):
                function_calls = event.get_function_calls()

            # If there are function calls, send them as tool calls
            if function_calls:
                for func_call in function_calls:
                    tool_call = {
                        "id": getattr(func_call, "id", f"call_{uuid.uuid4().hex[:12]}"),
                        "type": "function",
                        "function": {
                            "name": getattr(func_call, "name", "unknown"),
                            "arguments": json.dumps(getattr(func_call, "args", {})),
                        },
                    }
                    delta = DeltaContent(tool_calls=[tool_call])
                    choice = Choice(index=0, delta=delta, finish_reason=None)
                    yield ChatCompletionChunk(
                        id=request_id, created=int(time.time()), model=model, choices=[choice]
                    )
                    previous_event_has_tool_calls = True

            # Extract text content from event (excluding function calls/responses)
            if hasattr(event, "content") and event.content and hasattr(event.content, "parts"):
                # Parse parts to extract just the text
                for part in event.content.parts:
                    # Only send text parts, skip function calls/responses
                    if hasattr(part, "text") and part.text:
                        if not previous_event_has_tool_calls:
                            delta = DeltaContent(content=part.text)
                        else:
                            # Get a newline if the last event was a tool call to avoid lack of padding
                            delta = DeltaContent(content="\n\n" + part.text)
                        choice = Choice(index=0, delta=delta, finish_reason=None)
                        logger.debug(f"{delta = } {previous_event_has_tool_calls = }")
                        yield ChatCompletionChunk(
                            id=request_id,
                            created=int(time.time()),
                            model=model,
                            choices=[choice],
                        )
                        previous_event_has_tool_calls = False

            # Note: Tool results are typically included in content events
            # so we handle them as content

    except Exception as e:
        logger.error(f"Error converting events: {e}", exc_info=True)
        yield convert_error_event(request_id, model, str(e))

    # Send final completion chunk
    logger.debug(f"Sending completion chunk for request {request_id}")
    yield convert_completion_event(request_id, model)


def format_sse(chunk: ChatCompletionChunk) -> str:
    """Format chunk as Server-Sent Event.

    Args:
        chunk: ChatCompletionChunk to format

    Returns:
        SSE-formatted string
    """
    return f"data: {chunk.model_dump_json()}\n\n"


def format_sse_done() -> str:
    """Format done marker.

    Returns:
        SSE done marker string
    """
    return "data: [DONE]\n\n"
