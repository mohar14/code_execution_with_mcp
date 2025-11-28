# Quick Start Guide - Gradio UI with Auto-Start

The Gradio UI now **automatically starts all required services** when you launch it. No need to manually start the MCP server or Agent API in separate terminals!

## Prerequisites

Before running, ensure:

1. **Docker is running**
   ```bash
   docker ps  # Should work without errors
   ```

2. **Docker image is built**
   ```bash
   cd /Users/mohardey/Projects/code-execution-with-mcp/mcp_server/docker
   ./build.sh
   ```

3. **Dependencies are installed**
   ```bash
   cd /Users/mohardey/Projects/code-execution-with-mcp
   uv sync
   ```

## One-Command Launch

Simply run:

```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python gradio_ui/app.py
```

That's it! The app will:
1. ✅ Start the MCP Server (port 8989)
2. ✅ Start the Agent API (port 8000)
3. ✅ Launch the Gradio UI (port 7860)
4. ✅ Verify all services are healthy
5. ✅ Open at http://localhost:7860

## What You'll See

```
============================================================
Starting Code Execution with MCP - All Services
============================================================
INFO - Starting MCP Server...
INFO - MCP Server started with PID: 12345
INFO - MCP Server is ready!
INFO - Starting Agent API Server...
INFO - Agent API Server started with PID: 12346
INFO - Agent API Server is ready!
============================================================
All services started successfully!
MCP Server: http://localhost:8989
Agent API: http://localhost:8000
Gradio UI will start on: http://0.0.0.0:7860
============================================================

Running on local URL:  http://127.0.0.1:7860

To create a public link, set `share=True` in `launch()`.
```

## Stopping the Application

When you stop the Gradio UI (Ctrl+C), it will **automatically stop all background services**:

```
^C
INFO - Stopping background servers...
INFO - Terminating Agent API Server (PID: 12346)
INFO - Agent API Server stopped
INFO - Terminating MCP Server (PID: 12345)
INFO - MCP Server stopped
```

## Troubleshooting

### Port Already in Use

**Error:** `Cannot find empty port in range: 7860-7860`

**Solution:**
```bash
# Kill any process using port 7860
lsof -ti:7860 | xargs kill -9

# Or specify a different port
GRADIO_SERVER_PORT=7861 uv run python gradio_ui/app.py
```

### MCP Server Won't Start

**Symptoms:**
- "MCP Server did not become ready within 30 seconds"
- "Failed to start MCP Server"

**Solutions:**

1. Check Docker is running:
   ```bash
   docker ps
   ```

2. Check port 8989 is available:
   ```bash
   lsof -i:8989
   # If something is using it:
   lsof -ti:8989 | xargs kill -9
   ```

3. Check Docker image exists:
   ```bash
   docker images | grep code-executor
   # Should show: mcp-code-executor:latest
   ```

4. Rebuild Docker image if needed:
   ```bash
   cd mcp_server/docker
   ./build.sh
   ```

### Agent API Won't Start

**Symptoms:**
- "Agent API did not become ready within 30 seconds"
- "Failed to start Agent API Server"

**Solutions:**

1. Check port 8000 is available:
   ```bash
   lsof -i:8000
   # If something is using it:
   lsof -ti:8000 | xargs kill -9
   ```

2. Verify MCP Server started successfully (Agent API depends on it)

3. Check environment variables are set (if needed):
   ```bash
   # In .env file or export:
   export DEFAULT_MODEL=gemini-2.0-flash-exp
   export AGENT_NAME=code_executor_agent
   ```

### Services Start but Health Check Fails

**Symptoms:**
- Green indicator doesn't appear in UI
- "Services not initialized" error when trying to chat

**Solutions:**

1. Check logs in terminal for startup errors

2. Manually verify health:
   ```bash
   curl http://localhost:8989/health
   curl http://localhost:8000/health
   ```

3. Wait a few seconds after launch before chatting (services need time to initialize)

### Container Permission Issues

**Symptoms:**
- Errors about Docker socket permissions
- "Cannot connect to Docker daemon"

**Solutions:**

1. Ensure Docker daemon is running:
   ```bash
   # On macOS
   open -a Docker
   ```

2. Check Docker permissions:
   ```bash
   docker ps  # Should work without sudo
   ```

3. Add your user to docker group (Linux only):
   ```bash
   sudo usermod -aG docker $USER
   # Then log out and back in
   ```

