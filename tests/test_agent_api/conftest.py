"""Pytest fixtures for Agent API tests."""

import subprocess
import time
from pathlib import Path

import httpx
import pytest
from openai import OpenAI


@pytest.fixture(scope="session", autouse=True)
def start_servers():
    """Start MCP server and Agent API server in background for all tests.

    This fixture automatically starts both servers before any tests run
    and cleans them up after all tests complete.
    """
    project_root = Path(__file__).parent.parent.parent
    mcp_process = None
    agent_api_process = None

    try:
        # Start MCP server from its directory (uses relative imports)
        print("\n🚀 Starting MCP server...")
        mcp_process = subprocess.Popen(
            ["uv", "run", "python", "-m", "server"],
            cwd=project_root / "mcp_server",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for MCP server to be ready
        mcp_ready = False
        for i in range(30):  # 30 second timeout
            try:
                response = httpx.get("http://localhost:8989/health", timeout=1.0)
                if response.status_code == 200:
                    print(f"✓ MCP server ready (PID: {mcp_process.pid})")
                    mcp_ready = True
                    break
            except Exception:
                pass
            time.sleep(1)

        if not mcp_ready:
            raise RuntimeError("MCP server failed to start within 30 seconds")

        # Start Agent API server from its directory (uses relative imports)
        print("🚀 Starting Agent API server...")
        agent_api_process = subprocess.Popen(
            ["uv", "run", "python", "-m", "server"],
            cwd=project_root / "agent_api",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for Agent API server to be ready
        api_ready = False
        for i in range(30):  # 30 second timeout
            try:
                response = httpx.get("http://localhost:8000/health", timeout=1.0)
                if response.status_code in [200, 503]:  # 503 is ok (degraded but running)
                    print(f"✓ Agent API server ready (PID: {agent_api_process.pid})")
                    api_ready = True
                    break
            except Exception:
                pass
            time.sleep(1)

        if not api_ready:
            raise RuntimeError("Agent API server failed to start within 30 seconds")

        print("✓ All servers ready for testing\n")

        # Yield control to tests
        yield

    finally:
        # Cleanup: Kill both servers
        print("\n🛑 Shutting down test servers...")

        if agent_api_process:
            print(f"  Stopping Agent API server (PID: {agent_api_process.pid})")
            agent_api_process.terminate()
            try:
                agent_api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent_api_process.kill()
                agent_api_process.wait()

        if mcp_process:
            print(f"  Stopping MCP server (PID: {mcp_process.pid})")
            mcp_process.terminate()
            try:
                mcp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mcp_process.kill()
                mcp_process.wait()

        print("✓ All servers stopped\n")


@pytest.fixture
def openai_client():
    """Create OpenAI client for testing Agent API."""
    return OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy"  # Not used but required by SDK
    )


@pytest.fixture
def test_model():
    """Default model for testing."""
    return "anthropic/claude-sonnet-4-5-20250929"
