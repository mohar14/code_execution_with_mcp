import base64
import os

import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server"))

from docker_client import DockerExecutionClient


class TestListArtifacts:
    @pytest.fixture
    def docker_client(self):
        with patch("docker.from_env"):
            client = DockerExecutionClient()
            client.execute_bash = AsyncMock()
            return client

    async def test_list_artifacts_empty_directory(self, docker_client):
        docker_client.execute_bash.return_value = (0, "", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == []
        docker_client.execute_bash.assert_called_once_with(
            "test-user", "find /artifacts/ -maxdepth 1 -type f -printf '%f\\n'"
        )

    async def test_list_artifacts_single_file(self, docker_client):
        docker_client.execute_bash.return_value = (0, "report.pdf\n", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == ["report.pdf"]

    async def test_list_artifacts_multiple_files(self, docker_client):
        docker_client.execute_bash.return_value = (0, "chart.png\nanalysis.py\nreport.pdf\n", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == ["analysis.py", "chart.png", "report.pdf"]

    async def test_list_artifacts_with_whitespace(self, docker_client):
        docker_client.execute_bash.return_value = (0, "  file1.txt  \n\n  file2.txt  \n", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == ["file1.txt", "file2.txt"]

    async def test_list_artifacts_command_failure(self, docker_client):
        docker_client.execute_bash.return_value = (1, "", "Permission denied")

        with pytest.raises(RuntimeError, match="Failed to list artifacts: Permission denied"):
            await docker_client.list_artifacts("test-user")

    async def test_list_artifacts_filters_empty_lines(self, docker_client):
        docker_client.execute_bash.return_value = (0, "file1.txt\n\n\nfile2.txt\n", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == ["file1.txt", "file2.txt"]


class TestGetArtifact:
    @pytest.fixture
    def docker_client(self):
        with patch("docker.from_env"):
            with patch.dict(os.environ, {"MCP_ARTIFACT_SIZE_LIMIT_MB": "1"}):
                client = DockerExecutionClient()
                client.execute_bash = AsyncMock()
                return client

    async def test_get_artifact_success(self, docker_client):
        test_content = "Hello, World!"
        encoded_content = base64.b64encode(test_content.encode()).decode()

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),
            (0, "13\n", ""),
            (0, encoded_content, ""),
        ]

        result = await docker_client.get_artifact("test-user", "test.txt")

        assert result == encoded_content

    async def test_get_artifact_path_with_slash(self, docker_client):
        with pytest.raises(RuntimeError, match="Invalid artifact path.*no '/' or"):
            await docker_client.get_artifact("test-user", "subdir/file.txt")

    async def test_get_artifact_path_with_backslash(self, docker_client):
        with pytest.raises(RuntimeError, match="Invalid artifact path.*no '/' or"):
            await docker_client.get_artifact("test-user", "subdir\\file.txt")

    async def test_get_artifact_path_starting_with_dot(self, docker_client):
        with pytest.raises(RuntimeError, match="Invalid artifact path.*cannot start with '.'"):
            await docker_client.get_artifact("test-user", ".hidden_file")

    async def test_get_artifact_path_with_dotdot(self, docker_client):
        with pytest.raises(RuntimeError, match="Invalid artifact path"):
            await docker_client.get_artifact("test-user", "../etc/passwd")

    async def test_get_artifact_file_not_found(self, docker_client):
        docker_client.execute_bash.return_value = (1, "", "")

        with pytest.raises(RuntimeError, match="Artifact not found: missing.txt"):
            await docker_client.get_artifact("test-user", "missing.txt")

    async def test_get_artifact_size_check_failure(self, docker_client):
        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),
            (1, "", "Permission denied"),
        ]

        with pytest.raises(RuntimeError, match="Failed to check artifact size: Permission denied"):
            await docker_client.get_artifact("test-user", "test.txt")

    async def test_get_artifact_exceeds_size_limit(self, docker_client):
        file_size_bytes = 2 * 1024 * 1024

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),
            (0, f"{file_size_bytes}\n", ""),
        ]

        with pytest.raises(RuntimeError, match="exceeds limit"):
            await docker_client.get_artifact("test-user", "large_file.zip")

    async def test_get_artifact_at_size_limit(self, docker_client):
        file_size_bytes = 1 * 1024 * 1024
        encoded_content = "base64encodedcontent"

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),
            (0, f"{file_size_bytes}\n", ""),
            (0, encoded_content, ""),
        ]

        result = await docker_client.get_artifact("test-user", "exact_size.bin")

        assert result == encoded_content

    async def test_get_artifact_encoding_failure(self, docker_client):
        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),
            (0, "100\n", ""),
            (1, "", "Failed to read file"),
        ]

        with pytest.raises(RuntimeError, match="Failed to encode artifact: Failed to read file"):
            await docker_client.get_artifact("test-user", "test.txt")

    async def test_get_artifact_binary_file(self, docker_client):
        binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        encoded_content = base64.b64encode(binary_data).decode()

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),
            (0, f"{len(binary_data)}\n", ""),
            (0, encoded_content, ""),
        ]

        result = await docker_client.get_artifact("test-user", "image.png")

        assert result == encoded_content
        decoded = base64.b64decode(result)
        assert decoded == binary_data

    async def test_get_artifact_zero_size_file(self, docker_client):
        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),
            (0, "0\n", ""),
            (0, "", ""),
        ]

        result = await docker_client.get_artifact("test-user", "empty.txt")

        assert result == ""


class TestArtifactSizeLimitConfiguration:
    def test_default_size_limit(self):
        with patch("docker.from_env"):
            client = DockerExecutionClient()
            assert client.artifact_size_limit_bytes == 50 * 1024 * 1024

    def test_custom_size_limit(self):
        with (
            patch("docker.from_env"),
            patch.dict(os.environ, {"MCP_ARTIFACT_SIZE_LIMIT_MB": "100"}),
        ):
            client = DockerExecutionClient()
            assert client.artifact_size_limit_bytes == 100 * 1024 * 1024

    def test_small_size_limit(self):
        with patch("docker.from_env"), patch.dict(os.environ, {"MCP_ARTIFACT_SIZE_LIMIT_MB": "1"}):
            client = DockerExecutionClient()
            assert client.artifact_size_limit_bytes == 1 * 1024 * 1024


class TestArtifactSecurityValidation:
    @pytest.fixture
    def docker_client(self):
        with patch("docker.from_env"):
            client = DockerExecutionClient()
            client.execute_bash = AsyncMock()
            return client

    @pytest.mark.parametrize(
        "malicious_path",
        [
            "../../../etc/passwd",
            "../../secrets.txt",
            "./config/database.yml",
            ".ssh/id_rsa",
            ".env",
            "subdirectory/file.txt",
            "path/to/file",
            "..\\windows\\system32",
            ".bashrc",
            ".gitignore",
        ],
    )
    async def test_reject_malicious_paths(self, docker_client, malicious_path):
        with pytest.raises(RuntimeError, match="Invalid artifact path"):
            await docker_client.get_artifact("test-user", malicious_path)

    @pytest.mark.parametrize(
        "valid_filename",
        [
            "report.pdf",
            "analysis.py",
            "chart.png",
            "data.json",
            "output.txt",
            "results_2024.csv",
            "my-file.html",
        ],
    )
    async def test_accept_valid_filenames(self, docker_client, valid_filename):
        docker_client.execute_bash.return_value = (1, "", "")

        with pytest.raises(RuntimeError, match="Artifact not found"):
            await docker_client.get_artifact("test-user", valid_filename)
