"""Utility functions for tool discovery and metadata extraction."""

import ast
import re
from pathlib import Path

from loguru import logger


def parse_tool_docstring(content: str) -> tuple[dict, str]:
    """Parse structured metadata from a Python module's docstring.

    Extracts Name:, Description:, Version:, Dependencies: prefixes from
    the module docstring, similar to skill frontmatter parsing.

    Args:
        content: The module docstring content

    Returns:
        Tuple of (metadata_dict, remaining_description)
    """
    if not content:
        return {}, ""

    lines = content.strip().split("\n")
    metadata = {}
    description_start = 0

    # Parse prefix lines (Name:, Description:, Version:, Dependencies:)
    prefixes = ["name", "description", "version", "dependencies"]
    for i, line in enumerate(lines):
        stripped = line.strip()
        matched = False
        for prefix in prefixes:
            if stripped.lower().startswith(f"{prefix}:"):
                value = stripped.split(":", 1)[1].strip()
                metadata[prefix] = value
                matched = True
                break
        if not matched and stripped:
            description_start = i
            break

    # Remaining content is the description
    remaining = "\n".join(lines[description_start:]).strip()

    return metadata, remaining


def extract_tool_functions(content: str) -> list[str]:
    """Extract the Available Functions section from tool docstring.

    Args:
        content: Full tool module docstring

    Returns:
        List of function descriptions in format "name: description"
    """
    functions = []

    # Look for "Available Functions:" section
    pattern = r"Available Functions:\s*\n((?:[-*]\s+.+\n?)+)"
    match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)

    if match:
        functions_text = match.group(1)
        for line in functions_text.split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                # Remove bullet point and clean up
                func_desc = line.lstrip("-* ").strip()
                if func_desc:
                    functions.append(func_desc)

    return functions


def get_tool_module(module_name: str) -> dict:
    """Retrieve a tool module by name from the tools directory.

    Args:
        module_name: Name of the Python module (without .py extension)

    Returns:
        Dictionary containing tool metadata, functions, and location

    Raises:
        FileNotFoundError: If module doesn't exist
    """
    # Get the directory where this file is located
    server_dir = Path(__file__).parent.parent
    tools_dir = server_dir / "tools"
    tool_path = tools_dir / f"{module_name}.py"

    if not tool_path.exists():
        raise FileNotFoundError(f"Tool module '{module_name}' not found")

    # Parse the module to extract docstring without importing
    content = tool_path.read_text()
    tree = ast.parse(content)

    # Get module docstring
    docstring = ast.get_docstring(tree) or ""
    metadata, description = parse_tool_docstring(docstring)

    # Extract function list
    functions = extract_tool_functions(docstring)

    return {
        "module_id": module_name,
        "name": metadata.get("name", module_name),
        "description": metadata.get("description", ""),
        "version": metadata.get("version", "1.0.0"),
        "dependencies": metadata.get("dependencies", ""),
        "functions": functions,
        "location": f"/tools/{module_name}.py",
        "content": description,
    }


def list_available_tools() -> list[dict]:
    """List all available tool modules in the tools directory.

    Returns:
        List of tool metadata dictionaries
    """
    server_dir = Path(__file__).parent.parent
    tools_dir = server_dir / "tools"

    if not tools_dir.exists():
        return []

    tools = []
    for tool_file in tools_dir.glob("*.py"):
        # Skip __init__.py and private modules
        if tool_file.name.startswith("_"):
            continue

        try:
            tool_data = get_tool_module(tool_file.stem)
            # Return lightweight metadata for listing
            tools.append(
                {
                    "module_id": tool_data["module_id"],
                    "name": tool_data["name"],
                    "description": tool_data["description"],
                    "version": tool_data["version"],
                    "dependencies": tool_data["dependencies"],
                    "functions": tool_data["functions"],
                    "location": tool_data["location"],
                }
            )
        except Exception as e:
            logger.error(f"Error loading tool {tool_file.name}: {e}")

    return tools


def generate_tools_section(tools: list[dict]) -> str:
    """Generate the tools section of the agent prompt.

    Args:
        tools: List of tool metadata dictionaries

    Returns:
        Formatted markdown section describing all available tools
    """
    if not tools:
        return ""

    sections = []
    for tool in tools:
        module_id = tool["module_id"]
        name = tool["name"]
        version = tool["version"]
        description = tool["description"]
        dependencies = tool.get("dependencies", "None")
        functions = tool.get("functions", [])
        location = tool["location"]

        # Format functions list
        if functions:
            functions_list = "\n".join(f"  - `{f}`" for f in functions)
        else:
            functions_list = "  - Use `read_docstring()` to discover functions"

        # Format tool section
        section = f"""---

### **{module_id}**
**Name:** {name}
**Version:** {version}
**Description:** {description}
**Dependencies:** `{dependencies}`

**Available Functions:**
{functions_list}

**Tool location:** `{location}`
**Discover function details:** `read_docstring("{location}", "function_name")`
"""
        sections.append(section)

    return "\n".join(sections)
