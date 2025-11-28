# Gradio UI for Code Execution with MCP

An interactive web interface for the Code Execution with MCP platform, providing real-time visualization of AI agent reasoning, tool calls, and Docker container operations.

## Features

### 🎨 Visual Design
- **Modern gradient header** with project branding
- **Color-coded activity monitoring** showing tool calls, Docker operations, and reasoning steps
- **Responsive layout** that works on desktop and mobile
- **Real-time streaming** of agent responses and activities

### 📊 Real-Time Monitoring
- **Agent Reasoning Display**: Watch the AI agent think through problems
- **Tool Call Visualization**: See which MCP tools are being invoked with their arguments
- **Docker Container Tracking**: Monitor container creation, command execution, and file operations
- **Execution Status**: Real-time status updates with success/error indicators

### 🔍 Activity Log Components

The UI displays different types of activities with distinct visual styling:

1. **Tool Calls** (Blue) - Shows when the agent uses MCP tools
   - Tool name and arguments
   - Formatted JSON display
   - Truncated long values for readability

2. **Docker Actions** (Purple) - Container-level operations
   - Container initialization
   - Command execution
   - File operations

3. **Reasoning Steps** (Orange) - Agent's thought process
   - Problem analysis
   - Strategy planning
   - Result interpretation

4. **Status Updates** (Green/Red) - Execution results
   - Success indicators
   - Error messages
   - Completion notifications

### 🛡️ System Health Monitoring
- **Agent API Status**: Connection and health check
- **MCP Server Status**: Backend service availability
- **Live refresh**: Update status on demand

### 👤 User Session Management
- **Unique user IDs**: Each session gets isolated container
- **Session persistence**: Continue conversations across multiple requests
- **Easy reset**: Generate new session ID anytime

### 💡 Example Queries
Pre-configured examples to help users get started:
- Python scripting
- Data visualization
- Symbolic mathematics
- Bash operations
- Statistical analysis

## Architecture

### Communication Flow
```
┌─────────────────┐
│   Gradio UI     │
│  (Port 7860)    │
└────────┬────────┘
         │ HTTP/SSE
         ▼
┌─────────────────┐
│   Agent API     │
│  (Port 8000)    │
└────────┬────────┘
         │ MCP Protocol
         ▼
┌─────────────────┐
│   MCP Server    │
│  (Port 8989)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Docker Executor │
└─────────────────┘
```

### Data Flow
1. User enters message in Gradio UI
2. UI calls Agent API via OpenAI SDK
3. Agent API streams back SSE events
4. UI parses events and updates:
   - Chat history (agent responses)
   - Activity log (tool calls, Docker actions)
5. Real-time updates display in parallel columns

## Installation & Setup

### Prerequisites
- Python 3.12+
- Running Agent API (port 8000)
- Running MCP Server (port 8989)
- Docker daemon running

### Install Dependencies

The Gradio UI uses the same virtual environment as the main project:

```bash
cd /Users/mohardey/Projects/code-execution-with-mcp

# Dependencies should already be installed
# If not, run:
uv sync
```

### Configuration

The UI connects to:
- **Agent API**: `http://localhost:8000` (configurable in app.py)
- **MCP Server**: `http://localhost:8989` (for health checks)

To modify these URLs, edit the constants at the top of `app.py`:

```python
AGENT_API_URL = "http://localhost:8000"
MCP_SERVER_URL = "http://localhost:8989"
```

## Running the UI

### Option 1: Run Directly

```bash
cd /Users/mohardey/Projects/code-execution-with-mcp

# Activate virtual environment
source .venv/bin/activate

# Run the Gradio app
python gradio_ui/app.py
```

The UI will be available at `http://localhost:7860`

### Option 2: Full System Startup

Start all components in separate terminals:

**Terminal 1 - MCP Server:**
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python -m mcp_server.server
# Runs on http://0.0.0.0:8989
```

**Terminal 2 - Agent API:**
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python -m agent_api.server
# Runs on http://0.0.0.0:8000
```

**Terminal 3 - Gradio UI:**
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python gradio_ui/app.py
# Runs on http://0.0.0.0:7860
```

### Option 3: Using Docker Image

First, ensure the Docker image is built:

```bash
cd mcp_server/docker
./build.sh
```

This builds the `code-executor:latest` image that the MCP server uses.

## Usage

### Basic Chat

1. Open `http://localhost:7860` in your browser
2. Check the **System Status** panel (should show green indicators)
3. Type your message or select an example
4. Click **Send** or press Enter
5. Watch the activity log for real-time updates

### Monitoring Agent Activity

The **Agent Activity Monitor** panel shows:

- **🔧 Tool Calls**: When the agent uses tools like `execute_bash`, `write_file`, etc.
- **🐳 Docker Actions**: Container operations (initialization, command execution)
- **🤔 Reasoning Steps**: Agent's thought process
- **✅ Status Updates**: Success/error indicators

### Example Workflow

**Request:** "Write a Python script to calculate factorial of 10"

**Activity Log Shows:**
1. 🐳 Docker: Initializing container (User: user-abc123)
2. 🔧 Tool Call: `write_file`
   - `file_path`: `/workspace/factorial.py`
   - `content`: [Python code]
3. 🐳 Docker: Writing file (Path: `/workspace/factorial.py`)
4. 🔧 Tool Call: `execute_bash`
   - `command`: `python /workspace/factorial.py`
5. 🐳 Docker: Executing command
6. ✅ Completed

### Managing Sessions

- **Current Session**: Shows your unique user ID
- **New Session**: Click to generate a new ID and start fresh
- Each session gets its own Docker container
- Old containers are cleaned up automatically

