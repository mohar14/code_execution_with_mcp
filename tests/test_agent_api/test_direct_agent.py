"""Direct test to see all agent output including errors."""

import asyncio

import httpx


async def test_agent():
    """Test agent and print all logs."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "=" * 80)
        print("Sending request to agent...")
        print("=" * 80)

        async with client.stream(
            "POST",
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Execute this Python code: print(2 + 2)"}],
                "stream": True,
            },
        ) as response:
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print("\nResponse chunks:")
            print("-" * 80)

            full_response = ""
            async for line in response.aiter_lines():
                if line.strip():
                    print(f"CHUNK: {line}")
                    if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                        import json

                        try:
                            data = json.loads(line[6:])
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    full_response += delta["content"]
                        except:
                            pass

            print("-" * 80)
            print(f"\nFull response:\n{full_response}")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_agent())
