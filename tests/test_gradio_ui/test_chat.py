#!/usr/bin/env python3
"""Test script to verify Gradio UI chat functionality."""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set PYTHONPATH
os.environ['PYTHONPATH'] = str(PROJECT_ROOT)

from openai import AsyncOpenAI
import httpx
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")


async def test_chat():
    """Test chat functionality with simple query."""

    # Get configured model from environment
    model = os.getenv("DEFAULT_MODEL", "claude-sonnet-4-5")
    print(f"Using model: {model}")

    # Wait for services to be ready
    print("Waiting for Agent API to be ready...")
    max_wait = 30
    elapsed = 0
    agent_ready = False

    while elapsed < max_wait:
        try:
            response = httpx.get("http://localhost:8000/health", timeout=2.0)
            if response.status_code == 200:
                agent_ready = True
                print(f"✅ Agent API ready after {elapsed}s")
                break
        except:
            pass

        time.sleep(1)
        elapsed += 1

    if not agent_ready:
        print("❌ Agent API not ready")
        return False

    # Initialize OpenAI client
    client = AsyncOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy"
    )

    # Test query
    print("\n📝 Sending test query: 'Write a Python script that prints hello world'")

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Write a Python script that prints hello world"}],
            stream=True,
            user="test_user"
        )

        tool_calls_seen = []
        content_chunks = []

        async for chunk in stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # Track content
            if delta.content:
                content_chunks.append(delta.content)
                print(f"📨 Content: {delta.content[:50]}...")

            # Track tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    if tool_call.function and tool_call.function.name:
                        tool_name = tool_call.function.name
                        if tool_name not in tool_calls_seen:
                            tool_calls_seen.append(tool_name)
                            print(f"🔧 Tool Call: {tool_name}")

                        if tool_call.function.arguments:
                            print(f"   Args chunk: {tool_call.function.arguments[:50]}...")

            # Track finish
            if choice.finish_reason:
                print(f"🏁 Finish reason: {choice.finish_reason}")

        print(f"\n✅ Test completed!")
        print(f"   Tool calls seen: {tool_calls_seen}")
        print(f"   Content chunks: {len(content_chunks)}")
        print(f"   Total content length: {sum(len(c) for c in content_chunks)}")

        return True

    except Exception as e:
        print(f"❌ Error during chat: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_chat())
    sys.exit(0 if result else 1)
