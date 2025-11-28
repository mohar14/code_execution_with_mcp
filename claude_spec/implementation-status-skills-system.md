# Skills System Implementation Status

**Project:** MCP Code Execution with Docker
**Date:** 2025-11-24
**Phase:** 3.5 - Skills System & Agent Prompt
**Previous Phase:** [Agent API Implementation Plan](agent-api-implementation-plan.md)

---

## Executive Summary

Implemented a complete Skills System and dynamic Agent System Prompt generation for the MCP server. This provides AI agents with domain-specific guidance and best practices through a skills framework.

**Status:** ✅ **COMPLETED**

**Critical Integration Note:** The Agent API (Phase 4) must be updated to fetch the system prompt from the MCP server's `agent_system_prompt` prompt instead of using a hardcoded instruction string.

---

## What Was Implemented

### 1. Skills Framework ✅

**Location:** `mcp_server/skills/`

Created a skills system for defining domain-specific knowledge modules:

```
mcp_server/skills/
├── README.md                          # Skills documentation
└── symbolic-computation/
    └── Skill.md                       # SymPy skill (236 lines)
```

**Skill Format:**
- YAML frontmatter (name, description, version, dependencies)
- Markdown content with examples and best practices
- "When to Use This Skill" trigger conditions
- Complete code examples and workflows

**First Skill:** `symbolic-computation`
- Symbolic mathematics with SymPy
- Calculus, algebra, equation solving
- Matrix operations, series expansions
- LaTeX rendering

---

### 2. Utility Module Refactoring ✅

**Location:** `mcp_server/utils/`

Refactored server code to separate concerns:

**New Files:**
- `utils/__init__.py` - Package initialization
- `utils/skill_utils.py` - Skill management utilities (380 lines)

**Key Functions:**
- `parse_skill_frontmatter(content)` - Parse YAML frontmatter
- `get_skill(skill_name)` - Load skill metadata and content
- `list_available_skills()` - Discover all skills
- `extract_use_cases(content)` - Extract usage triggers
- `generate_skills_section(skills)` - Format skills for embedding
- `generate_agent_prompt(skills_section)` - Generate complete prompt

**Refactored:**
- `server.py` - Removed utilities (now cleaner, server-only code)
- Imported from `utils` module

---

### 3. Agent System Prompt (MCP Prompt) ✅

**Location:** `mcp_server/server.py` (lines 285-315)

Created an MCP prompt that dynamically generates a system prompt with embedded skills.

```python
@mcp.prompt()
def agent_system_prompt() -> str:
    """Generate a system prompt for agents with embedded skill descriptions.

    This prompt provides agents with:
    - Overview of the skills system
    - Dynamically embedded skill descriptions from /skills/ folder
    - Workflow patterns for using skills with read_file tool
    - Complete usage examples (no API calls, no package installation)

    Returns:
        Complete system prompt with all available skills embedded
    """
    skills = list_available_skills()
    skills_section = generate_skills_section(skills)
    prompt = generate_agent_prompt(skills_section)
    return prompt
```

**Prompt Features:**
- Dynamically embeds all available skills
- References container filesystem (`/skills/SKILL_NAME/Skill.md`)
- Uses `read_file` tool (NO curl, NO HTTP requests)
- NO package installation (dependencies pre-installed)
- Complete workflow examples
- Best practices and error handling

---

### 4. HTTP Endpoints for Skills ✅

Added skill retrieval endpoints (for debugging/administration):

- `GET /health` - Health check
- `GET /skills` - List all skills
- `GET /skills/{skill_name}` - Get specific skill

---

### 5. Comprehensive Testing ✅

**Location:** `tests/test_mcp_server/test_server.py`

Added `TestSkillsEndpoints` class with 5 tests:

1. ✅ `test_parse_skill_frontmatter` - YAML parsing
2. ✅ `test_list_available_skills` - Skill discovery
3. ✅ `test_get_skill` - Skill retrieval
4. ✅ `test_get_nonexistent_skill` - Error handling
5. ✅ `test_agent_system_prompt` - Prompt generation

**Results:** 5/5 tests passing (100%)

---

## Integration with Agent API (Phase 4)

### 🚨 CRITICAL UPDATE REQUIRED 🚨

