# Gradio UI Tool Calls Issue - Investigation Report

## Problem

When using the Gradio UI, tool calls don't appear in the "Tool Calls" section of the Activity Monitor. The collapsible sections show:
- **Docker Operations**: Stuck on "Initializing container"
- **Tool Calls**: Empty
- **Status**: Shows "Completed" but no intermediate updates
- **Debug/Raw Output**: Contains all the actual tool call information as raw text

## Root Cause

The issue is in how Google ADK events are converted to OpenAI-compatible format in [`agent_api/converters.py`](../agent_api/converters.py).

### Current Behavior

1. Google ADK sends events through `runner.run_async()`
2. The `convert_adk_events_to_openai()` function processes these events
3. For content, it extracts `event.content` and sends it as `delta.content`
4. For tool calls, it looks for `event.tool_call` attribute

### The Problem

Google ADK doesn't expose tool calls via `event.tool_call`. Instead, ALL content (including internal state and tool calls) comes through as text in `event.content`.

**Example of what we receive**:
```python
parts=[Part(
  text='I'll create a Python script that prints hello world'
), Part(
  function_call=FunctionCall(
    name='write_file',
    args={'file_path': '/workspace/hello.py', 'content': 'print("Hello, World!")'}
  )
)]
```

This appears as a string in `delta.content`, not as structured `delta.tool_calls`.

### Expected vs Actual

**Expected** (OpenAI format):
```json
{
  "choices": [{
    "delta": {
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "write_file",
          "arguments": "{\"file_path\": \"/workspace/hello.py\", ...}"
        }
      }]
    }
  }]
}
```

**Actual** (what we get):
```json
{
  "choices": [{
    "delta": {
      "content": "parts=[Part(\n  function_call=FunctionCall(...)\n)]"
    }
  }]
}
```

## Impact

1. **Gradio UI**:
   - Tool calls section empty
   - Docker activities not updated
   - Poor user experience - can't see what's happening

2. **Functionality**:
   - Everything still works (tools execute correctly)
   - Just the visibility/monitoring that's broken

3. **Current Workaround**:
   - All tool info visible in "Debug/Raw Output" section
   - Not user-friendly, but technically accessible

## Solution

Fix the converter to properly parse Google ADK events.

### Investigation Needed

1. **Determine actual Event structure**:
   ```python
   # What attributes does a Google ADK Event actually have?
   # - event.content
   # - event.parts?
   # - event.function_call?
   # - event.tool_use?
   ```

2. **Parse the content**:
   - If events don't expose structured tool calls
   - We need to parse the string representation
   - Extract function calls from `parts=[...]` format

3. **Generate proper OpenAI chunks**:
   - Separate tool calls from text content
   - Send tool calls in `delta.tool_calls`
   - Send text in `delta.content`

### Proposed Fix

**File**: `agent_api/converters.py`

**Approach 1**: If Google ADK events have structured attributes:
```python
async def convert_adk_events_to_openai(...):
    async for event in events:
        # Check for parts/function calls in event
        if hasattr(event, 'parts'):
            for part in event.parts:
                if hasattr(part, 'function_call'):
                    # Generate tool call chunk
                    yield convert_tool_call_event(part.function_call, ...)
                elif hasattr(part, 'text'):
                    # Generate content chunk
                    yield convert_content_event(part.text, ...)
```

**Approach 2**: If we must parse string content:
```python
import re

def parse_function_calls(content: str):
    """Parse function calls from Google ADK content string."""
    # Pattern to match: function_call=FunctionCall(name='...', args={...})
    pattern = r"function_call=FunctionCall\(name='(\w+)',\s*args=({[^}]+})\)"
    matches = re.findall(pattern, content)

    tool_calls = []
    for name, args_str in matches:
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": args_str
            }
        })
    return tool_calls
```

## Testing Plan

1. **Unit Test**: Test converter with sample Google ADK events
2. **Integration Test**: Run full flow through Gradio UI
3. **Verify**:
   - Tool calls appear in correct section
   - Docker activities update properly
   - Text content separated from tool calls
   - No duplicate entries

## Files to Modify

1. **`agent_api/converters.py`**:
   - Update `convert_adk_events_to_openai()` function
   - Add parsing logic for Google ADK events
   - Properly separate content from tool calls

2. **`gradio_ui/app.py`** (already fixed):
   - Added `displayed_tool_calls` tracking to prevent duplicates
   - Check for complete JSON before displaying
   - Only display each tool call once

3. **`tests/test_agent_api/test_converters.py`** (create):
   - Test cases for event conversion
   - Verify tool call extraction
   - Verify content separation

## Next Steps

1. **Inspect Google ADK Event objects**:
   - Add logging to see actual event structure
   - Check Google ADK documentation
   - Test with real events

2. **Implement proper parsing**:
   - Based on inspection results
   - Choose appropriate approach
   - Add error handling

3. **Test thoroughly**:
   - Unit tests for converter
   - End-to-end tests with Gradio UI
   - Verify all scenarios work

4. **Update documentation**:
   - Remove "Known Issues" section once fixed
   - Document the solution
   - Add code comments explaining the parsing

## References

- Google ADK Events: https://github.com/google/genai-agent-dev-kit
- OpenAI Streaming Format: https://platform.openai.com/docs/api-reference/streaming
- Current converter: `agent_api/converters.py:112-161`
- Gradio chat handler: `gradio_ui/app.py:560-728`

---

**Status**: Investigated, root cause identified, solution proposed
**Date**: 2025-11-28
**Next**: Implement converter fix in agent_api