## Customization

### Styling

The UI uses custom CSS defined in `CUSTOM_CSS`. Key classes:

- `.header` - Main header with gradient
- `.info-box` - Information panels
- `.tool-call` - Tool call display (blue)
- `.docker-info` - Docker actions (purple)
- `.reasoning-step` - Agent reasoning (orange)
- `.code-block` - Code snippets (dark theme)

To customize, edit the CSS in `app.py`.

### Adding Examples

Add new examples to the `gr.Examples` component:

```python
gr.Examples(
    examples=[
        ["Your new example query here"],
        # ... existing examples
    ],
    inputs=msg_input
)
```

### Modifying Layout

The layout uses Gradio's `Blocks` API:
- `gr.Row()` - Horizontal layout
- `gr.Column(scale=N)` - Vertical layout with width ratio
- `gr.Markdown()` - Formatted text
- `gr.HTML()` - Custom HTML content

## API Integration

### OpenAI SDK

The UI uses the official OpenAI Python SDK to communicate with the Agent API:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url=f"{AGENT_API_URL}/v1",
    api_key="dummy"
)

stream = await client.chat.completions.create(
    model="gemini-2.0-flash-exp",
    messages=[{"role": "user", "content": message}],
    stream=True,
    user=user_id
)
```

### Event Parsing

The UI parses Server-Sent Events (SSE) from the Agent API:

- **Content deltas**: Agent's response text
- **Tool calls**: Function name and arguments
- **Finish reasons**: Completion status

### Health Checks

The UI performs async health checks:

```python
async def check_health() -> dict:
    # Check Agent API
    GET /health

    # Check MCP Server
    GET /health

    # Return status for both
```

## Troubleshooting

### UI Won't Start

**Error:** `ModuleNotFoundError: No module named 'gradio'`

**Solution:**
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv sync
```

### Connection Errors

**Symptom:** Red indicators in System Status

**Solutions:**
1. Ensure MCP Server is running on port 8989
2. Ensure Agent API is running on port 8000
3. Check Docker daemon is running
4. Verify no firewall blocking localhost connections

### No Activity in Monitor

**Symptom:** Activity log stays empty during chat

**Possible Causes:**
1. Agent API not streaming events correctly
2. OpenAI SDK version mismatch
3. Browser blocking SSE connections

**Solutions:**
1. Check browser console for errors
2. Verify Agent API logs show streaming
3. Try different browser

### Docker Container Issues

**Symptom:** Error messages about container operations

**Solutions:**
1. Ensure Docker daemon is running: `docker ps`
2. Check Docker image exists: `docker images | grep code-executor`
3. Rebuild image: `cd mcp_server/docker && ./build.sh`
4. Check MCP server logs for detailed errors

## Development

### Adding New Features

1. **New Activity Type:**
   - Add formatting function (e.g., `format_new_type()`)
   - Add CSS class for styling
   - Parse events and call formatter in `chat_with_agent()`

2. **New Status Indicator:**
   - Add check in `check_health()`
   - Update `format_health_status()` to display
   - Add to UI health panel

3. **New Tool Visualization:**
   - Detect tool name in `chat_with_agent()`
   - Extract relevant arguments
   - Call `format_docker_action()` or custom formatter

### Code Structure

```
gradio_ui/
├── app.py              # Main application
│   ├── Configuration   # API URLs, constants
│   ├── CSS Styling     # Custom themes
│   ├── Health Checks   # Status monitoring
│   ├── Event Parsing   # SSE handling
│   ├── Formatters      # Activity display
│   ├── Chat Handler    # Main streaming logic
│   └── UI Layout       # Gradio components
└── README.md           # This file
```

### Async Patterns

The UI uses async/await for non-blocking operations:

```python
async def chat_with_agent(...) -> AsyncIterator[...]:
    # Stream events from Agent API
    async for chunk in stream:
        # Parse and format
        yield history, response, activity_log
```

This allows real-time updates without blocking the UI.

## Performance Considerations

### Streaming Optimization
- Uses Gradio's built-in queue system
- Async generators prevent blocking
- Incremental HTML updates minimize re-renders

### Memory Management
- Tool calls buffer cleaned per message
- Activity log resets on new session
- No persistent storage (stateless)

### Network Efficiency
- SSE connection reused during chat
- Health checks cached briefly
- Minimal data in each update

## Security Notes

### API Keys
- Agent API doesn't require real authentication (dummy key used)
- Not suitable for production without adding auth

### User Isolation
- Each user ID gets isolated Docker container
- No cross-user data access
- Containers cleaned up on shutdown

### Input Validation
- User messages passed directly to agent
- Agent responsible for safe code execution
- Docker provides isolation layer

## Future Enhancements

Potential features for future versions:

- [ ] File upload/download from containers
- [ ] Artifact viewer for generated files
- [ ] Execution history and replay
- [ ] Multi-user authentication
- [ ] Container resource monitoring
- [ ] Custom skill selection
- [ ] Code syntax highlighting in chat
- [ ] Export conversation history
- [ ] Dark mode toggle
- [ ] Configurable timeout settings

## License

This project is part of the Code Execution with MCP platform.

## Credits

- **Team**: Mohar Dey, Jonathan Kadowaki
- **Technologies**: Gradio, FastAPI, Google ADK, FastMCP, Docker
- **Event**: Built for MCP 1st Birthday Hackathon

## Support

For issues or questions:
1. Check logs in terminal running the UI
2. Verify all services are healthy
3. Check Docker container status
4. Review Agent API and MCP Server logs

---

**Built with ❤️ for the MCP 1st Birthday Hackathon**