#!/usr/bin/env python3
"""Demonstrate how .env values propagate through the system."""

import os
import sys
from pathlib import Path


def load_dotenv():
    """Load .env file into environment variables."""
    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        print(f"⚠️  .env file not found at {env_path}")
        return False

    # Simple .env parser (avoids dependency on python-dotenv)
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Set in environment
                os.environ[key] = value

    return True


def test_config_loading():
    """Show how .env values get loaded and used."""

    print("=" * 70)
    print("Configuration Loading Test")
    print("=" * 70)
    print()

    # Step 0: Load .env file into environment
    print("STEP 0: Loading .env File")
    print("-" * 70)
    if load_dotenv():
        print("  ✓ .env file loaded into environment variables")
    else:
        print("  ✗ Failed to load .env file")
        return False
    print()

    # Step 1: Show raw environment variables (after loading .env)
    print("STEP 1: Raw Environment Variables (from .env)")
    print("-" * 70)
    env_vars = [
        "ANTHROPIC_API_KEY",
        "DEFAULT_MODEL",
        "AGENT_API_HOST",
        "AGENT_API_PORT",
        "MCP_SERVER_URL",
        "SESSION_TIMEOUT_SECONDS",
    ]

    for var in env_vars:
        value = os.getenv(var, "NOT SET")
        # Mask API keys
        if "API_KEY" in var and value != "NOT SET":
            value = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
        print(f"  {var:30} = {value}")

    print()

    # Step 2: Import settings (this triggers .env loading)
    print("STEP 2: Importing settings from agent_api.config")
    print("-" * 70)
    print("  Executing: from agent_api.config import settings")

    try:
        from agent_api.config import settings

        print("  ✓ Settings imported successfully")
    except Exception as e:
        print(f"  ✗ Failed to import settings: {e}")
        return False

    print()

    # Step 3: Show Pydantic settings object
    print("STEP 3: Pydantic Settings Object Values")
    print("-" * 70)
    print(f"  settings.agent_api_host         = {settings.agent_api_host}")
    print(f"  settings.agent_api_port         = {settings.agent_api_port}")
    print(f"  settings.mcp_server_url         = {settings.mcp_server_url}")
    print(f"  settings.default_model          = {settings.default_model}")
    print(f"  settings.agent_name             = {settings.agent_name}")
    print(f"  settings.session_timeout_seconds = {settings.session_timeout_seconds}")

    print()

    # Step 4: Show how these values would be used
    print("STEP 4: How Values Are Used in Code")
    print("-" * 70)

    print("\n  In agent_api/server.py:")
    print(f"    AgentManager(mcp_server_url='{settings.mcp_server_url}')")
    print(f"    logger.info('Default Model: {settings.default_model}')")

    print("\n  In agent_api/agent_manager.py:")
    print(f"    model = LiteLlm(model='{settings.default_model}')")
    print(f"    agent = Agent(name='{settings.agent_name}', ...)")

    print()

    # Step 5: Verify API key in environment
    print("STEP 5: API Key Availability for LiteLLM")
    print("-" * 70)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        masked = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
        print(f"  ✓ ANTHROPIC_API_KEY found in environment: {masked}")
        print("  → LiteLLM will use this key automatically")
    else:
        print("  ✗ ANTHROPIC_API_KEY not found in environment")
        print("  → LiteLLM will fail when trying to use Anthropic models")

    print()

    # Step 6: Summary
    print("=" * 70)
    print("SUMMARY: How .env Values Propagate")
    print("=" * 70)
    print()
    print("TWO PARALLEL PATHS:")
    print()
    print("Path 1: For Agent API Configuration")
    print("  .env file → Pydantic BaseSettings → settings object")
    print("  - Pydantic reads .env automatically when Settings() is created")
    print("  - Values available as: settings.agent_api_port, settings.default_model, etc.")
    print("  - Used by: server.py, agent_manager.py, session_store.py")
    print()
    print("Path 2: For API Keys (LiteLLM)")
    print("  .env file → os.environ → LiteLLM")
    print("  - Need to manually load .env (or use python-dotenv)")
    print("  - API keys read from os.environ by LiteLLM")
    print("  - Used by: LiteLlm() when creating model")
    print()
    print("IMPORTANT: Pydantic does NOT set os.environ!")
    print("  - settings.default_model works ✓")
    print("  - os.getenv('DEFAULT_MODEL') may not work ✗ (unless manually loaded)")
    print()
    print("All .env values are now available throughout the application!")
    print()

    return True


if __name__ == "__main__":
    # Make sure we can import from agent_api
    sys.path.insert(0, "/Users/mohardey/Projects/code-execution-with-mcp")

    success = test_config_loading()
    sys.exit(0 if success else 1)
