# Claude Spec Documentation Index

**Last Updated:** November 29, 2025
**Project:** Code Execution with MCP

---

## Quick Navigation

- **[Current Status](#current-status)** - Where we are now
- **[Documentation Timeline](#documentation-timeline)** - Chronological order of work
- **[By Component](#by-component)** - Find docs by feature area

---

## Current Status

**Latest Document:** [implementation-plan-mcp-artifact-backend.md](implementation-plan-mcp-artifact-backend.md) (Nov 29, 2025)

**Project Completion:** ~85-90%

**What's Working:**
- ✅ Docker executor with per-user containers
- ✅ MCP server with 4 core tools
- ✅ Skills system with dynamic prompting
- ✅ Agent API with Google ADK + LiteLLM
- ✅ Gradio frontend with streaming
- ✅ Artifact management (backend + frontend)

**In Progress:**
- 🔄 MCP artifact backend implementation planning (Nov 29)

**What's Next:**
- Production hardening
- Additional skills
- Performance optimization

---

## Documentation Timeline

### November 29, 2025
- **[implementation-plan-mcp-artifact-backend.md](implementation-plan-mcp-artifact-backend.md)**
  - Planning document for artifact management via MCP
  - Status: Planning phase

### November 28, 2025 (Evening)
- **[IMPLEMENTATION_OVERVIEW.md](IMPLEMENTATION_OVERVIEW.md)**
  - Comprehensive system architecture overview
  - 75% completion status at time of writing
  - Detailed component breakdown

- **[implementation-status-gradio-ui.md](implementation-status-gradio-ui.md)**
  - Gradio UI implementation complete
  - Real-time streaming, artifact browser, activity monitor

- **[gradio-ui-tool-calls-issue.md](gradio-ui-tool-calls-issue.md)**
  - Documented tool call parsing issue in Gradio UI
  - Status: Resolved

### November 28, 2025 (Morning)
- **[implementation-status-phase4-skills-integration.md](implementation-status-phase4-skills-integration.md)**
  - Skills integration into Agent API
  - Dynamic prompt fetching with TTL cache

- **[CLAUDE.md](CLAUDE.md)**
  - Guidelines for Claude spec directory structure
  - File naming conventions and workflows

- **[implementation-plan-agent-api.md](implementation-plan-agent-api.md)**
  - Planning document for Agent API implementation
  - OpenAI-compatible endpoints design

- **[implementation-status-agent-api-testing.md](implementation-status-agent-api-testing.md)**
  - Agent API testing implementation
  - 10/11 tests passing

- **[implementation-status-skills-system.md](implementation-status-skills-system.md)**
  - Skills system implementation complete
  - Dynamic skill discovery and prompt generation

- **[implementation-status-agent-api.md](implementation-status-agent-api.md)**
  - Agent API implementation complete
  - Google ADK integration with LiteLLM

- **[prompt-docker-executor.md](prompt-docker-executor.md)**
  - Initial requirements for Docker executor
  - Archive: Implementation complete

### November 26, 2025
- **[implementation-status-mcp-server.md](implementation-status-mcp-server.md)**
  - MCP server implementation complete
  - 4 tools exposed via FastMCP

- **[implementation-status-docker-executor.md](implementation-status-docker-executor.md)**
  - Docker executor implementation complete
  - Per-user container isolation

- **[README.md](README.md)**
  - Brief overview of claude_spec directory

---

## By Component

### Docker Executor
- **Prompt:** [prompt-docker-executor.md](prompt-docker-executor.md) (Nov 28)
- **Status:** [implementation-status-docker-executor.md](implementation-status-docker-executor.md) (Nov 26)
- **Completion:** 100% ✅

### MCP Server
- **Status:** [implementation-status-mcp-server.md](implementation-status-mcp-server.md) (Nov 26)
- **Completion:** 100% ✅

### Skills System
- **Status:** [implementation-status-skills-system.md](implementation-status-skills-system.md) (Nov 28)
- **Completion:** 100% ✅

### Agent API
- **Plan:** [implementation-plan-agent-api.md](implementation-plan-agent-api.md) (Nov 28)
- **Status:** [implementation-status-agent-api.md](implementation-status-agent-api.md) (Nov 28)
- **Testing:** [implementation-status-agent-api-testing.md](implementation-status-agent-api-testing.md) (Nov 28)
- **Completion:** 100% ✅

### Skills Integration
- **Status:** [implementation-status-phase4-skills-integration.md](implementation-status-phase4-skills-integration.md) (Nov 28)
- **Completion:** 100% ✅

### Gradio UI
- **Status:** [implementation-status-gradio-ui.md](implementation-status-gradio-ui.md) (Nov 28)
- **Issue:** [gradio-ui-tool-calls-issue.md](gradio-ui-tool-calls-issue.md) (Nov 28, resolved)
- **Completion:** 100% ✅

### Artifact Management
- **Plan:** [implementation-plan-mcp-artifact-backend.md](implementation-plan-mcp-artifact-backend.md) (Nov 29)
- **Completion:** Planning phase 🔄

### System Overview
- **Overview:** [IMPLEMENTATION_OVERVIEW.md](IMPLEMENTATION_OVERVIEW.md) (Nov 28)

---

## How to Use This Documentation

### For Developers

**Starting work:**
1. Read [CURRENT_STATUS.md](CURRENT_STATUS.md) for latest state
2. Check component-specific status docs
3. Review "Next Steps" sections

**After completing work:**
1. Create/update `implementation-status-*.md`
2. Update this INDEX.md with new docs
3. Update CURRENT_STATUS.md

### For Claude Code

**Before starting:**
1. Read CURRENT_STATUS.md
2. Check relevant implementation-status-*.md files
3. Review "Known Issues" and "Next Steps"

**During work:**
1. Reference technical details from status docs
2. Follow established patterns

**After completing:**
1. Create handoff document following CLAUDE.md guidelines
2. Update this INDEX.md
3. Update CURRENT_STATUS.md

---

## File Categories

### Active Documents
- `CURRENT_STATUS.md` - Always current project state
- `INDEX.md` - This file
- `CLAUDE.md` - Guidelines
- `IMPLEMENTATION_OVERVIEW.md` - Architecture reference

### Historical Records
- `prompt-*.md` - Original requirements (archived)
- `implementation-status-*.md` - Session handoffs (historical)
- `implementation-plan-*.md` - Planning documents (historical)

### Issue Tracking
- `*-issue.md` - Specific problems and resolutions

---

## Metrics

**Total Documents:** 14
**Prompts:** 1
**Plans:** 2
**Status Docs:** 9
**Issues:** 1
**Guidelines:** 2

**Date Range:** Nov 26 - Nov 29, 2025
**Duration:** 4 days
**Components Completed:** 6/7

---

**Maintained By:** Development Team + Claude Code
**Updated:** After each significant work session
