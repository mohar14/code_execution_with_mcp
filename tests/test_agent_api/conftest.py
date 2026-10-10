import pytest
from openai import OpenAI


@pytest.fixture
def openai_client():
    return OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy",
    )


@pytest.fixture
def test_model():
    return "anthropic/claude-sonnet-4-5-20250929"
