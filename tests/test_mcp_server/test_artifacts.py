"""Unit tests for artifact management functionality in DockerExecutionClient."""

import base64
import os
from unittest.mock import AsyncMock, patch

import pytest

# Add project root to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server"))

from docker_client import DockerExecutionClient


class TestListArtifacts:
    """Tests for the list_artifacts method."""

    @pytest.fixture
    def docker_client(self):
        """Create a DockerExecutionClient with mocked Docker."""
        with patch('docker.from_env'):
            client = DockerExecutionClient()
            # Mock the execute_bash method
            client.execute_bash = AsyncMock()
            return client

    async def test_list_artifacts_empty_directory(self, docker_client):
        """Test listing artifacts when directory is empty."""
        # Mock execute_bash to return empty output
        docker_client.execute_bash.return_value = (0, "", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == []
        docker_client.execute_bash.assert_called_once_with(
            "test-user",
            "find /artifacts/ -maxdepth 1 -type f -printf '%f\\n'"
        )

    async def test_list_artifacts_single_file(self, docker_client):
        """Test listing artifacts with one file."""
        docker_client.execute_bash.return_value = (0, "report.pdf\n", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == ["report.pdf"]

    async def test_list_artifacts_multiple_files(self, docker_client):
        """Test listing artifacts with multiple files."""
        # Files returned in unsorted order
        docker_client.execute_bash.return_value = (0, "chart.png\nanalysis.py\nreport.pdf\n", "")

        result = await docker_client.list_artifacts("test-user")

        # Should be sorted alphabetically
        assert result == ["analysis.py", "chart.png", "report.pdf"]

    async def test_list_artifacts_with_whitespace(self, docker_client):
        """Test listing artifacts with extra whitespace."""
        docker_client.execute_bash.return_value = (0, "  file1.txt  \n\n  file2.txt  \n", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == ["file1.txt", "file2.txt"]

    async def test_list_artifacts_command_failure(self, docker_client):
        """Test listing artifacts when command fails."""
        docker_client.execute_bash.return_value = (1, "", "Permission denied")

        with pytest.raises(RuntimeError, match="Failed to list artifacts: Permission denied"):
            await docker_client.list_artifacts("test-user")

    async def test_list_artifacts_filters_empty_lines(self, docker_client):
        """Test that empty lines are filtered out."""
        docker_client.execute_bash.return_value = (0, "file1.txt\n\n\nfile2.txt\n", "")

        result = await docker_client.list_artifacts("test-user")

        assert result == ["file1.txt", "file2.txt"]


class TestGetArtifact:
    """Tests for the get_artifact method."""

    @pytest.fixture
    def docker_client(self):
        """Create a DockerExecutionClient with mocked Docker and size limit."""
        with patch('docker.from_env'):
            # Set a small size limit for testing (1MB)
            with patch.dict(os.environ, {"MCP_ARTIFACT_SIZE_LIMIT_MB": "1"}):
                client = DockerExecutionClient()
                client.execute_bash = AsyncMock()
                return client

    async def test_get_artifact_success(self, docker_client):
        """Test successfully retrieving an artifact."""
        # Mock the three execute_bash calls: existence check, size check, base64 encoding
        test_content = "Hello, World!"
        encoded_content = base64.b64encode(test_content.encode()).decode()

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),  # File exists
            (0, "13\n", ""),  # Size in bytes
            (0, encoded_content, ""),  # Base64 encoded content
        ]

        result = await docker_client.get_artifact("test-user", "test.txt")

        assert result == encoded_content

    async def test_get_artifact_path_with_slash(self, docker_client):
        """Test that paths with slashes are rejected."""
        with pytest.raises(RuntimeError, match="Invalid artifact path.*no '/' or"):
            await docker_client.get_artifact("test-user", "subdir/file.txt")

    async def test_get_artifact_path_with_backslash(self, docker_client):
        """Test that paths with backslashes are rejected."""
        with pytest.raises(RuntimeError, match="Invalid artifact path.*no '/' or"):
            await docker_client.get_artifact("test-user", "subdir\\file.txt")

    async def test_get_artifact_path_starting_with_dot(self, docker_client):
        """Test that paths starting with '.' are rejected."""
        with pytest.raises(RuntimeError, match="Invalid artifact path.*cannot start with '.'"):
            await docker_client.get_artifact("test-user", ".hidden_file")

    async def test_get_artifact_path_with_dotdot(self, docker_client):
        """Test that path traversal attempts are rejected."""
        with pytest.raises(RuntimeError, match="Invalid artifact path"):
            await docker_client.get_artifact("test-user", "../etc/passwd")

    async def test_get_artifact_file_not_found(self, docker_client):
        """Test getting an artifact that doesn't exist."""
        # File existence check fails
        docker_client.execute_bash.return_value = (1, "", "")

        with pytest.raises(RuntimeError, match="Artifact not found: missing.txt"):
            await docker_client.get_artifact("test-user", "missing.txt")

    async def test_get_artifact_size_check_failure(self, docker_client):
        """Test when size check command fails."""
        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),  # File exists
            (1, "", "Permission denied"),  # Size check fails
        ]

        with pytest.raises(RuntimeError, match="Failed to check artifact size: Permission denied"):
            await docker_client.get_artifact("test-user", "test.txt")

    async def test_get_artifact_exceeds_size_limit(self, docker_client):
        """Test getting an artifact that exceeds size limit."""
        # 2MB file (exceeds 1MB limit set in fixture)
        file_size_bytes = 2 * 1024 * 1024

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),  # File exists
            (0, f"{file_size_bytes}\n", ""),  # Size check
        ]

        with pytest.raises(RuntimeError, match="exceeds limit"):
            await docker_client.get_artifact("test-user", "large_file.zip")

    async def test_get_artifact_at_size_limit(self, docker_client):
        """Test getting an artifact exactly at size limit (should succeed)."""
        # Exactly 1MB file (at the limit)
        file_size_bytes = 1 * 1024 * 1024
        encoded_content = "base64encodedcontent"

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),  # File exists
            (0, f"{file_size_bytes}\n", ""),  # Size check
            (0, encoded_content, ""),  # Base64 encoding
        ]

        result = await docker_client.get_artifact("test-user", "exact_size.bin")

        assert result == encoded_content

    async def test_get_artifact_encoding_failure(self, docker_client):
        """Test when base64 encoding fails."""
        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),  # File exists
            (0, "100\n", ""),  # Size check
            (1, "", "Failed to read file"),  # Encoding fails
        ]

        with pytest.raises(RuntimeError, match="Failed to encode artifact: Failed to read file"):
            await docker_client.get_artifact("test-user", "test.txt")

    async def test_get_artifact_binary_file(self, docker_client):
        """Test getting a binary file (like an image)."""
        # Simulate a small binary file
        binary_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        encoded_content = base64.b64encode(binary_data).decode()

        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),  # File exists
            (0, f"{len(binary_data)}\n", ""),  # Size check
            (0, encoded_content, ""),  # Base64 encoded content
        ]

        result = await docker_client.get_artifact("test-user", "image.png")

        assert result == encoded_content
        # Verify it can be decoded back
        decoded = base64.b64decode(result)
        assert decoded == binary_data

    async def test_get_artifact_zero_size_file(self, docker_client):
        """Test getting an empty file."""
        docker_client.execute_bash.side_effect = [
            (0, "exists\n", ""),  # File exists
            (0, "0\n", ""),  # Size is 0
            (0, "", ""),  # Empty base64 content
        ]

        result = await docker_client.get_artifact("test-user", "empty.txt")

        assert result == ""


