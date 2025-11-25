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

![Architecture Diagram](docs/architecture.png)

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

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
