"""Google ADK Agent lifecycle management with LiteLLM support for Agent API."""

import logging

from fastmcp.client import Client as FastMCPClient
from google.adk import Agent, Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from cache import ttl_cache
from config import settings

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

    @ttl_cache(ttl_seconds=3600)  # 1-hour TTL
    async def _get_instruction_prompt(self) -> str:
        """Fetch agent instruction/system prompt from MCP server.

        Attempts to fetch the dynamic prompt with embedded skills from the
        MCP server. Falls back to the default prompt from settings if:
        - MCP server is unreachable
        - Prompt fetch fails
        - Fetched prompt is empty

        Returns:
            System prompt for the agent (either dynamic or fallback)
        """
        logger.info("Fetching agent system prompt from MCP server")

        try:
            # Connect to MCP server using FastMCP client
            async with FastMCPClient(
                connection_params={"url": self.mcp_server_url}
            ) as client:
                # Fetch the agent_system_prompt
                result = await client.get_prompt("agent_system_prompt")

                # Extract prompt text from result
                # Based on test_server.py:567-595, response structure is:
                # result.messages[0].content.text
                if result and result.messages and len(result.messages) > 0:
                    prompt_text = result.messages[0].content.text

                    # Validate prompt is not empty
                    if prompt_text and prompt_text.strip():
                        logger.info(
                            f"Successfully fetched dynamic prompt from MCP server "
                            f"({len(prompt_text)} chars)"
                        )
                        return prompt_text
                    else:
                        logger.warning("MCP server returned empty prompt, using fallback")
                else:
                    logger.warning("MCP server returned no messages, using fallback")

        except Exception as e:
            logger.warning(f"Failed to fetch prompt from MCP server: {e}, using fallback")

        # Fallback to settings
        logger.info("Using default system prompt from settings")
        return settings.system_prompt

    async def _create_agent(self, user_id: str) -> Agent:
        """Create Google ADK agent with MCP tools and LiteLLM model routing.

        Args:
            user_id: User identifier

        Returns:
            Configured Google ADK Agent
        """
        logger.info(f"Creating agent for user {user_id} with model {settings.default_model}")
        toolset = self._create_mcp_toolset(user_id)

        # Fetch instruction prompt from MCP server (with TTL cache)
        instruction = await self._get_instruction_prompt()

        # Use LiteLLM wrapper for multi-provider support
        # LiteLLM supports: OpenAI, Anthropic, Google, Cohere, etc.
        # Model format: "provider/model" (e.g., "openai/gpt-4", "anthropic/claude-3-sonnet")
        # For Gemini: "gemini/gemini-2.0-flash-exp" or just "gemini-2.0-flash-exp"
        model = LiteLlm(model=settings.default_model)

        agent = Agent(
            model=model,
            name=settings.agent_name,
            instruction=instruction,  # Now using dynamic prompt!
            tools=[toolset],
        )

        return agent

    async def get_or_create_runner(
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
            agent = await self._create_agent(user_id)  # Now async!

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