The Agent API implementation plan (Phase 2) currently shows:

**❌ OLD APPROACH (From agent-api-implementation-plan.md):**

```python
# agent_api/agent_manager.py

def _get_instruction_prompt(self) -> str:
    """Get agent instruction/system prompt."""
    return """You are a code execution assistant with access to secure Docker containers.

You can:
- Execute bash commands and Python scripts
- Write files to the workspace
- Read file contents with pagination
- Inspect function documentation

Guidelines:
- Always validate user code before execution
...
"""
```

**✅ NEW APPROACH (Required):**

```python
# agent_api/agent_manager.py

from mcp import Client
from mcp.client.streamable_http import StreamableHTTPTransport

class AgentManager:
    def __init__(self, mcp_server_url: str):
        self.mcp_server_url = mcp_server_url
        self._cached_prompt = None
        self._prompt_cache_time = None

    async def _get_instruction_prompt(self) -> str:
        """Get agent instruction/system prompt from MCP server.

        Fetches the dynamically generated prompt with embedded skills
        from the MCP server's agent_system_prompt.
        """
        # Optional: Cache for 5 minutes to reduce calls
        if self._cached_prompt and self._prompt_cache_time:
            if (time.time() - self._prompt_cache_time) < 300:
                return self._cached_prompt

        # Connect to MCP server
        transport = StreamableHTTPTransport(url=self.mcp_server_url)

        async with Client(transport=transport) as client:
            # Fetch the dynamic prompt
            result = await client.get_prompt("agent_system_prompt")
            prompt_text = result.messages[0].content.text

            # Cache it
            self._cached_prompt = prompt_text
            self._prompt_cache_time = time.time()

            return prompt_text

    def _create_agent(self, user_id: str) -> Agent:
        """Create Google ADK agent with MCP tools."""
        toolset = self._create_mcp_toolset(user_id)

        # Get dynamic instruction from MCP server
        instruction = await self._get_instruction_prompt()  # NEW!

        agent = Agent(
            model=settings.default_model,
            name=settings.agent_name,
            instruction=instruction,  # Now includes skills!
            tools=[toolset],
        )

        return agent
```

### Why This Matters

**Benefits:**
1. **Dynamic Skills** - Agents automatically get new skills when added
2. **Consistent Guidance** - All agents use same up-to-date patterns
3. **Single Source of Truth** - Skills defined once, used everywhere
4. **Versionable** - Skills can be updated without code changes
5. **Container-Native** - Skills reference `/skills/` in container

**Without This Integration:**
- ❌ Agents won't know about skills
- ❌ Hardcoded instruction becomes stale
- ❌ No benefit from skills system
- ❌ Manual prompt updates required

---

## Updated Agent API Architecture

### Before This Implementation
```
┌─────────────────────┐
│   OpenAI SDK        │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────┐
│  Agent API                   │
│  ┌────────────────────────┐  │
│  │ Agent Manager          │  │
│  │ - Hardcoded prompt     │  │  ❌ Static
│  └────────────────────────┘  │
└──────────┬───────────────────┘
           │
           ▼
    ┌─────────────┐    ┌──────────────────┐
    │ ADK Agent   │───→│ MCP Server       │
    └─────────────┘    │ (4 tools)        │
                       └──────────────────┘
```

### After This Implementation (Required Update)
```
┌─────────────────────┐
│   OpenAI SDK        │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Agent API                               │
│  ┌────────────────────────────────────┐  │
│  │ Agent Manager                      │  │
│  │ 1. Fetch agent_system_prompt  ────┼──┼─┐
│  │ 2. Create agent with prompt       │  │ │
│  └────────────────────────────────────┘  │ │
└──────────┬───────────────────────────────┘ │
           │                                 │
           │ MCP Tools                       │ MCP Prompt
           ▼                                 │
    ┌─────────────┐    ┌─────────────────────▼──┐
    │ ADK Agent   │───→│ MCP Server              │
    │             │    │ - 4 tools               │
    │ Instruction │◄───│ - 1 prompt (NEW!)       │
    │ (w/ skills) │    │   • agent_system_prompt │
    └─────────────┘    └─────────────────────────┘
                                 │
                                 ▼
                          ┌─────────────────┐
                          │ Skills          │
                          │ /skills/        │
                          │ - symbolic-...  │
                          └─────────────────┘
```

