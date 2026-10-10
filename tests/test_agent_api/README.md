# Agent API Tests

Integration tests; they need live servers, so they cannot run offline.

Prerequisites: Docker daemon running, API key in `.env`, and both servers up
(from the repo root, each in its own terminal):

```bash
uv run python -m mcp_server.server   # port 8989
uv run python -m agent_api.server    # port 8000
```

Then run:

```bash
uv run pytest tests/test_agent_api/ -v                  # all
uv run pytest tests/test_agent_api/test_server.py::TestChatCompletions -v   # one class
uv run pytest tests/test_agent_api/ -v -s               # show prints
```
