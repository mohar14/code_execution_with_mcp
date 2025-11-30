"""Pytest fixtures for Agent API tests."""

import pytest
from openai import OpenAI


@pytest.fixture
def openai_client():
    """Create OpenAI client for testing Agent API."""
    return OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy",  # Not used but required by SDK
    )


@pytest.fixture
def test_model():
    """Default model for testing."""
    return "anthropic/claude-sonnet-4-5-20250929"
