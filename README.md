---
title: Code Execution With Mcp
emoji: 🐨
colorFrom: gray
colorTo: red
sdk: gradio
sdk_version: 6.0.0
app_file: app.py
pinned: false
---

# Code Execution with MCP

A secure, containerized code execution platform for AI agents with multi-user isolation, skills discovery, and a Gradio frontend.

**Team Members:**
- **Mohar Dey** - [@mohar1406](https://huggingface.co/mohar1406) - Lead Developer
- **Jonathan Kadowaki** - [@jkadowak](https://huggingface.co/jkadowak) - Lead Developer

## Architecture

![Architecture Diagram](https://huggingface.co/spaces/MCP-1st-Birthday/code-execution-with-mcp/blob/refs%2Fpr%2F2/docs/architecture.png)

<details>
<summary>View/Edit Diagram Source</summary>

The diagram source is maintained in [generate_diagram.py](generate_diagram.py). To regenerate the diagram after making changes:

```bash
python3 generate_diagram.py
```

</details>

## Key Features

### Security & Isolation
- **Per-user Docker containers**: Each user gets an isolated execution environment
- **Read-only tool/skill mounts**: Prevents modification of shared resources
- **Non-root execution**: Code runs as unprivileged `coderunner` user
- **Workspace isolation**: Users can only access their own `/workspace` directory

### Code Execution
- **Async execution**: Non-blocking command execution with timeout support
- **File operations**: Read and write files within user containers
- **Tool introspection**: Dynamic docstring retrieval for skill discovery

### Agent Integration
- **MCP Protocol**: Standard Model Context Protocol for tool exposure
- **Google ADK**: Agent reasoning loop with streaming support
- **OpenAI-compatible API**: Easy integration with existing AI workflows

### User Experience
- **Gradio frontend**: Interactive chat interface with authentication
- **Real-time streaming**: See agent responses and tool use in real-time
- **Artifact management**: Browse and examine generated files

## Container Lifecycle
- Containers are created on first use per user
- Containers persist across requests for the same user
- Stopped containers are automatically restarted when needed
- All containers are cleaned up on server shutdown

## Quick Start

### One-Command Launch (Recommended)

The Gradio UI automatically starts all required services:

```bash
cd /Users/mohardey/Projects/code-execution-with-mcp

# Build Docker image (first time only)
cd mcp_server/docker && ./build.sh && cd ../..

# Start everything with one command
uv run python gradio_ui/app.py
```

This will:
1. ✅ Start MCP Server (port 8989)
2. ✅ Start Agent API (port 8000)
3. ✅ Launch Gradio UI (port 7860)
4. ✅ Open at http://localhost:7860

**Stop with Ctrl+C** - all services shut down automatically!

For detailed instructions, see [Gradio UI Quick Start](gradio_ui/QUICKSTART.md).

### Manual Service Control

If you prefer to run services separately:

**Terminal 1 - MCP Server:**
```bash
uv run python -m mcp_server.server  # Port 8989
```

**Terminal 2 - Agent API:**
```bash
uv run python -m agent_api.server   # Port 8000
```

**Terminal 3 - Gradio UI:**
```bash
# Comment out initialize_services() in gradio_ui/app.py first
uv run python gradio_ui/app.py      # Port 7860
```

## Documentation

- **[Gradio UI Quick Start](gradio_ui/QUICKSTART.md)** - Complete setup and usage guide
- **[Gradio UI README](gradio_ui/README.md)** - Features and architecture
- **[Implementation Overview](claude_spec/IMPLEMENTATION_OVERVIEW.md)** - System architecture
- **[MCP Server README](mcp_server/README.md)** - MCP server details
- **[Agent API README](agent_api/README.md)** - Agent API details

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
