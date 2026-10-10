import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server"))

import pytest
from fastmcp.client import Client as FastMCPClient

os.environ["MCP_EXECUTOR_IMAGE"] = "mcp-code-executor:latest"
os.environ["MCP_TOOLS_PATH"] = "tools"
os.environ["MCP_SKILLS_PATH"] = "skills"


@pytest.fixture
def test_user_id() -> str:
    return "test-user-123"


@pytest.fixture
async def mcp_client(test_user_id):
    import server

    def mock_get_user_id(ctx):
        return test_user_id

    with patch.object(server, "get_user_id", mock_get_user_id):
        async with FastMCPClient(transport=server.mcp) as client:
            yield client


@pytest.fixture(autouse=True)
async def cleanup_containers():
    yield

    import server

    if server.docker_client:
        server.docker_client.cleanup_all()
