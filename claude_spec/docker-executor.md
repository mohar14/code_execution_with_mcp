# Task

Your task is to construct a secure code execution environment leveraging docker that can be used by an AI Agent for code execution to support user queries. The container will be managed by a docker execution client, and this client will be invoked during MCP tool calls.

## Phase 1: Docker environment construction

The following requirements must be met by the container environment:

1. The user will be non-root
2. The container will provide a python 3.12 executable and Bash for code execution
3. There will be mounted directories providing context/code for the calling agent:
    - `/tools/`: this mount will contain python code that the agent can leverage during code execution
    - `/skills/`: this mount will contains Anthropic skill definitions to dynamically provide the agent additional context when request, depending on the user's query
    - Each of the mounts must be read/execute only to avoid writing to the host system

Place the file resulting `Dockerfile` in `/mcp/docker/`. Provide a build script, `build.sh` as well.

## Phase 2: Docker execution client

Once the container environment has been constructed, you should proceed by constructing an execution client to support running containers and executing code on behalf of the AI Agent.

The following requirements must be met:

1. The class should be called `DockerExecutionClient`
2. The class should handle creating/starting/stopping containers on *user-by-user* basis so that created files can be segmented and recovered per user.
3. The class should use the python docker client and expose methods for:
    - Executing bash commands
    - Reading files with a specific file number offset and line count
    - Writing files
    - Reading python function docstrings in `/tools/` given a module path and a function name
    - support async execution for throughput when being wrapped by an MCP server


