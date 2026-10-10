from cache import ttl_cache
from config import settings
from fastmcp.client import Client as FastMCPClient
from google.adk import Agent, Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from loguru import logger


class AgentManager:
    def __init__(self, mcp_server_url: str):
        self.mcp_server_url = mcp_server_url
        self.runners: dict[str, Runner] = {}
        logger.info(f"AgentManager initialized with MCP server: {mcp_server_url}")

    def _create_mcp_toolset(self, user_id: str) -> McpToolset:
        logger.debug(f"Creating MCP toolset for user {user_id}")

        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=self.mcp_server_url,
            ),
            header_provider=lambda ctx: {"x-user-id": user_id},
        )

    @ttl_cache(ttl_seconds=3600)
    async def _get_instruction_prompt(self) -> str:
        logger.info("Fetching agent system prompt from MCP server")

        try:
            async with FastMCPClient(self.mcp_server_url) as client:
                result = await client.get_prompt("agent_system_prompt")

                if result and result.messages and len(result.messages) > 0:
                    prompt_text = result.messages[0].content.text

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

        logger.info("Using default system prompt from settings")
        return settings.system_prompt

    async def _create_agent(self, user_id: str) -> Agent:
        logger.info(f"Creating agent for user {user_id} with model {settings.default_model}")
        toolset = self._create_mcp_toolset(user_id)

        instruction = await self._get_instruction_prompt()

        def instruction_provider(ctx):
            return instruction

        model = LiteLlm(model=settings.default_model)

        agent = Agent(
            model=model,
            name=settings.agent_name,
            instruction=instruction_provider,
            tools=[toolset],
        )

        return agent

    async def get_or_create_runner(
        self, user_id: str, session_service: InMemorySessionService
    ) -> Runner:
        if user_id not in self.runners:
            logger.info(f"Creating new runner for user {user_id}")
            agent = await self._create_agent(user_id)

            runner = Runner(
                app_name="agents",
                agent=agent,
                session_service=session_service,
            )

            self.runners[user_id] = runner
        else:
            logger.debug(f"Reusing existing runner for user {user_id}")

        return self.runners[user_id]

    def cleanup_runner(self, user_id: str):
        if user_id in self.runners:
            logger.info(f"Cleaning up runner for user {user_id}")
            del self.runners[user_id]

    def get_active_runner_count(self) -> int:
        return len(self.runners)
