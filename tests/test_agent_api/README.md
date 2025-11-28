# Agent API Tests

Integration tests for the Agent API server.

## Prerequisites

Before running tests, you must have:

1. **Docker daemon running**
2. **MCP server running** on port 8989
3. **Agent API server running** on port 8000
4. **API key configured** in `.env`

## Starting the Servers

### Terminal 1: MCP Server
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python -m mcp_server.server
```

### Terminal 2: Agent API Server
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
uv run python -m agent_api.server
```

## Running Tests

### Terminal 3: Run Tests

```bash
cd /Users/mohardey/Projects/code-execution-with-mcp

# Run all Agent API tests
uv run pytest tests/test_agent_api/ -v

# Run specific test class
uv run pytest tests/test_agent_api/test_server.py::TestChatCompletions -v

# Run with output capture disabled (see print statements)
uv run pytest tests/test_agent_api/ -v -s

# Run specific test
uv run pytest tests/test_agent_api/test_server.py::TestChatCompletions::test_simple_chat_completion -v
```

## Test Structure

```
tests/test_agent_api/
├── __init__.py          # Package marker
├── conftest.py          # Pytest fixtures
├── test_server.py       # Integration tests
└── README.md            # This file
```

## Test Classes

### 1. TestHealthEndpoints
- `test_agent_api_health()` - Agent API health check
- `test_mcp_server_health()` - MCP server connectivity

### 2. TestModelsEndpoint
- `test_list_models()` - Models listing endpoint

### 3. TestChatCompletions
- `test_simple_chat_completion()` - Basic chat
- `test_streaming_response()` - Streaming works

### 4. TestCodeExecution
- `test_execute_simple_python()` - Execute Python code
- `test_write_and_execute_workflow()` - Multi-step workflow
- `test_use_numpy()` - Pre-installed packages

### 5. TestSessionManagement
- `test_multi_turn_conversation()` - Context preservation

### 6. TestErrorHandling
- `test_non_streaming_rejected()` - Error cases
- `test_empty_messages()` - Invalid requests

## Quick Health Check

Before running full test suite, check if servers are ready:

```bash
# Check MCP server
curl http://localhost:8989/health

# Check Agent API
curl http://localhost:8000/health

# List models
curl http://localhost:8000/v1/models
```

## Troubleshooting

### "Connection refused" errors
- Make sure both servers are running
- Check ports 8000 and 8989 are not in use

### "API key not found" errors
- Check `.env` file has ANTHROPIC_API_KEY
- Restart Agent API server after changing .env

### "Docker not running" errors
- Start Docker daemon
- Check: `docker ps`

### Tests hang or timeout
- Some tests execute real code, may take 10-30 seconds
- Use `-v` flag to see progress

## Expected Output

```
tests/test_agent_api/test_server.py::TestHealthEndpoints::test_agent_api_health PASSED
tests/test_agent_api/test_server.py::TestHealthEndpoints::test_mcp_server_health PASSED
tests/test_agent_api/test_server.py::TestModelsEndpoint::test_list_models PASSED
tests/test_agent_api/test_server.py::TestChatCompletions::test_simple_chat_completion PASSED
tests/test_agent_api/test_server.py::TestChatCompletions::test_streaming_response PASSED
tests/test_agent_api/test_server.py::TestCodeExecution::test_execute_simple_python PASSED
tests/test_agent_api/test_server.py::TestCodeExecution::test_write_and_execute_workflow PASSED
tests/test_agent_api/test_server.py::TestCodeExecution::test_use_numpy PASSED
tests/test_agent_api/test_server.py::TestSessionManagement::test_multi_turn_conversation PASSED
tests/test_agent_api/test_server.py::TestErrorHandling::test_non_streaming_rejected PASSED
tests/test_agent_api/test_server.py::TestErrorHandling::test_empty_messages PASSED

======================== 11 passed in ~45s ========================
```

## Notes

- Tests use the OpenAI Python SDK to test compatibility
- Each test is independent and can run standalone
- Tests create temporary files in `/workspace/` in containers
- User isolation is tested with unique user IDs
