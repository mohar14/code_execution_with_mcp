import asyncio
import contextlib
import importlib.util
import inspect
import os
from pathlib import Path

import docker
from docker.models.containers import Container


class DockerExecutionClient:
    def __init__(
        self,
        image_name: str | None = None,
        tools_path: str | None = None,
        skills_path: str | None = None,
    ):
        dirname = os.path.abspath(os.path.dirname(__file__))
        self.image_name = image_name or os.getenv("MCP_EXECUTOR_IMAGE", "mcp-code-executor:latest")
        self.tools_path = tools_path or os.getenv("MCP_TOOLS_PATH", os.path.join(dirname, "tools"))
        self.skills_path = skills_path or os.getenv(
            "MCP_SKILLS_PATH", os.path.join(dirname, "skills")
        )

        default_size_limit_mb = 50
        size_limit_mb = int(os.getenv("MCP_ARTIFACT_SIZE_LIMIT_MB", default_size_limit_mb))
        self.artifact_size_limit_bytes = size_limit_mb * 1024 * 1024

        self.docker_client = docker.from_env()

        self.user_containers: dict[str, Container] = {}

    def _get_or_create_container(self, user_id: str) -> Container:
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
                del self.user_containers[user_id]

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
        if line_count is not None:
            command = f"tail -n +{offset + 1} {file_path} | head -n {line_count}"
        else:
            command = f"tail -n +{offset + 1} {file_path}"

        exit_code, stdout, stderr = await self.execute_bash(user_id, command)

        if exit_code != 0:
            raise RuntimeError(f"Failed to read file {file_path}: {stderr}")

        return stdout

    async def write_file(self, user_id: str, file_path: str, content: str) -> None:
        escaped_content = content.replace("'", "'\\''")

        command = f"printf '%s' '{escaped_content}' > {file_path}"

        exit_code, _stdout, stderr = await self.execute_bash(user_id, command)

        if exit_code != 0:
            raise RuntimeError(f"Failed to write file {file_path}: {stderr}")

    async def read_docstring(self, module_path: str, function_name: str) -> str:
        def _get_docstring():
            module_file = Path(self.tools_path) / module_path.replace(".", "/")

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

            if not hasattr(module, function_name):
                raise AttributeError(f"Function {function_name} not found in module {module_path}")

            func = getattr(module, function_name)
            docstring = inspect.getdoc(func)

            return docstring or ""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_docstring)

    async def read_file_docstring(self, user_id: str, file_path: str, function_name: str) -> str:
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
        command = "find /artifacts/ -maxdepth 1 -type f -printf '%f\\n'"

        exit_code, stdout, stderr = await self.execute_bash(user_id, command)

        if exit_code != 0:
            raise RuntimeError(f"Failed to list artifacts: {stderr}")

        if not stdout.strip():
            return []

        artifacts = [f.strip() for f in stdout.strip().split("\n") if f.strip()]
        return sorted(artifacts)

    async def get_artifact(self, user_id: str, artifact_path: str) -> str:
        if "/" in artifact_path or "\\" in artifact_path:
            raise RuntimeError(
                f"Invalid artifact path '{artifact_path}': "
                "must be a filename, not a path (no '/' or '\\' allowed)"
            )
        if artifact_path.startswith("."):
            raise RuntimeError(f"Invalid artifact path '{artifact_path}': cannot start with '.'")

        exit_code, stdout, _ = await self.execute_bash(
            user_id, f"test -f /artifacts/{artifact_path} && echo 'exists'"
        )
        if exit_code != 0 or "exists" not in stdout:
            raise RuntimeError(f"Artifact not found: {artifact_path}")

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

        exit_code, stdout, stderr = await self.execute_bash(
            user_id, f"base64 -w 0 /artifacts/{artifact_path}"
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to encode artifact: {stderr}")

        return stdout.strip()

    def stop_container(self, user_id: str) -> None:
        if user_id in self.user_containers:
            try:
                container = self.user_containers[user_id]
                container.stop(timeout=10)
            except docker.errors.NotFound:
                pass

    def cleanup_container(self, user_id: str, force: bool) -> None:
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
        for user_id in list(self.user_containers.keys()):
            self.cleanup_container(user_id, force)

    def __del__(self):
        with contextlib.suppress(Exception):
            self.cleanup_all()
