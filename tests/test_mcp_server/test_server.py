"""Integration tests for MCP server following FastMCP patterns."""

import re

import numpy as np
import pytest
from fastmcp.client import Client as FastMCPClient


class TestServerSetup:
    """Tests for server initialization and tool registration."""

    async def test_list_tools(self, mcp_client: FastMCPClient):
        """Test that all expected tools are registered."""
        result = await mcp_client.list_tools()

        tool_names = [tool.name for tool in result]

        # Verify all expected tools are registered
        assert "execute_bash" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "read_docstring" in tool_names

        # Verify we have exactly 4 tools
        assert len(result) == 4

    async def test_tool_metadata(self, mcp_client: FastMCPClient):
        """Test that tools have proper descriptions."""
        tools = await mcp_client.list_tools()

        for tool in tools:
            assert tool.description
            assert tool.inputSchema
            assert tool.inputSchema.get("properties")


class TestExecuteBashTool:
    """Tests for the execute_bash MCP tool."""

    async def test_simple_echo_command(self, mcp_client: FastMCPClient):
        """Test executing a simple echo command."""
        result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={
                "command": "echo 'Hello, World!'",
                "timeout": 30,
            },
        )

        assert result.content[0].text
        output = eval(result.content[0].text)  # Parse dict from string
        assert output["exit_code"] == 0
        assert "Hello, World!" in output["stdout"]

    @pytest.mark.parametrize(
        "command,expected_in_output",
        [
            ("python --version", "Python 3.12"),
            ("whoami", "coderunner"),
            ("pwd", "/workspace"),
            ("echo 'test'", "test"),
        ],
    )
    async def test_various_commands(
        self, mcp_client: FastMCPClient, command: str, expected_in_output: str
    ):
        """Test various bash commands using parametrized tests."""
        result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={"command": command},
        )

        output = eval(result.content[0].text)
        assert output["exit_code"] == 0
        assert expected_in_output in output["stdout"]

    async def test_failing_command(self, mcp_client: FastMCPClient):
        """Test that failing commands return non-zero exit code."""
        result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={"command": "exit 1"},
        )

        output = eval(result.content[0].text)
        assert output["exit_code"] == 1

    async def test_command_with_stderr(self, mcp_client: FastMCPClient):
        """Test command that writes to stderr."""
        result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={"command": "ls /nonexistent 2>&1"},
        )

        output = eval(result.content[0].text)
        assert output["exit_code"] != 0

    async def test_timeout_parameter(self, mcp_client: FastMCPClient):
        """Test custom timeout parameter."""
        result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={
                "command": "sleep 1 && echo 'done'",
                "timeout": 5,
            },
        )

        output = eval(result.content[0].text)
        assert output["exit_code"] == 0
        assert "done" in output["stdout"]


class TestWriteFileTool:
    """Tests for the write_file MCP tool."""

    async def test_write_simple_file(self, mcp_client: FastMCPClient):
        """Test writing a simple text file."""
        result = await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/test.txt",
                "content": "Hello from test!",
            },
        )

        assert result.content[0].text
        assert "Successfully wrote" in result.content[0].text
        assert "/workspace/test.txt" in result.content[0].text

    @pytest.mark.parametrize(
        "filename,content",
        [
            ("simple.txt", "Simple content"),
            ("multiline.txt", "Line 1\nLine 2\nLine 3"),
            ("script.py", "print('Hello, World!')"),
            ("data.json", '{"key": "value"}'),
        ],
    )
    async def test_write_various_files(
        self, mcp_client: FastMCPClient, filename: str, content: str
    ):
        """Test writing various file types."""
        result = await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": f"/workspace/{filename}",
                "content": content,
            },
        )

        assert "Successfully wrote" in result.content[0].text

    async def test_write_python_script(self, mcp_client: FastMCPClient):
        """Test writing a Python script with special characters and executing it."""
        python_code = '''def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
'''

        # Write the Python script
        write_result = await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/greet.py",
                "content": python_code,
            },
        )

        assert "Successfully wrote" in write_result.content[0].text

        # Execute the Python script
        exec_result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={
                "command": "python /workspace/greet.py",
            },
        )

        output = eval(exec_result.content[0].text)
        assert output["exit_code"] == 0
        assert "Hello, World!" in output["stdout"]