## Manual Service Control (Advanced)

If you need to run services separately (for debugging):

### Option 1: Run All Services Automatically (Recommended)
```bash
uv run python gradio_ui/app.py
```

### Option 2: Run Services Manually (For Debugging)

**Terminal 1 - MCP Server:**
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python -m mcp_server.server
```

**Terminal 2 - Agent API:**
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python -m agent_api.server
```

**Terminal 3 - Gradio UI (without auto-start):**

Edit `gradio_ui/app.py` and comment out the initialization:
```python
if __name__ == "__main__":
    # initialize_services()  # Comment this out
    demo.queue()
    demo.launch(...)
```

Then run:
```bash
uv run python gradio_ui/app.py
```

## Using the UI

Once launched, open http://localhost:7860 in your browser.

### 1. Check System Status

Look for green indicators:
- 🟢 **Agent API**: Connected
- 🟢 **MCP Server**: Connected

If you see 🔴 red indicators, see troubleshooting above.

### 2. Start Chatting

Try example queries:
- "Write a Python script to calculate the factorial of 10"
- "Create a plot showing sine and cosine waves from 0 to 2π"
- "Find the derivative of x³ + 2x² - 5x + 3 using SymPy"

### 3. Watch the Activity Monitor

The right panel shows real-time:
- 🔧 **Tool Calls**: When agent uses MCP tools
- 🐳 **Docker Actions**: Container operations
- 🤔 **Reasoning Steps**: Agent's thought process
- ✅ **Status Updates**: Success/error indicators

### 4. Manage Your Session

- **Your User ID**: Shows your unique session ID
- **New Session**: Click to start fresh with a new container
- **Clear**: Clear chat history

## Development Mode

To enable auto-reload during development:

Edit `gradio_ui/app.py`:
```python
if __name__ == "__main__":
    initialize_services()
    demo.queue()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True  # Add this
    )
```

Note: Auto-reload won't restart the background services. You'll need to manually restart the entire app.

## Logs and Debugging

### View Service Logs

Services run in background, but you can check their output:

```bash
# Check if services are running
ps aux | grep -E "(mcp_server|agent_api)"

# View service logs (if running in test mode)
tail -f /tmp/gradio_test.log
```

### Enable Verbose Logging

Edit `gradio_ui/app.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## Configuration

### Change Ports

Edit `gradio_ui/app.py`:
```python
# Configuration
AGENT_API_URL = "http://localhost:8000"  # Change port
MCP_SERVER_URL = "http://localhost:8989"  # Change port
```

Or set environment variables:
```bash
export AGENT_API_PORT=8001
export MCP_SERVER_PORT=8990
```

### Change Models

Edit `agent_api/config.py` or set environment variable:
```bash
export DEFAULT_MODEL=gemini-2.0-flash-exp
```

Supported models (via LiteLLM):
- Google: `gemini-2.0-flash-exp`, `gemini-1.5-pro`
- OpenAI: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`
- Anthropic: `claude-3-sonnet`, `claude-3-opus`
- And many more...

## Testing the Installation

Use the included test script:

```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
chmod +x tests/test_gradio_ui/test_startup.sh
./tests/test_gradio_ui/test_startup.sh
```

This will:
1. Start all services
2. Wait for initialization
3. Check health endpoints
4. Display logs
5. Clean up

## Performance Tips

### Startup Time
- First startup: ~5-10 seconds (services need to initialize)
- Subsequent requests: Instant (containers are cached)

### Container Management
- Containers persist across requests (faster)
- Automatically cleaned up on shutdown
- Each user gets their own isolated container

### Memory Usage
- MCP Server: ~50-100 MB
- Agent API: ~100-200 MB
- Gradio UI: ~50-100 MB
- Docker containers: ~200-500 MB per user

## Next Steps

- Try the example queries
- Upload your own code for execution
- Check out the [full README](README.md) for advanced features
- Explore the Activity Monitor to understand agent behavior
- Create custom skills (see main project README)

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review logs in the terminal
3. Verify Docker is running and image is built
4. Check all ports are available
5. Try the test script to isolate issues

---

**Built with ❤️ for the MCP 1st Birthday Hackathon**

Team: [Mohar Dey](https://huggingface.co/mohar1406) • [Jonathan Kadowaki](https://huggingface.co/jkadowak)
