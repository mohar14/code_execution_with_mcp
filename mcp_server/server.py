"""MCP Server for Docker-based code execution.

This server exposes the DockerExecutionClient methods as MCP tools,
allowing AI agents to execute code in isolated Docker containers.
"""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastmcp import FastMCP
from fastmcp import Context

from docker_client import DockerExecutionClient
from starlette.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global client instance (initialized in lifespan)
docker_client: DockerExecutionClient | None = None


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Lifespan context manager for server startup and shutdown.

    Handles:
    - Creating singleton DockerExecutionClient on startup
    - Cleaning up all containers on shutdown
    """
    global docker_client

    # Startup
    logger.info("Starting MCP Code Executor server...")
    logger.info("Initializing Docker execution client...")

    try:
        docker_client = DockerExecutionClient()
        logger.info("Docker client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Docker client: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down MCP server...")
    if docker_client:
        try:
            logger.info("Cleaning up all containers...")
            docker_client.cleanup_all()
            logger.info("All containers cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Initialize MCP server with lifespan
mcp = FastMCP("code-executor", lifespan=lifespan)


def get_user_id(ctx: Context) -> str:
    """Extract user ID from MCP request context.

    Checks for user ID in multiple possible header locations:
    1. X-User-ID header
    2. X-MCP-User-ID header
    3. Falls back to "default" if not found

    Args:
        ctx: FastMCP request context

    Returns:
        User ID string
    """
    # Try different header variations
    request_headers = ctx.get_http_request().headers
    user_id = request_headers.get("x-user-id", "")

    logger.debug(f"Extracted user_id: {user_id}")

    if not user_id:
        raise RuntimeError("Failed to parse x-user-id header")
    return user_id


@mcp.tool()
async def execute_bash(
    command: Annotated[str, "Bash command to execute in the container"],
    timeout: Annotated[int, "Command timeout in seconds (default: 30)"] = 30,
    ctx: Context = None,
) -> dict[str, str | int]:
    """Execute a bash command in the user's isolated Docker container.

    This tool runs arbitrary bash commands in a secure, per-user container.
    The container persists between calls for the same user.

    Args:
        command: The bash command to execute
        timeout: Maximum execution time in seconds
        ctx: MCP request context (automatically injected)

    Returns:
        Dictionary containing:
        - exit_code: Command exit code (0 for success)
        - stdout: Standard output from the command
        - stderr: Standard error from the command

    Example:
        >>> result = await execute_bash("python --version")
        >>> print(result)
        {'exit_code': 0, 'stdout': 'Python 3.12.0\\n', 'stderr': ''}
    """
    user_id = get_user_id(ctx)
    logger.info(f"Executing bash command for user {user_id}: {command[:100]}...")

    try:
        exit_code, stdout, stderr = await docker_client.execute_bash(
            user_id=user_id,
            command=command,
            timeout=timeout,
        )

        logger.info(f"Command completed for user {user_id} with exit code {exit_code}")

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        }

    except Exception as e:
        logger.error(f"Error executing bash command for user {user_id}: {e}")
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Error: {str(e)}",
        }


@mcp.tool()
async def read_file(
    file_path: Annotated[str, "Absolute path to the file in the container"],
    offset: Annotated[int, "Line number to start reading from (0-indexed)"] = 0,
    line_count: Annotated[int | None, "Number of lines to read (None for all)"] = None,
    ctx: Context = None,
) -> str:
    """Read a file from the user's container with optional line-based pagination.

    Reads files from the user's persistent container filesystem. Useful for
    retrieving execution results, logs, or generated files.

    Args:
        file_path: Absolute path to the file (e.g., "/workspace/output.txt")
        offset: Line number to start reading from (default: 0)
        line_count: Maximum number of lines to read (default: all)
        ctx: MCP request context (automatically injected)

    Returns:
        File contents as a string

    Example:
        >>> content = await read_file("/workspace/data.txt")
        >>> print(content)
        'Line 1\\nLine 2\\nLine 3'

        >>> # Read lines 10-20
        >>> content = await read_file("/workspace/log.txt", offset=10, line_count=10)
    """
    user_id = get_user_id(ctx)
    logger.info(f"Reading file for user {user_id}: {file_path}")

    try:
        content = await docker_client.read_file(
            user_id=user_id,
            file_path=file_path,
            offset=offset,
            line_count=line_count,
        )

        logger.info(f"Successfully read {len(content)} bytes from {file_path}")
        return content

    except Exception as e:
        logger.error(f"Error reading file for user {user_id}: {e}")
        raise


@mcp.tool()
async def write_file(
    file_path: Annotated[str, "Absolute path where to write the file"],
    content: Annotated[str, "Content to write to the file"],
    ctx: Context = None,
) -> str:
    """Write content to a file in the user's container.

    Creates or overwrites a file in the user's container filesystem.
    Handles special characters and multi-line content safely.

    Args:
        file_path: Absolute path for the file (e.g., "/workspace/script.py")
        content: Text content to write
        ctx: MCP request context (automatically injected)

    Returns:
        Success message

    Example:
        >>> await write_file("/workspace/hello.py", "print('Hello, World!')")
        'Successfully wrote 22 bytes to /workspace/hello.py'
    """
    user_id = get_user_id(ctx)
    logger.info(f"Writing file for user {user_id}: {file_path}")

    try:
        await docker_client.write_file(
            user_id=user_id,
            file_path=file_path,
            content=content,
        )

        logger.info(f"Successfully wrote {len(content)} bytes to {file_path}")
        return f"Successfully wrote {len(content)} bytes to {file_path}"

    except Exception as e:
        logger.error(f"Error writing file for user {user_id}: {e}")
        raise


@mcp.tool()
async def read_docstring(
    file_path: Annotated[str, "Absolute path to Python file (e.g., '/workspace/script.py')"],
    function_name: Annotated[str, "Name of the function to inspect"],
    ctx: Context = None,
) -> str:
    """Read the docstring of a function from a Python file.

    Retrieves documentation for functions defined in Python files in the
    container filesystem. Uses Python's help() to get formatted documentation.

    Args:
        file_path: Absolute path to the Python file (e.g., "/workspace/utils.py")
        function_name: Name of the function to get documentation for
        ctx: MCP request context (automatically injected)

    Returns:
        The function's docstring, or empty string if not found

    Example:
        >>> doc = await read_docstring("/workspace/utils.py", "greet")
        >>> print(doc)
        'Generate a greeting message.\\n\\nArgs:\\n    name: The name to greet...'
    """
    user_id = get_user_id(ctx)
    logger.info(f"Reading docstring for user {user_id}: {file_path}:{function_name}")

    try:
        # Use Python to dynamically import and get the docstring
        python_cmd = (
            f"import sys; "
            f"import importlib.util; "
            f"spec = importlib.util.spec_from_file_location('temp_module', '{file_path}'); "
            f"module = importlib.util.module_from_spec(spec); "
            f"spec.loader.exec_module(module); "
            f"print(getattr(module, '{function_name}').__doc__ or '')"
        )

        exit_code, stdout, stderr = await docker_client.execute_bash(
            user_id=user_id,
            command=f"python -c \"{python_cmd}\"",
            timeout=10,
        )

        if exit_code == 0:
            docstring = stdout.strip()
            if docstring:
                logger.info(f"Successfully retrieved docstring for {function_name}")
            else:
                logger.warning(f"No docstring found for {file_path}:{function_name}")
            return docstring
        else:
            logger.error(f"Error reading docstring: {stderr}")
            return ""

    except Exception as e:
        logger.error(f"Error reading docstring: {e}")
        return ""


# HTTP health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check():
    """HTTP health check endpoint for monitoring and load balancers.

    Returns:
        JSON response with server status
    """
    return JSONResponse({
        "status": "healthy",
        "service": "mcp-code-executor",
        "client_initialized": docker_client is not None,
    })


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