class TestReadFileTool:
    """Tests for the read_file MCP tool."""

    async def test_read_written_file(self, mcp_client: FastMCPClient):
        """Test reading a file that was just written."""
        content = "Test content for reading"

        # Write file
        await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/read_test.txt",
                "content": content,
            },
        )

        # Read file
        result = await mcp_client.call_tool(
            name="read_file",
            arguments={"file_path": "/workspace/read_test.txt"},
        )

        assert result.content[0].text == content

    async def test_read_with_offset(self, mcp_client: FastMCPClient):
        """Test reading file with line offset."""
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"

        # Write file
        await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/offset_test.txt",
                "content": content,
            },
        )

        # Read with offset
        result = await mcp_client.call_tool(
            name="read_file",
            arguments={
                "file_path": "/workspace/offset_test.txt",
                "offset": 2,
                "line_count": 2,
            },
        )

        read_content = result.content[0].text
        assert "Line 3" in read_content
        assert "Line 4" in read_content
        assert "Line 1" not in read_content

    @pytest.mark.parametrize(
        "offset,line_count",
        [
            (0, 1),   # First line only
            (0, 3),   # First three lines
            (2, 2),   # Lines 3-4
            (4, 10),  # Last line (more than available)
        ],
    )
    async def test_read_pagination(
        self, mcp_client: FastMCPClient, offset: int, line_count: int
    ):
        """Test file reading with various pagination parameters."""
        content = "\n".join([f"Line {i}" for i in range(1, 11)])

        # Write file
        await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/paginated.txt",
                "content": content,
            },
        )

        # Read with pagination
        result = await mcp_client.call_tool(
            name="read_file",
            arguments={
                "file_path": "/workspace/paginated.txt",
                "offset": offset,
                "line_count": line_count,
            },
        )

        assert result.content[0].text


class TestReadDocstringTool:
    """Tests for the read_docstring MCP tool."""

    async def test_read_greet_docstring(self, mcp_client: FastMCPClient):
        """Test reading docstring from a written Python file."""
        # Write a Python file with a function
        python_code = '''def greet(name):
    """Generate a greeting message.

    Args:
        name: The name to greet

    Returns:
        A greeting string
    """
    return f"Hello, {name}!"
'''

        await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/greet_module.py",
                "content": python_code,
            },
        )

        # Read the docstring
        result = await mcp_client.call_tool(
            name="read_docstring",
            arguments={
                "file_path": "/workspace/greet_module.py",
                "function_name": "greet",
            },
        )

        docstring = result.content[0].text
        assert docstring
        assert "greeting" in docstring.lower()

    @pytest.mark.parametrize(
        "function_name,function_code,expected_in_docstring",
        [
            (
                "add_numbers",
                '''def add_numbers(a, b):
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b
''',
                "add two numbers",
            ),
            (
                "calculate_sum",
                '''def calculate_sum(numbers):
    """Calculate the sum of a list of numbers.

    Args:
        numbers: List of numbers to sum

    Returns:
        Total sum
    """
    return sum(numbers)
''',
                "sum of a list",
            ),
        ],
    )
    async def test_read_various_docstrings(
        self, mcp_client: FastMCPClient, function_name: str, function_code: str, expected_in_docstring: str
    ):
        """Test reading docstrings from various functions."""
        # Write the function to a file
        await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": f"/workspace/{function_name}_module.py",
                "content": function_code,
            },
        )

        # Read the docstring
        result = await mcp_client.call_tool(
            name="read_docstring",
            arguments={
                "file_path": f"/workspace/{function_name}_module.py",
                "function_name": function_name,
            },
        )

        docstring = result.content[0].text
        assert docstring
        assert expected_in_docstring.lower() in docstring.lower()


class TestWorkflows:
    """Integration tests for complete workflows."""

    async def test_write_execute_read_workflow(self, mcp_client: FastMCPClient):
        """Test complete workflow: write script, execute, read output."""
        # Write Python script
        script = """
result = 2 + 2
print(f"Result: {result}")
with open("/workspace/result.txt", "w") as f:
    f.write(str(result))
"""

        await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/calculate.py",
                "content": script,
            },
        )

        # Execute script
        exec_result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={"command": "python /workspace/calculate.py"},
        )

        output = eval(exec_result.content[0].text)
        assert output["exit_code"] == 0
        assert "Result: 4" in output["stdout"]

        # Read result file
        read_result = await mcp_client.call_tool(
            name="read_file",
            arguments={"file_path": "/workspace/result.txt"},
        )

        assert "4" in read_result.content[0].text

    async def test_data_analysis_workflow(self, mcp_client: FastMCPClient):
        """Test data analysis using numpy and pandas."""
        script = """
import numpy as np
import pandas as pd

data = pd.DataFrame({
    'x': [1, 2, 3, 4, 5],
    'y': [2, 4, 6, 8, 10]
})

correlation = data['x'].corr(data['y'])
print(f"Correlation: {correlation}")
print(f"Mean x: {data['x'].mean()}")
print(f"Mean y: {data['y'].mean()}")
"""

        await mcp_client.call_tool(
            name="write_file",
            arguments={
                "file_path": "/workspace/analysis.py",
                "content": script,
            },
        )

        result = await mcp_client.call_tool(
            name="execute_bash",
            arguments={
                "command": "python /workspace/analysis.py",
                "timeout": 60,
            },
        )
        corr_pattern = r"""Correlation: ([0-9]+\.[0-9]+)"""
        match_ = re.search(corr_pattern, result.content[0].text)
        output = eval(result.content[0].text)
        assert output["exit_code"] == 0
        assert match_ is not None and np.isclose(float(match_.group(1)), 1.0)
        assert "Mean x: 3.0" in output["stdout"]


