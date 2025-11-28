"""Configuration management for Agent API."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for the Agent API."""

    # API Server
    agent_api_host: str = "0.0.0.0"
    agent_api_port: int = 8000

    # MCP Server Connection
    mcp_server_url: str = "http://localhost:8989/mcp"
    mcp_server_health_endpoint: str = "http://localhost:8989/health"

    # LiteLLM Model Configuration
    default_model: str = "anthropic/claude-sonnet-4-5-20250929"
    # Supported models (LiteLLM format):
    # - OpenAI: "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"
    # - Anthropic: "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"
    # - Google: "gemini/gemini-2.0-flash-exp", "gemini/gemini-1.5-pro"
    # - Add API keys in environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)

    # Agent Configuration
    agent_name: str = "code_executor_agent"
    system_prompt: str = """You are a code execution assistant with access to secure Docker containers.

You can:
- Execute bash commands and Python scripts
- Write files to the workspace
- Read file contents with pagination
- Inspect function documentation

Guidelines:
- Always validate user code before execution
- Use appropriate timeouts for long-running tasks
- Handle errors gracefully and provide clear feedback
- Keep the workspace organized

Available tools:
- execute_bash: Run commands in isolated container
- write_file: Create/overwrite files in workspace
- read_file: Read file contents (supports pagination)
- read_docstring: Extract function documentation

Be helpful, secure, and efficient!"""

    # Session Management
    session_timeout_seconds: int = 3600  # 1 hour

    # LiteLLM Settings
    litellm_drop_params: bool = True  # Drop unsupported params for each provider
    litellm_max_tokens: int = 4096
    litellm_temperature: float = 0.7

    class Config:
        env_file = ".env"
        extra = "ignore"

    def get_model_owner(self) -> str:
        default_owner = "unknown"
        if not self.default_model:
            return default_owner

        try:
            owner, _ = self.default_model.split("/", 1)
        except:
            owner = default_owner

        if owner:
            return owner
        return default_owner


settings = Settings()
