import ast
import re
from pathlib import Path

from loguru import logger


def parse_tool_docstring(content: str) -> tuple[dict, str]:
    if not content:
        return {}, ""

    lines = content.strip().split("\n")
    metadata = {}
    description_start = 0

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

    remaining = "\n".join(lines[description_start:]).strip()

    return metadata, remaining


def extract_tool_functions(content: str) -> list[str]:
    functions = []

    pattern = r"Available Functions:\s*\n((?:[-*]\s+.+\n?)+)"
    match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)

    if match:
        functions_text = match.group(1)
        for line in functions_text.split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                func_desc = line.lstrip("-* ").strip()
                if func_desc:
                    functions.append(func_desc)

    return functions


def get_tool_module(module_name: str) -> dict:
    server_dir = Path(__file__).parent.parent
    tools_dir = server_dir / "tools"
    tool_path = tools_dir / f"{module_name}.py"

    if not tool_path.exists():
        raise FileNotFoundError(f"Tool module '{module_name}' not found")

    content = tool_path.read_text()
    tree = ast.parse(content)

    docstring = ast.get_docstring(tree) or ""
    metadata, description = parse_tool_docstring(docstring)

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
    server_dir = Path(__file__).parent.parent
    tools_dir = server_dir / "tools"

    if not tools_dir.exists():
        return []

    tools = []
    for tool_file in tools_dir.glob("*.py"):
        if tool_file.name.startswith("_"):
            continue

        try:
            tool_data = get_tool_module(tool_file.stem)
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

        if functions:
            functions_list = "\n".join(f"  - `{f}`" for f in functions)
        else:
            functions_list = "  - Use `read_docstring()` to discover functions"

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