---

## Agent API Implementation Changes

### File: `agent_api/agent_manager.py`

**Add Dependency:**
```python
from mcp import Client
from mcp.client.streamable_http import StreamableHTTPTransport
import time
```

**Update `__init__` Method:**
```python
def __init__(self, mcp_server_url: str):
    self.mcp_server_url = mcp_server_url
    self.runners: dict[str, Runner] = {}

    # Add prompt caching
    self._cached_prompt: str | None = None
    self._prompt_cache_time: float | None = None
```

**Replace `_get_instruction_prompt` Method:**
```python
async def _get_instruction_prompt(self) -> str:
    """Fetch dynamic agent prompt from MCP server.

    Returns:
        Complete system prompt with embedded skills
    """
    # Cache for 5 minutes
    if self._cached_prompt and self._prompt_cache_time:
        if (time.time() - self._prompt_cache_time) < 300:
            logger.debug("Using cached agent prompt")
            return self._cached_prompt

    logger.info("Fetching agent prompt from MCP server")

    try:
        transport = StreamableHTTPTransport(url=self.mcp_server_url)

        async with Client(transport=transport) as client:
            result = await client.get_prompt("agent_system_prompt")
            prompt_text = result.messages[0].content.text

            # Cache it
            self._cached_prompt = prompt_text
            self._prompt_cache_time = time.time()

            logger.info(f"Fetched prompt ({len(prompt_text)} chars)")
            return prompt_text

    except Exception as e:
        logger.error(f"Failed to fetch agent prompt: {e}")
        # Fallback to basic prompt
        return "You are a helpful code execution assistant."
```

**Update `_create_agent` Method:**
```python
async def _create_agent(self, user_id: str) -> Agent:
    """Create Google ADK agent with MCP tools and dynamic prompt."""
    toolset = self._create_mcp_toolset(user_id)

    # Fetch instruction from MCP server (includes skills!)
    instruction = await self._get_instruction_prompt()

    agent = Agent(
        model=settings.default_model,
        name=settings.agent_name,
        instruction=instruction,  # Dynamic with skills
        tools=[toolset],
    )

    return agent
```

**Update `get_or_create_runner` Signature:**
```python
async def get_or_create_runner(
    self,
    user_id: str,
    session_service: InMemorySessionService
) -> Runner:
    """Get existing runner or create new one for user."""
    if user_id not in self.runners:
        agent = await self._create_agent(user_id)  # Now async!

        runner = Runner(
            app_name='code-execution-app',
            agent=agent,
            session_service=session_service,
        )

        self.runners[user_id] = runner

    return self.runners[user_id]
```

### File: `agent_api/server.py`

**Update `/v1/chat/completions` Endpoint:**
```python
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint (streaming only)."""

    # ... existing validation ...

    # Get runner for user (now async)
    runner = await agent_manager.get_or_create_runner(  # Add await!
        user_id=user_id,
        session_service=session_store.session_service
    )

    # ... rest of endpoint ...
```

---

## Testing the Integration

### Test 1: Verify Prompt Fetching

```python
# tests/test_agent_api/test_agent_manager.py

import pytest
from agent_api.agent_manager import AgentManager

@pytest.mark.asyncio
async def test_get_instruction_prompt():
    """Test fetching agent prompt from MCP server."""
    manager = AgentManager(mcp_server_url="http://localhost:8989")

    prompt = await manager._get_instruction_prompt()

    # Verify prompt has skills
    assert "symbolic-computation" in prompt
    assert "/skills/" in prompt
    assert "read_file" in prompt

    # Verify NO API calls
    assert "curl" not in prompt.lower()
    assert "pip install" not in prompt
```

### Test 2: Verify Agent Creation

```python
@pytest.mark.asyncio
async def test_create_agent_with_skills():
    """Test that agents are created with skill-aware prompts."""
    manager = AgentManager(mcp_server_url="http://localhost:8989")

    agent = await manager._create_agent(user_id="test-user")

    # Verify instruction includes skills
    assert "symbolic-computation" in agent.instruction
    assert "When to Use This Skill" in agent.instruction
```