class TestUserIsolation:
    """Tests for user container isolation."""

    async def test_different_users_isolated(self, monkeypatch):
        """Test that different users cannot access each other's files."""
        from fastmcp.client import Client as FastMCPClient
        import server

        # Test with user1
        def mock_get_user_id_user1(ctx):
            return "user1"

        monkeypatch.setattr(server, "get_user_id", mock_get_user_id_user1)

        async with FastMCPClient(transport=server.mcp) as client1:
            # Write file for user1
            await client1.call_tool(
                name="write_file",
                arguments={
                    "file_path": "/workspace/user_data.txt",
                    "content": "User1 specific data",
                },
            )

        # Test with user2
        def mock_get_user_id_user2(ctx):
            return "user2"

        monkeypatch.setattr(server, "get_user_id", mock_get_user_id_user2)

        async with FastMCPClient(transport=server.mcp) as client2:
            # Try to read user1's file as user2 (should fail)
            result = await client2.call_tool(
                name="execute_bash",
                arguments={"command": "cat /workspace/user_data.txt"},
            )

            output = eval(result.content[0].text)
            # File should not exist for user2
            assert output["exit_code"] != 0
            assert "No such file" in output["stderr"] or "No such file" in output["stdout"]


class TestSkillsEndpoints:
    """Tests for the skills API functionality."""

    def test_parse_skill_frontmatter(self):
        """Test parsing YAML frontmatter from skill markdown."""
        from utils.skill_utils import parse_skill_frontmatter

        content = """---
name: Test Skill
description: A test skill
version: 1.0.0
dependencies: numpy>=1.0
---

# Test Content

This is the skill body.
"""
        metadata, body = parse_skill_frontmatter(content)

        assert metadata["name"] == "Test Skill"
        assert metadata["description"] == "A test skill"
        assert metadata["version"] == "1.0.0"
        assert metadata["dependencies"] == "numpy>=1.0"
        assert "# Test Content" in body

    def test_list_available_skills(self):
        """Test listing all available skills."""
        from utils.skill_utils import list_available_skills

        skills = list_available_skills()

        assert isinstance(skills, list)
        assert len(skills) >= 1  # At least the symbolic-computation skill

        # Find the symbolic-computation skill
        sympy_skill = next((s for s in skills if s["skill_id"] == "symbolic-computation"), None)
        assert sympy_skill is not None
        assert sympy_skill["name"] == "Symbolic Computation"
        assert "sympy" in sympy_skill["description"].lower()
        assert sympy_skill["version"] == "1.0.0"

    def test_get_skill(self):
        """Test retrieving a specific skill by name."""
        from utils.skill_utils import get_skill

        skill_data = get_skill("symbolic-computation")

        # Verify metadata
        assert skill_data["skill_id"] == "symbolic-computation"
        assert skill_data["name"] == "Symbolic Computation"
        assert "sympy" in skill_data["description"].lower()
        assert skill_data["version"] == "1.0.0"
        assert "sympy" in skill_data["dependencies"].lower()

        # Verify content is present
        assert skill_data["content"]
        assert "SymPy" in skill_data["content"]
        assert "Calculus" in skill_data["content"]
        assert "derivatives" in skill_data["content"].lower()

    def test_get_nonexistent_skill(self):
        """Test requesting a skill that doesn't exist."""
        from utils.skill_utils import get_skill
        import pytest

        with pytest.raises(FileNotFoundError, match="not found"):
            get_skill("nonexistent-skill")

    async def test_agent_system_prompt(self, mcp_client: FastMCPClient):
        """Test the agent_system_prompt MCP prompt."""
        # List prompts
        prompts = await mcp_client.list_prompts()
        prompt_names = [p.name for p in prompts]

        assert "agent_system_prompt" in prompt_names

        # Get the prompt
        result = await mcp_client.get_prompt("agent_system_prompt")

        assert result.messages
        assert len(result.messages) > 0

        prompt_text = result.messages[0].content.text

        # Verify key sections
        assert "Agentic Code Execution with Domain Skills" in prompt_text
        assert "Available Skills" in prompt_text
        assert "symbolic-computation" in prompt_text
        assert "/skills/" in prompt_text
        assert "read_file" in prompt_text

        # Verify NO API calls
        assert "curl" not in prompt_text.lower()
        assert "http://" not in prompt_text

        # Verify NO package installation
        assert "pip install" not in prompt_text