class TestArtifactSizeLimitConfiguration:
    """Tests for artifact size limit environment variable configuration."""

    def test_default_size_limit(self):
        """Test that default size limit is 50MB."""
        with patch('docker.from_env'):
            client = DockerExecutionClient()
            assert client.artifact_size_limit_bytes == 50 * 1024 * 1024

    def test_custom_size_limit(self):
        """Test setting custom size limit via environment variable."""
        with patch('docker.from_env'), patch.dict(os.environ, {"MCP_ARTIFACT_SIZE_LIMIT_MB": "100"}):
            client = DockerExecutionClient()
            assert client.artifact_size_limit_bytes == 100 * 1024 * 1024

    def test_small_size_limit(self):
        """Test setting a small size limit (1MB)."""
        with patch('docker.from_env'), patch.dict(os.environ, {"MCP_ARTIFACT_SIZE_LIMIT_MB": "1"}):
            client = DockerExecutionClient()
            assert client.artifact_size_limit_bytes == 1 * 1024 * 1024


class TestArtifactSecurityValidation:
    """Security-focused tests for artifact path validation."""

    @pytest.fixture
    def docker_client(self):
        """Create a DockerExecutionClient with mocked Docker."""
        with patch('docker.from_env'):
            client = DockerExecutionClient()
            client.execute_bash = AsyncMock()
            return client

    @pytest.mark.parametrize("malicious_path", [
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
    ])
    async def test_reject_malicious_paths(self, docker_client, malicious_path):
        """Test that various malicious path patterns are rejected."""
        with pytest.raises(RuntimeError, match="Invalid artifact path"):
            await docker_client.get_artifact("test-user", malicious_path)

    @pytest.mark.parametrize("valid_filename", [
        "report.pdf",
        "analysis.py",
        "chart.png",
        "data.json",
        "output.txt",
        "results_2024.csv",
        "my-file.html",
    ])
    async def test_accept_valid_filenames(self, docker_client, valid_filename):
        """Test that valid filenames are accepted (up to the existence check)."""
        # Mock file doesn't exist (so it fails at existence check, not validation)
        docker_client.execute_bash.return_value = (1, "", "")

        with pytest.raises(RuntimeError, match="Artifact not found"):
            # This should pass validation but fail at existence check
            await docker_client.get_artifact("test-user", valid_filename)
