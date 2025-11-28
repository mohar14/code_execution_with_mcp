# Technical Notes - Gradio UI Implementation

## Import Resolution Fix

### Problem

When starting services via subprocess, Python import resolution can fail depending on how the script is invoked:

**Method 1: Module syntax (`python -m mcp_server.server`)**
- Requires absolute imports: `from mcp_server.docker_client import ...`
- Works when run as module from project root
- Fails if code uses relative imports: `from docker_client import ...`

**Method 2: Direct path (`python ./mcp_server/server.py`)**
- Python adds script directory to path
- Relative imports work within that directory
- Fails for package imports: `from mcp_server.xxx import ...`

### Solution

Set `PYTHONPATH` environment variable to project root before starting subprocesses:

```python
env = dict(os.environ)
env['PYTHONPATH'] = str(PROJECT_ROOT)

subprocess.Popen(
    [python_exe, "./mcp_server/server.py"],
    cwd=PROJECT_ROOT,
    env=env,
    ...
)
```

This ensures:
- Python can find all project packages
- Both relative and absolute imports work
- No need to modify existing import statements

### Why This Matters

The project has mixed import styles:
- `mcp_server/server.py` uses relative imports
- `agent_api/server.py` uses absolute imports

Setting PYTHONPATH accommodates both styles without code changes.

## Process Management

### Subprocess Creation

```python
subprocess.Popen(
    [sys.executable, "./path/to/server.py"],
    cwd=PROJECT_ROOT,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)
```

**Key parameters:**
- `sys.executable`: Uses same Python as parent process (respects venv)
- `cwd`: Sets working directory
- `env`: Passes environment with PYTHONPATH
- `stdout/stderr=PIPE`: Captures output for debugging
- `text=True`: Get string output (not bytes)
- `bufsize=1`: Line-buffered for real-time logging

### Health Checks

30-second timeout with 1-second intervals:

```python
while elapsed < max_wait:
    try:
        response = httpx.get(url, timeout=2.0)
        if response.status_code == 200:
            return True
    except:
        pass

    time.sleep(wait_interval)
    elapsed += wait_interval

    # Detect process death
    if process.poll() is not None:
        return False
```

**Benefits:**
- Non-blocking with incremental checks
- Detects if process crashes during startup
- Reasonable timeout for services that need initialization

### Cleanup Handler

```python
atexit.register(stop_servers)
```

Ensures services stop when:
- User presses Ctrl+C
- Python exits normally
- Exception causes exit
- Gradio app stops

**Graceful shutdown:**
1. Send SIGTERM (`process.terminate()`)
2. Wait 5 seconds
3. Force kill if needed (`process.kill()`)

## Streaming Implementation

### OpenAI SDK Integration

```python
stream = await client.chat.completions.create(
    model="gemini-2.0-flash-exp",
    messages=[{"role": "user", "content": message}],
    stream=True,
    user=user_id
)

async for chunk in stream:
    # Process deltas
    yield updates
```

**Stream events processed:**
- `delta.content`: Agent's response text
- `delta.tool_calls`: MCP tool invocations
- `choice.finish_reason`: Completion status

### Activity Log Building

Incremental HTML construction:

```python
activity_log = ""

# Add tool call
activity_log += format_tool_call(name, args)

# Add Docker action
activity_log += format_docker_action(action, details)

# Yield to UI
yield history, response, activity_log
```

**Benefits:**
- Real-time updates as events arrive
- Preserves order of operations
- No need to rebuild entire log

## Docker Image Name

The MCP server looks for image `mcp-code-executor:latest`.

This is defined in `mcp_server/docker_client.py`:

```python
IMAGE_NAME = "mcp-code-executor:latest"
```

**Build command:**
```bash
cd mcp_server/docker
./build.sh
```

The build script tags the image correctly.

## Port Configuration

Default ports:
- Gradio UI: 7860
- Agent API: 8000
- MCP Server: 8989

**Why these ports:**
- 7860: Gradio default
- 8000: Common API server port
- 8989: Avoids conflicts with 8080, 8888, etc.

**To change:**

Edit `gradio_ui/app.py`:
```python
AGENT_API_URL = "http://localhost:8000"
MCP_SERVER_URL = "http://localhost:8989"
```

Or set environment variables:
```bash
export GRADIO_SERVER_PORT=7861
```

## Health Check Timing

**Why 30 seconds?**
- MCP Server: ~1-2 seconds (just Docker client init)
- Agent API: ~1-2 seconds (depends on MCP)
- Docker image pull: Can take minutes (first time only)

30 seconds accommodates:
- Normal startup
- Slow machines
- Network latency
- Image downloads

If both fail, usually a config issue, not timing.

## Error Handling

### Service Startup Failure

If a service fails to start:
1. Check stderr from subprocess
2. Health check returns False
3. Stop all services
4. Exit with error

```python
if not start_mcp_server():
    logger.error("Failed to start MCP Server. Exiting.")
    sys.exit(1)
```

**User sees:**
- Clear error message
- No orphaned processes
- Clean exit

### Chat Errors

If chat fails:
```python
try:
    stream = await client.chat.completions.create(...)
    # Process stream
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    activity_log += format_error(str(e))
    yield history, response, activity_log
```

**Benefits:**
- User sees error in UI
- Conversation continues
- Full traceback in logs

## Gradio Deprecation Warnings

Current warnings from Gradio 6.0:

1. **CSS parameter**: Move to `launch(css=...)`
2. **Chatbot type**: Use `type='messages'`
3. **show_copy_button**: Use `buttons=["copy"]`
4. **allow_tags**: Will default to True

