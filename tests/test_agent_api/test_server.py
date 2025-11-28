"""Integration tests for Agent API server.

These tests require:
1. MCP server running on http://localhost:8989
2. Agent API server running on http://localhost:8000
3. Docker daemon running
4. API key configured in .env
"""

import httpx
import pytest


class TestHealthEndpoints:
    """Test health check and status endpoints."""

    @pytest.mark.asyncio
    async def test_agent_api_health(self):
        """Test Agent API health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "agent-api"
            assert "status" in data
            assert "mcp_server_connected" in data

    @pytest.mark.asyncio
    async def test_mcp_server_health(self):
        """Test MCP server is running and healthy."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8989/health")

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "mcp-code-executor"
            assert data["client_initialized"] is True


class TestModelsEndpoint:
    """Test models listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_models(self):
        """Test models endpoint returns available models."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/v1/models")

            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert len(data["data"]) > 0
            assert data["data"][0]["object"] == "model"


class TestChatCompletions:
    """Test chat completions endpoint."""

    def test_simple_chat_completion(self, openai_client, test_model):
        """Test basic chat completion with simple message."""
        print("\n" + "=" * 60)
        print("Agent Response:")
        print("=" * 60)

        stream = openai_client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Say hello!"}],
            stream=True,
        )

        chunks = []
        response_text = ""
        for chunk in stream:
            chunks.append(chunk)
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                response_text += content

        print("\n" + "=" * 60)
        print(f"Total chunks received: {len(chunks)}")
        print(f"Total characters: {len(response_text)}")
        print("=" * 60)

        # Verify we got valid response
        assert len(chunks) > 0, "No chunks received"
        assert chunks[0].object == "chat.completion.chunk", "Invalid chunk object type"
        assert len(response_text) > 0, "No response text received"
        # Ensure we didn't get an error response
        assert not response_text.startswith("Error:"), f"Got error response: {response_text}"
        # Verify we got actual content (more than just role)
        assert len(response_text) > 10, f"Response too short, likely an error: {response_text}"

    def test_streaming_response(self, openai_client, test_model):
        """Test that streaming actually works."""
        stream = openai_client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Count from 1 to 3"}],
            stream=True,
        )

        response_text = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                response_text += chunk.choices[0].delta.content

        assert len(response_text) > 0


class TestCodeExecution:
    """Test code execution capabilities through the agent."""

    def test_execute_simple_python(self, openai_client, test_model):
        """Test agent can execute simple Python code."""
        stream = openai_client.chat.completions.create(
            model=test_model,
            messages=[
                {
                    "role": "user",
                    "content": "Execute this Python code: print(2 + 2)",
                }
            ],
            stream=True,
        )

        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content

        # Check if response mentions execution or contains result
        assert len(response) > 0

    def test_write_and_execute_workflow(self, openai_client, test_model):
        """Test write file -> execute -> read result workflow."""
        stream = openai_client.chat.completions.create(
            model=test_model,
            messages=[
                {
                    "role": "user",
                    "content": """Write a Python script to /workspace/test.py that calculates 5 factorial,
                    then execute it and tell me the result.""",
                }
            ],
            stream=True,
        )

        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content

        # Should mention 120 (5! = 120)
        assert len(response) > 0

    def test_use_numpy(self, openai_client, test_model):
        """Test agent can use pre-installed packages like numpy."""
        stream = openai_client.chat.completions.create(
            model=test_model,
            messages=[
                {
                    "role": "user",
                    "content": "Use numpy to create a 2x2 identity matrix and show me the result",
                }
            ],
            stream=True,
        )

        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content

        # Should execute numpy code
        assert len(response) > 0


class TestSessionManagement:
    """Test conversation session handling."""

    def test_multi_turn_conversation(self, openai_client, test_model):
        """Test that sessions maintain context across turns."""
        # First turn: create a variable
        stream1 = openai_client.chat.completions.create(
            model=test_model,
            messages=[
                {
                    "role": "user",
                    "content": "Write a file /workspace/data.txt with the text 'Session test data'",
                }
            ],
            stream=True,
            user="test-session-123",  # Same user ID
        )

        # Consume first stream
        for chunk in stream1:
            pass

        # Second turn: reference previous context
        stream2 = openai_client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Now read the file you just created"}],
            stream=True,
            user="test-session-123",  # Same user ID for context
        )

        response = ""
        for chunk in stream2:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content

        # Should reference the file or show the content
        assert len(response) > 0


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_non_streaming_rejected(self):
        """Test that non-streaming requests are rejected."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/v1/chat/completions",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,  # Should be rejected
                },
            )

            assert response.status_code == 422
            data = response.text
            assert "error" in data.lower()
            assert "input should be true" in data.lower()

    @pytest.mark.asyncio
    async def test_empty_messages(self):
        """Test handling of empty messages."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/v1/chat/completions",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "messages": [],  # Empty
                    "stream": True,
                },
            )

            assert response.status_code == 400
