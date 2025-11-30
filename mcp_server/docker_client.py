"""Docker-based code execution client for AI agents.

This module provides a secure execution environment for running code
on behalf of AI agents, with per-user container isolation.

Environment Variables:
    MCP_EXECUTOR_IMAGE: Docker image name (default: mcp-code-executor:latest)
    MCP_TOOLS_PATH: Path to tools directory (default: ./tools)
    MCP_SKILLS_PATH: Path to skills directory (default: ./skills)
    MCP_ARTIFACT_SIZE_LIMIT_MB: Max artifact file size in MB (default: 50)
"""

import asyncio
import contextlib
import importlib.util
import inspect
import os
from pathlib import Path

import docker
from docker.models.containers import Container


class DockerExecutionClient:
    """Manages Docker containers for secure code execution.

    Provides per-user container isolation and async methods for code execution,
    file operations, and tool introspection.
    """

    def __init__(
        self,
        image_name: str | None = None,
        tools_path: str | None = None,
        skills_path: str | None = None,
    ):
        """Initialize the Docker execution client.

        Configuration is loaded from environment variables with fallback to parameters:
        - MCP_EXECUTOR_IMAGE: Docker image name
        - MCP_TOOLS_PATH: Path to tools directory
        - MCP_SKILLS_PATH: Path to skills directory

        Args:
            image_name: Override for Docker image name (defaults to env var or latest)
            tools_path: Override for tools directory path (defaults to env var or ./tools)
            skills_path: Override for skills directory path (defaults to env var or ./skills)
        """
        dirname = os.path.abspath(os.path.dirname(__file__))
        self.image_name = image_name or os.getenv("MCP_EXECUTOR_IMAGE", "mcp-code-executor:latest")
        self.tools_path = tools_path or os.getenv("MCP_TOOLS_PATH", os.path.join(dirname, "tools"))
        self.skills_path = skills_path or os.getenv(
            "MCP_SKILLS_PATH", os.path.join(dirname, "skills")
        )

        # Configure artifact size limit
        default_size_limit_mb = 50
        size_limit_mb = int(os.getenv("MCP_ARTIFACT_SIZE_LIMIT_MB", default_size_limit_mb))
        self.artifact_size_limit_bytes = size_limit_mb * 1024 * 1024

        # Initialize Docker client
        self.docker_client = docker.from_env()

        # Track containers per user
        self.user_containers: dict[str, Container] = {}

    def _get_or_create_container(self, user_id: str) -> Container:
        """Get existing container for user or create a new one.

        Args:
            user_id: Unique identifier for the user

        Returns:
            Docker container instance for the user
        """
        # Check if container exists and is running
        if user_id in self.user_containers:
            container = self.user_containers[user_id]
            try:
                container.reload()
                if container.status == "running":
                    return container
                elif container.status == "exited":
                    container.start()
                    return container
            except docker.errors.NotFound:
                # Container was removed externally
                del self.user_containers[user_id]

        # Create new container with mounted volumes
        volumes = {
            self.tools_path: {"bind": "/tools", "mode": "ro"},
            self.skills_path: {"bind": "/skills", "mode": "ro"},
        }

        container = self.docker_client.containers.create(
            image=self.image_name,
            detach=True,
            tty=True,
            stdin_open=True,
            volumes=volumes,
            name=f"mcp-executor-{user_id}",
        )

        container.start()
        self.user_containers[user_id] = container
        return container

    async def execute_bash(
        self, user_id: str, command: str, timeout: int = 30
    ) -> tuple[int, str, str]:
        """Execute a bash command in the user's container.

        Args:
            user_id: Unique identifier for the user
            command: Bash command to execute
            timeout: Maximum execution time in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """

        def _run_command():
            container = self._get_or_create_container(user_id)
            exit_code, output = container.exec_run(
                cmd=["bash", "-c", command],
                demux=True,
                user="coderunner",
            )
            stdout = output[0].decode("utf-8") if output[0] else ""
            stderr = output[1].decode("utf-8") if output[1] else ""
            return exit_code, stdout, stderr

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _run_command), timeout=timeout
            )
            return result
        except TimeoutError:
            return -1, "", f"Command timed out after {timeout} seconds"

    async def read_file(
        self, user_id: str, file_path: str, offset: int = 0, line_count: int | None = None
    ) -> str:
        """Read a file from the user's container with line offset and count.

        Args:
            user_id: Unique identifier for the user
            file_path: Path to the file in the container
            offset: Number of lines to skip from the beginning (0-indexed)
            line_count: Number of lines to read (None = read all remaining)

        Returns:
            File content as string
        """
        # Build tail/head command for efficient line reading
        if line_count is not None:
            command = f"tail -n +{offset + 1} {file_path} | head -n {line_count}"
        else:
            command = f"tail -n +{offset + 1} {file_path}"

        exit_code, stdout, stderr = await self.execute_bash(user_id, command)

        if exit_code != 0:
            raise RuntimeError(f"Failed to read file {file_path}: {stderr}")

        return stdout

    async def write_file(self, user_id: str, file_path: str, content: str) -> None:
        """Write content to a file in the user's container.

        Args:
            user_id: Unique identifier for the user
            file_path: Path to the file in the container
            content: Content to write to the file
        """
        # Escape content for safe shell usage
        escaped_content = content.replace("'", "'\\''")

        # Use printf for better handling of special characters
        command = f"printf '%s' '{escaped_content}' > {file_path}"

        exit_code, _stdout, stderr = await self.execute_bash(user_id, command)

        if exit_code != 0:
            raise RuntimeError(f"Failed to write file {file_path}: {stderr}")

    async def read_docstring(self, module_path: str, function_name: str) -> str:
        """Read the docstring of a Python function from the /tools/ directory.

        Args:
            module_path: Python module path (e.g., 'tools.utils')
            function_name: Name of the function to get docstring from

        Returns:
            Function docstring as string

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If function doesn't exist in module
        """

        def _get_docstring():
            # Convert module path to file path
            module_file = Path(self.tools_path) / module_path.replace(".", "/")

            # Try both .py file and __init__.py in directory
            if module_file.with_suffix(".py").exists():
                spec = importlib.util.spec_from_file_location(
                    module_path, module_file.with_suffix(".py")
                )
            elif (module_file / "__init__.py").exists():
                spec = importlib.util.spec_from_file_location(
                    module_path, module_file / "__init__.py"
                )
            else:
                raise ImportError(f"Module {module_path} not found in {self.tools_path}")

            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module {module_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get function and extract docstring
            if not hasattr(module, function_name):
                raise AttributeError(f"Function {function_name} not found in module {module_path}")

            func = getattr(module, function_name)
            docstring = inspect.getdoc(func)

            return docstring or ""

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_docstring)

    async def read_file_docstring(self, user_id: str, file_path: str, function_name: str) -> str:
        """Read the docstring of a function from a Python file in the user's container.

        Args:
            user_id: Unique identifier for the user
            file_path: Absolute path to the Python file in the container
            function_name: Name of the function to get docstring from

        Returns:
            Function docstring as string, or empty string if not found
        """
        # Build Python command to dynamically import and extract docstring
        python_cmd = (
            f"import sys; "
            f"import importlib.util; "
            f"spec = importlib.util.spec_from_file_location('temp_module', '{file_path}'); "
            f"module = importlib.util.module_from_spec(spec); "
            f"spec.loader.exec_module(module); "
            f"print(getattr(module, '{function_name}').__doc__ or '')"
        )

        exit_code, stdout, stderr = await self.execute_bash(
            user_id=user_id,
            command=f'python -c "{python_cmd}"',
            timeout=10,
        )

        if exit_code == 0:
            return stdout.strip()
        else:
            raise RuntimeError(f"Failed to read docstring from {file_path}: {stderr}")

    async def list_artifacts(self, user_id: str) -> list[str]:
        """List all artifact files for a specific user.

        Lists files in the /artifacts/ directory. Only returns files that exist
        directly in /artifacts/ (no nested directories).

        Args:
            user_id: Unique identifier for the user

        Returns:
            List of filenames (without paths) in /artifacts/, sorted alphabetically.
            Empty list if directory is empty or doesn't exist.

        Raises:
            RuntimeError: If unable to execute the list command
        """
        # Use find to list only regular files directly in /artifacts/
        command = "find /artifacts/ -maxdepth 1 -type f -printf '%f\\n'"

        exit_code, stdout, stderr = await self.execute_bash(user_id, command)

        if exit_code != 0:
            raise RuntimeError(f"Failed to list artifacts: {stderr}")

        if not stdout.strip():
            return []

        # Parse and sort filenames
        artifacts = [f.strip() for f in stdout.strip().split("\n") if f.strip()]
        return sorted(artifacts)

    async def get_artifact(self, user_id: str, artifact_path: str) -> str:
        """Retrieve an artifact file encoded as base64.

        Reads a file from /artifacts/ and returns its base64-encoded content.
        Supports binary and text files. Performs security and size validation.

        Args:
            user_id: Unique identifier for the user
            artifact_path: Filename only (e.g., 'report.pdf', not '/artifacts/report.pdf')

        Returns:
            Base64-encoded string containing the artifact data

        Raises:
            RuntimeError: If file doesn't exist
            RuntimeError: If path traversal attempt detected (nested paths)
            RuntimeError: If file exceeds size limit
            RuntimeError: If unable to read file
        """
        # Step 1: Path validation (security)
        if "/" in artifact_path or "\\" in artifact_path:
            raise RuntimeError(
                f"Invalid artifact path '{artifact_path}': "
                "must be a filename, not a path (no '/' or '\\' allowed)"
            )
        if artifact_path.startswith("."):
            raise RuntimeError(f"Invalid artifact path '{artifact_path}': cannot start with '.'")

        # Step 2: File existence check
        exit_code, stdout, _ = await self.execute_bash(
            user_id, f"test -f /artifacts/{artifact_path} && echo 'exists'"
        )
        if exit_code != 0 or "exists" not in stdout:
            raise RuntimeError(f"Artifact not found: {artifact_path}")

        # Step 3: Size check
        exit_code, size_str, stderr = await self.execute_bash(
            user_id, f"wc -c < /artifacts/{artifact_path}"
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to check artifact size: {stderr}")

        size_bytes = int(size_str.strip())
        if size_bytes > self.artifact_size_limit_bytes:
            raise RuntimeError(
                f"Artifact '{artifact_path}' is {size_bytes} bytes, "
                f"exceeds limit of {self.artifact_size_limit_bytes} bytes"
            )

        # Step 4: Read and encode as base64
        exit_code, stdout, stderr = await self.execute_bash(
            user_id, f"base64 -w 0 /artifacts/{artifact_path}"
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to encode artifact: {stderr}")

        return stdout.strip()

    def stop_container(self, user_id: str) -> None:
        """Stop a user's container.

        Args:
            user_id: Unique identifier for the user
        """
        if user_id in self.user_containers:
            try:
                container = self.user_containers[user_id]
                container.stop(timeout=10)
            except docker.errors.NotFound:
                pass

    def cleanup_container(self, user_id: str, force: bool) -> None:
        """Remove a user's container completely.

        Args:
            user_id: Unique identifier for the user
            force: Boolean flag to force container removal
        """
        if user_id in self.user_containers:
            try:
                container = self.user_containers[user_id]
                container.stop(timeout=30)
                container.remove(force=force)
            except docker.errors.NotFound:
                pass
            finally:
                del self.user_containers[user_id]

    def cleanup_all(self, force: bool = True) -> None:
        """Stop and remove all managed containers."""
        for user_id in list(self.user_containers.keys()):
            self.cleanup_container(user_id, force)

    def __del__(self):
        """Cleanup on deletion."""
        with contextlib.suppress(Exception):
            self.cleanup_all()  # Best effort cleanup
