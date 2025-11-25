"""Pytest configuration and fixtures for MCP server tests."""

import os
import sys

# Add project root to path to import our mcp_server module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server"))

import pytest
from fastmcp.client import Client as FastMCPClient

# Set test environment variables
os.environ["MCP_EXECUTOR_IMAGE"] = "mcp-code-executor:latest"
os.environ["MCP_TOOLS_PATH"] = "tools"
os.environ["MCP_SKILLS_PATH"] = "skills"


@pytest.fixture
async def mcp_client(test_user_id, monkeypatch):
    """Create a test client for the MCP server.

    This fixture wraps the FastMCP server in a Client instance
    for testing, following FastMCP testing patterns.
    """
    # Import the FastMCP app from our server module
    import server

    # Monkey patch the get_user_id function to return test user ID
    def mock_get_user_id(ctx):
        return test_user_id

    monkeypatch.setattr(server, "get_user_id", mock_get_user_id)

    async with FastMCPClient(transport=server.mcp) as client:
        yield client


@pytest.fixture
def test_user_id() -> str:
    """Fixture providing a test user ID."""
    return "test-user-123"


@pytest.fixture(autouse=True)
async def cleanup_containers():
    """Cleanup all containers after tests."""
    yield

    # Cleanup after tests complete
    import server
    if server.docker_client:
        server.docker_client.cleanup_all()
