"""Google ADK Agent lifecycle management with LiteLLM support for Agent API."""

import logging

from google.adk import Agent, Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from agent_api.config import settings

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages Google ADK Agent and Runner instances for users."""

    def __init__(self, mcp_server_url: str):
        """Initialize the agent manager.

        Args:
            mcp_server_url: URL of the MCP server to connect to
        """
        self.mcp_server_url = mcp_server_url
        self.runners: dict[str, Runner] = {}  # user_id -> Runner
        logger.info(f"AgentManager initialized with MCP server: {mcp_server_url}")

    def _create_mcp_toolset(self, user_id: str) -> McpToolset:
        """Create MCP toolset with per-user routing.

        Args:
            user_id: User identifier for routing requests to correct container

        Returns:
            Configured MCP toolset
        """
        logger.debug(f"Creating MCP toolset for user {user_id}")

        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=self.mcp_server_url,
            ),
            header_provider=lambda ctx: {"x-user-id": user_id},
        )

    def _get_instruction_prompt(self) -> str:
        """Get agent instruction/system prompt.

        Returns:
            System prompt for the agent
        """
        return """You are a code execution assistant with access to secure Docker containers.

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

    def _create_agent(self, user_id: str) -> Agent:
        """Create Google ADK agent with MCP tools and LiteLLM model routing.

        Args:
            user_id: User identifier

        Returns:
            Configured Google ADK Agent
        """
        logger.info(f"Creating agent for user {user_id} with model {settings.default_model}")
        toolset = self._create_mcp_toolset(user_id)

        # Use LiteLLM wrapper for multi-provider support
        # LiteLLM supports: OpenAI, Anthropic, Google, Cohere, etc.
        # Model format: "provider/model" (e.g., "openai/gpt-4", "anthropic/claude-3-sonnet")
        # For Gemini: "gemini/gemini-2.0-flash-exp" or just "gemini-2.0-flash-exp"
        model = LiteLlm(model=settings.default_model)

        agent = Agent(
            model=model,
            name=settings.agent_name,
            instruction=settings.system_prompt,
            tools=[toolset],
        )

        return agent

    def get_or_create_runner(
        self, user_id: str, session_service: InMemorySessionService
    ) -> Runner:
        """Get existing runner or create new one for user.

        Args:
            user_id: User identifier
            session_service: Session service for conversation history

        Returns:
            Google ADK Runner instance
        """
        if user_id not in self.runners:
            logger.info(f"Creating new runner for user {user_id}")
            agent = self._create_agent(user_id)

            runner = Runner(
                app_name="agents",  # Must match agent module path
                agent=agent,
                session_service=session_service,
            )

            self.runners[user_id] = runner
        else:
            logger.debug(f"Reusing existing runner for user {user_id}")

        return self.runners[user_id]

    def cleanup_runner(self, user_id: str):
        """Clean up runner for a user.

        Args:
            user_id: User identifier
        """
        if user_id in self.runners:
            logger.info(f"Cleaning up runner for user {user_id}")
            del self.runners[user_id]

    def get_active_runner_count(self) -> int:
        """Get count of active runners.

        Returns:
            Number of active runners
        """
        return len(self.runners)