### Test 3: End-to-End Skill Usage

```python
@pytest.mark.asyncio
async def test_agent_uses_skill():
    """Test that agent can read and use skills."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy"
    )

    stream = await client.chat.completions.create(
        model="gemini-2.0-flash-exp",
        messages=[{
            "role": "user",
            "content": "Find the derivative of x^3 using SymPy"
        }],
        stream=True
    )

    response = ""
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            response += chunk.choices[0].delta.content

    # Agent should have used the symbolic-computation skill
    assert "sympy" in response.lower() or "diff" in response.lower()
```

---

## Deployment Updates

### Environment Variables

Add to `.env`:
```bash
# MCP Server (existing)
MCP_SERVER_URL=http://localhost:8989

# Prompt Caching (optional)
AGENT_PROMPT_CACHE_TTL=300  # 5 minutes
```

### Docker Compose

Ensure `/skills/` is mounted in containers:

```yaml
services:
  mcp-server:
    volumes:
      - ./mcp_server/skills:/skills:ro  # Mount skills
      - ./tools:/tools:ro

  agent-api:
    depends_on:
      - mcp-server
    environment:
      - MCP_SERVER_URL=http://mcp-server:8989
```

---

## File Summary

### New Files
| File | Lines | Purpose |
|------|-------|---------|
| `mcp_server/utils/__init__.py` | 18 | Package init |
| `mcp_server/utils/skill_utils.py` | 380 | Skill management |
| `mcp_server/skills/README.md` | 201 | Skills docs |
| `mcp_server/skills/symbolic-computation/Skill.md` | 236 | SymPy skill |

### Modified Files
| File | Changes | Purpose |
|------|---------|---------|
| `mcp_server/server.py` | +31, -95 | Added prompt, removed utils |
| `tests/test_mcp_server/test_server.py` | +35 | Added 5 tests |

**Total New Lines:** ~771

---

## Success Criteria

### Completed ✅
- [x] Skills framework implemented
- [x] Skill file format defined
- [x] First skill created (symbolic-computation)
- [x] Utilities refactored to separate module
- [x] MCP prompt created (agent_system_prompt)
- [x] HTTP endpoints for skills
- [x] Comprehensive tests (5/5 passing)
- [x] Documentation complete

### Required for Phase 4 Integration ⚠️
- [ ] Update `agent_api/agent_manager.py` to fetch prompt from MCP
- [ ] Make `_create_agent` async
- [ ] Update `get_or_create_runner` to await agent creation
- [ ] Update `/v1/chat/completions` to await runner creation
- [ ] Add tests for prompt fetching
- [ ] Add tests for agent creation with skills
- [ ] Verify end-to-end skill usage

---

## Next Steps

### Immediate (Phase 4)

1. **Update Agent Manager** ⚠️ CRITICAL
   - Implement `_get_instruction_prompt()` to fetch from MCP
   - Add prompt caching (5-minute TTL)
   - Make agent creation async

2. **Update Server Endpoint** ⚠️ CRITICAL
   - Add `await` to `get_or_create_runner()` call
   - Handle async agent creation

3. **Test Integration**
   - Verify prompt fetching works
   - Test agent receives skills
   - Validate end-to-end workflow

### Short-Term

1. **Add More Skills**
   - Data visualization
   - Web scraping
   - ML workflows

2. **Enhance Prompt**
   - Add skill selection logic
   - Implement prompt versioning
   - Add usage examples

3. **Performance**
   - Implement better caching
   - Monitor prompt size
   - Optimize skill loading

---

## Conclusion

Successfully implemented a Skills System and dynamic Agent System Prompt that provides AI agents with domain-specific guidance.

**Key Achievement:** Created an extensible framework where new skills can be added without code changes.

**Critical Next Step:** Update the Agent API (Phase 4) to fetch the `agent_system_prompt` from the MCP server instead of using a hardcoded instruction. This integration is **essential** for agents to benefit from the skills system.

**Status:** ✅ Phase 3.5 Complete | ⚠️ Phase 4 Update Required

---

*Generated: 2025-11-24*
*Phase: 3.5 - Skills System & Agent Prompt*
*Next: [Agent API Implementation](agent-api-implementation-plan.md) (requires updates)*
