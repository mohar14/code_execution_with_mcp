# Running the MCP Server and Agent API

This guide explains how to start and validate both servers in the code execution system.

## Prerequisites

- Python 3.12
- `uv` package manager installed
- Docker running (for code execution)
- Environment variables configured (see below)

## Required Environment Variables

```bash
# Required for Agent API to make LLM calls
export ANTHROPIC_API_KEY="your-api-key-here"

# Optional: Change default ports
export MCP_SERVER_PORT=8989
export AGENT_API_PORT=8000
```

---

## Starting the MCP Server

The MCP (Model Context Protocol) server provides code execution tools and dynamic skill-based prompts.

### Command

```bash
cd mcp_server
uv run python -m server
```

### Working Directory

**Must run from:** `mcp_server/` directory

The MCP server uses relative imports and expects to be run from its own directory.

### Expected Port

**Default:** `8989`

The server runs on `http://localhost:8989`

### Startup Output

You should see:

```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
Starting MCP Code Executor server...
Initializing Docker execution client...
Docker client initialized successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8989 (Press CTRL+C to quit)
```

### Health Check

Validate the MCP server is running:

```bash
curl http://localhost:8989/health
```

**Expected Response:**

```json
{
  "status": "healthy",
  "service": "mcp-code-executor",
  "client_initialized": true
}
```

---

## Starting the Agent API

The Agent API provides an OpenAI-compatible chat completions endpoint that uses Google ADK agents with MCP tools.

### Command

```bash
cd agent_api
uv run python -m server
```

### Working Directory

**Must run from:** `agent_api/` directory

The Agent API uses relative imports and expects to be run from its own directory.

### Expected Port

**Default:** `8000`

The server runs on `http://localhost:8000`

### Startup Output

You should see:

```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
Starting Agent API server...
MCP Server URL: http://localhost:8989/mcp
Default Model: anthropic/claude-sonnet-4-5-20250929
AgentManager initialized with MCP server: http://localhost:8989/mcp
SessionStore initialized
Agent API server started successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Health Check

Validate the Agent API is running:

```bash
curl http://localhost:8000/health
```

**Expected Response (when MCP server is running):**

```json
{
  "status": "healthy",
  "service": "agent-api",
  "mcp_server_connected": true,
  "timestamp": "2025-11-28T12:34:56.789Z"
}
```

**Response (when MCP server is not running):**

```json
{
  "status": "degraded",
  "service": "agent-api",
  "mcp_server_connected": false,
  "timestamp": "2025-11-28T12:34:56.789Z"
}
```

---

## Quick Start: Running Both Servers

### Option 1: Two Terminal Windows

**Terminal 1 (MCP Server):**
```bash
cd mcp_server
uv run python -m server
```

**Terminal 2 (Agent API):**
```bash
cd agent_api
uv run python -m server
```

### Option 2: Background Processes

```bash
# Start MCP server in background
cd mcp_server
uv run python -m server &
MCP_PID=$!
cd ..

# Wait for MCP server to be ready
sleep 3

# Start Agent API in background
cd agent_api
uv run python -m server &
AGENT_PID=$!
cd ..

# Wait for both to be ready
sleep 3

# Validate both servers
curl http://localhost:8989/health
curl http://localhost:8000/health

# To stop later:
# kill $MCP_PID $AGENT_PID
```

---

## Testing the Integration

### 1. Check MCP Server Health

```bash
curl http://localhost:8989/health
```

Should return `"status": "healthy"`

### 2. Check Agent API Health

```bash
curl http://localhost:8000/health
```

Should return `"mcp_server_connected": true`

### 3. List Available Models

```bash
curl http://localhost:8000/v1/models
```

**Expected Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "anthropic/claude-sonnet-4-5-20250929",
      "object": "model",
      "created": 1732800000,
      "owned_by": "google"
    }
  ]
}
```

### 4. Test Chat Completion (Streaming)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-sonnet-4-5-20250929",
    "messages": [
      {"role": "user", "content": "Execute this Python code: print(2 + 2)"}
    ],
    "stream": true
  }'
```

You should see Server-Sent Events (SSE) streaming back the agent's response.

---

## Port Configuration

### Default Ports

| Service    | Port | Endpoint                      |
|------------|------|-------------------------------|
| MCP Server | 8989 | http://localhost:8989         |
| Agent API  | 8000 | http://localhost:8000         |

### Changing Ports

**MCP Server:** Edit `mcp_server/server.py` (line ~387):

```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8989)  # Change port here
```

**Agent API:** Edit `agent_api/config.py`:

```python
class Settings(BaseSettings):
    agent_api_port: int = 8000  # Change port here
```

Or set via environment variable:

```bash
export AGENT_API_PORT=9000
```

---

## Troubleshooting

### MCP Server Won't Start

**Problem:** `Docker client initialization failed`

**Solution:** Ensure Docker daemon is running:

```bash
docker ps
```

### Agent API Returns "degraded" Status

**Problem:** `"mcp_server_connected": false`

**Solution:**
1. Check MCP server is running: `curl http://localhost:8989/health`
2. Verify MCP server URL in `agent_api/config.py`:
   ```python
   mcp_server_url: str = "http://localhost:8989/mcp"
   ```

### Authentication Error

**Problem:** `Missing Anthropic API Key`

**Solution:** Set the API key:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Then restart the Agent API.

### Port Already in Use

**Problem:** `Address already in use`

**Solution:** Find and kill the process using the port:

```bash
# For port 8000
lsof -ti:8000 | xargs kill -9

# For port 8989
lsof -ti:8989 | xargs kill -9
```

---

## Stopping the Servers

### Graceful Shutdown

Press `Ctrl+C` in each terminal window.

### Force Kill

```bash
# Kill MCP server
pkill -f "python -m server" -9

# Or kill by port
lsof -ti:8989 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

---

## Architecture Overview

```
┌─────────────────┐
│  Client/User    │
└────────┬────────┘
         │ HTTP POST /v1/chat/completions
         ▼
┌─────────────────────────────┐
│     Agent API (Port 8000)   │
│                             │
│  • OpenAI-compatible API    │
│  • Google ADK Runner        │
│  • Session Management       │
│  • Prompt Caching (1hr TTL)│
└────────┬───────────────┬────┘
         │               │
         │ (startup)     │ (runtime)
         │ Fetch prompt  │ MCP tool calls
         ▼               ▼
┌─────────────────────────────┐
│   MCP Server (Port 8989)    │
│                             │
│  • Code execution tools     │
│  • Dynamic skill prompts    │
│  • Docker container mgmt    │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   Docker Containers         │
│   (Per-user isolation)      │
└─────────────────────────────┘
```