These are warnings, not errors. UI works fine.

**To fix later:**
```python
# Current
with gr.Blocks(css=CUSTOM_CSS) as demo:
    chatbot = gr.Chatbot(show_copy_button=True)

# Gradio 6.0
with gr.Blocks() as demo:
    chatbot = gr.Chatbot(
        type='messages',
        buttons=["copy"],
        allow_tags=True
    )

demo.launch(css=CUSTOM_CSS)
```

## Performance Optimization

### Why Capture stdout/stderr?

```python
stdout=subprocess.PIPE,
stderr=subprocess.PIPE
```

**Pros:**
- Can debug startup failures
- Prevents console pollution
- Could add log viewer later

**Cons:**
- Buffers can fill up
- Logs not visible in main terminal

**Alternative:**
```python
stdout=None,
stderr=None
```

Logs go to terminal but harder to debug failures.

## Security Considerations

### PYTHONPATH Injection

We set PYTHONPATH dynamically:

```python
env = dict(os.environ)
env['PYTHONPATH'] = str(PROJECT_ROOT)
```

**Safe because:**
- PROJECT_ROOT is computed from script location
- No user input involved
- Only affects subprocess

**Risk if:**
- User can modify gradio_ui/app.py (but then they already have full access)
- Malicious package in project directory (same risk as any Python project)

### Subprocess Execution

We execute Python scripts we control:

```python
[sys.executable, "./mcp_server/server.py"]
```

**Safe because:**
- No user input in command
- Script paths are hardcoded
- Uses same Python as parent

**Would be unsafe:**
```python
[sys.executable, user_input]  # DON'T DO THIS
```

### Port Binding

Services bind to `0.0.0.0`, exposing to network.

**Development:**
- Acceptable on local machine
- Behind firewall

**Production:**
- Add authentication
- Use reverse proxy
- Bind to `127.0.0.1` only

## Testing Strategy

### Startup Test

`tests/test_gradio_ui/test_startup.sh`:
1. Start all services
2. Wait 20 seconds
3. Check health endpoints
4. Verify processes running
5. Clean up

**What it tests:**
- Service startup
- Import resolution
- Health checks
- Process management

**What it doesn't test:**
- Actual chat functionality
- Streaming responses
- UI rendering

### Manual Testing

To test full functionality:
```bash
uv run python gradio_ui/app.py
# Open http://localhost:7860
# Try example queries
# Check activity log updates
```

## Future Improvements

### 1. Log Viewer

Add tab to UI showing service logs:
```python
with gr.Tab("Logs"):
    mcp_logs = gr.Textbox(label="MCP Server", lines=20)
    agent_logs = gr.Textbox(label="Agent API", lines=20)
```

Read from subprocess pipes periodically.

### 2. Progress Indicators

Show startup progress:
```python
status = gr.Textbox(label="Status")

# Update during startup
status.value = "Starting MCP Server..."
status.value = "MCP Server ready!"
status.value = "Starting Agent API..."
```

### 3. Auto-Restart

If service dies, restart automatically:
```python
if process.poll() is not None:
    logger.warning("Service died, restarting...")
    start_service()
```

Needs max retry limit to avoid infinite loops.

### 4. Configuration UI

Let users change settings without editing code:
```python
with gr.Tab("Settings"):
    mcp_port = gr.Number(label="MCP Port", value=8989)
    agent_port = gr.Number(label="Agent Port", value=8000)
    apply_btn = gr.Button("Apply")
```

Would need to restart services with new ports.

### 5. Better Error Messages

Parse common errors and show helpful messages:
```python
if "docker" in error.lower() and "not found" in error.lower():
    return "Docker not installed or not running. Please start Docker Desktop."
```

## Known Limitations

### MCP Health Check Status

The Agent API health endpoint may show `mcp_server_connected: false` even when the MCP connection is working correctly. This happens because:
- The health check only verifies MCP connectivity at startup
- It doesn't continuously monitor the connection during operation
- Tool calls execute successfully regardless of this status

**How to verify MCP is working**:
- Check if tool calls appear in the Activity Monitor
- Verify Docker operations are executing
- Confirm file operations succeed

### Agent Reasoning Section

The "Agent Reasoning" section is currently not populated because Google ADK events don't expose intermediate reasoning steps in a structured format. The model's thinking is embedded in the text content rather than as separate reasoning events.

## Debugging Tips

### Services Won't Start

1. Check Docker:
   ```bash
   docker ps
   ```

2. Check ports:
   ```bash
   lsof -i:7860,8000,8989
   ```

3. Test services manually:
   ```bash
   PYTHONPATH=. uv run python ./mcp_server/server.py
   PYTHONPATH=. uv run python ./agent_api/server.py
   ```

4. Check logs:
   ```bash
   tail -f /tmp/gradio_test.log
   ```

### Import Errors

If you see `ModuleNotFoundError`:

1. Verify PYTHONPATH is set
2. Check __init__.py files exist
3. Verify imports match package structure

```bash
# Debug imports
python -c "import sys; sys.path.append('.'); import mcp_server"
```

### Process Zombies

If processes don't stop:

```bash
# Find all related processes
ps aux | grep -E "(mcp_server|agent_api|gradio_ui)"

# Kill forcefully
pkill -9 -f mcp_server
pkill -9 -f agent_api
pkill -9 -f gradio_ui
```

---

**Last Updated**: 2025-11-28
**Author**: Implementation by Claude Code
