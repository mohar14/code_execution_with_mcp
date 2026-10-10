import json
import time
import uuid
from collections.abc import AsyncGenerator

from google.adk.events import Event
from loguru import logger
from models import ChatCompletionChunk, Choice, DeltaContent


def convert_content_event(event: Event, request_id: str, model: str) -> ChatCompletionChunk:
    content = ""
    if hasattr(event, "content") and event.content:
        content = str(event.content)

    delta = DeltaContent(content=content)
    choice = Choice(index=0, delta=delta, finish_reason=None)

    return ChatCompletionChunk(
        id=request_id, created=int(time.time()), model=model, choices=[choice]
    )


def convert_tool_call_event(event: Event, request_id: str, model: str) -> ChatCompletionChunk:
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
    delta = DeltaContent()
    choice = Choice(index=0, delta=delta, finish_reason="stop")

    return ChatCompletionChunk(
        id=request_id, created=int(time.time()), model=model, choices=[choice]
    )


async def convert_adk_events_to_openai(
    events: AsyncGenerator[Event, None], model: str
) -> AsyncGenerator[ChatCompletionChunk, None]:
    request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    logger.info(f"[NEW CONVERTER] Starting event conversion for request {request_id}")

    first_chunk = True
    previous_event_has_tool_calls = False

    try:
        async for event in events:
            logger.info(f"[NEW CONVERTER] Processing event: {type(event).__name__}")

            if first_chunk:
                delta = DeltaContent(role="assistant")
                choice = Choice(index=0, delta=delta, finish_reason=None)
                yield ChatCompletionChunk(
                    id=request_id, created=int(time.time()), model=model, choices=[choice]
                )
                first_chunk = False

            function_calls = []
            if hasattr(event, "get_function_calls"):
                function_calls = event.get_function_calls()

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

            if (
                hasattr(event, "content")
                and event.content
                and hasattr(event.content, "parts")
                and event.partial is True
            ):
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        if not previous_event_has_tool_calls:
                            delta = DeltaContent(content=part.text)
                        else:
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

    except Exception as e:
        logger.error(f"Error converting events: {e}")
        raise

    logger.debug(f"Sending completion chunk for request {request_id}")
    yield convert_completion_event(request_id, model)


def format_sse(chunk: ChatCompletionChunk) -> str:
    try:
        logger.debug(f"Serializing chunk: {chunk}")
        chunk_data = chunk.model_dump_json()
    except Exception as e:
        logger.error(f"Failed to serialize chunk: {e}")
        raise e
    return f"data: {chunk_data}\n\n"


def format_sse_done() -> str:
    return "data: [DONE]\n\n"
