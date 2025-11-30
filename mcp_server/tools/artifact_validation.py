"""
Name: Artifact Validation
Description: Tools for validating artifacts including images, Python scripts, and data files (JSON, CSV) before saving to /artifacts/.
Version: 1.0.0
Dependencies: pillow>=10.0.0

This module provides validation utilities to ensure artifacts meet
requirements before saving. Use these helpers to validate file format,
size, structure, and content integrity.

Available Functions:
- validate_image: Validate image files (PNG, JPG, SVG)
- validate_python_script: Validate Python syntax and structure
- validate_json: Validate JSON format and optional schema
- validate_csv: Validate CSV structure and data types
- validate_artifact_path: Ensure path meets artifact directory rules
- get_file_info: Get metadata about a file
"""

import ast
import csv
import json
from io import StringIO
from pathlib import Path


def validate_image(file_path: str, max_size_mb: float = 50.0) -> dict:
    """Validate an image file for format, dimensions, and integrity.

    Checks that an image file is valid, not corrupted, and within
    size limits. Supports PNG, JPG, JPEG, GIF, and SVG formats.

    Args:
        file_path: Path to the image file to validate
        max_size_mb: Maximum file size in megabytes (default: 50)

    Returns:
        Dictionary with validation results:
        - valid: bool indicating if image is valid
        - format: detected image format
        - dimensions: tuple of (width, height) if applicable
        - size_bytes: file size in bytes
        - errors: list of error messages (empty if valid)

    Example:
        >>> result = validate_image("/artifacts/chart.png")
        >>> if result['valid']:
        ...     print(f"Valid {result['format']} image: {result['dimensions']}")
        ... else:
        ...     print(f"Invalid: {result['errors']}")
    """
    result = {
        "valid": False,
        "format": None,
        "dimensions": None,
        "size_bytes": 0,
        "errors": [],
    }

    path = Path(file_path)

    # Check file exists
    if not path.exists():
        result["errors"].append(f"File not found: {file_path}")
        return result

    # Check file size
    size_bytes = path.stat().st_size
    result["size_bytes"] = size_bytes
    max_bytes = max_size_mb * 1024 * 1024

    if size_bytes > max_bytes:
        result["errors"].append(f"File size {size_bytes} exceeds limit {max_bytes}")
        return result

    # Check extension
    ext = path.suffix.lower()
    if ext == ".svg":
        result["format"] = "SVG"
        # SVG validation - check it's valid XML
        try:
            content = path.read_text()
            if "<svg" not in content.lower():
                result["errors"].append("Not a valid SVG file")
                return result
            result["valid"] = True
        except Exception as e:
            result["errors"].append(f"SVG parse error: {e}")
        return result

    # For raster images, try to open with PIL
    try:
        from PIL import Image

        with Image.open(file_path) as img:
            result["format"] = img.format
            result["dimensions"] = img.size
            img.verify()  # Check for corruption
            result["valid"] = True
    except ImportError:
        result["errors"].append("PIL not available for image validation")
    except Exception as e:
        result["errors"].append(f"Image validation error: {e}")

    return result


def validate_python_script(file_path: str | None = None, content: str | None = None) -> dict:
    """Validate Python script syntax and basic structure.

    Parses Python code to check for syntax errors and optionally
    analyzes imports and function definitions.

    Args:
        file_path: Path to Python file (provide this OR content)
        content: Python source code as string (provide this OR file_path)

    Returns:
        Dictionary with validation results:
        - valid: bool indicating if syntax is valid
        - imports: list of imported modules
        - functions: list of defined function names
        - classes: list of defined class names
        - errors: list of error messages

    Example:
        >>> result = validate_python_script(content="def hello(): print('hi')")
        >>> print(result)
        {'valid': True, 'imports': [], 'functions': ['hello'], 'classes': [], 'errors': []}
    """
    result = {
        "valid": False,
        "imports": [],
        "functions": [],
        "classes": [],
        "errors": [],
    }

    # Get content
    if file_path:
        try:
            content = Path(file_path).read_text()
        except Exception as e:
            result["errors"].append(f"Could not read file: {e}")
            return result

    if not content:
        result["errors"].append("No content provided")
        return result

    # Parse the AST
    try:
        tree = ast.parse(content)
        result["valid"] = True

        # Extract imports, functions, classes
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                result["imports"].append(node.module or "")
            elif isinstance(node, ast.FunctionDef):
                result["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                result["classes"].append(node.name)

    except SyntaxError as e:
        result["errors"].append(f"Syntax error at line {e.lineno}: {e.msg}")
    except Exception as e:
        result["errors"].append(f"Parse error: {e}")

    return result


def validate_json(
    file_path: str | None = None, content: str | None = None, schema: dict | None = None
) -> dict:
    """Validate JSON format and optionally check against a schema.

    Parses JSON content and validates structure. Can optionally
    validate against a JSON Schema if provided.

    Args:
        file_path: Path to JSON file (provide this OR content)
        content: JSON string (provide this OR file_path)
        schema: Optional JSON Schema dict for validation

    Returns:
        Dictionary with validation results:
        - valid: bool indicating if JSON is valid
        - data_type: type of root element (object, array, etc.)
        - key_count: number of keys if object, length if array
        - errors: list of error messages

    Example:
        >>> result = validate_json(content='{"name": "test", "value": 42}')
        >>> print(result['valid'], result['data_type'])
        True dict
    """
    result = {
        "valid": False,
        "data_type": None,
        "key_count": 0,
        "errors": [],
    }

    # Get content
    if file_path:
        try:
            content = Path(file_path).read_text()
        except Exception as e:
            result["errors"].append(f"Could not read file: {e}")
            return result

    if not content:
        result["errors"].append("No content provided")
        return result

    # Parse JSON
    try:
        data = json.loads(content)
        result["valid"] = True
        result["data_type"] = type(data).__name__

        if isinstance(data, dict | list):
            result["key_count"] = len(data)

    except json.JSONDecodeError as e:
        result["errors"].append(f"JSON parse error at line {e.lineno}: {e.msg}")
        return result

    # Optional schema validation
    if schema and result["valid"]:
        try:
            import jsonschema

            jsonschema.validate(data, schema)
        except ImportError:
            result["errors"].append("jsonschema not available for schema validation")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Schema validation error: {e}")

    return result


def validate_csv(
    file_path: str | None = None, content: str | None = None, expected_columns: list | None = None
) -> dict:
    """Validate CSV structure and data consistency.

    Parses CSV content to verify format, column consistency,
    and optionally check for expected column headers.

    Args:
        file_path: Path to CSV file (provide this OR content)
        content: CSV string (provide this OR file_path)
        expected_columns: Optional list of expected column names

    Returns:
        Dictionary with validation results:
        - valid: bool indicating if CSV is valid
        - row_count: number of data rows (excluding header)
        - column_count: number of columns
        - columns: list of column headers
        - errors: list of error messages

    Example:
        >>> csv_content = "name,age\\nAlice,30\\nBob,25"
        >>> result = validate_csv(content=csv_content)
        >>> print(result['columns'], result['row_count'])
        ['name', 'age'] 2
    """
    result = {
        "valid": False,
        "row_count": 0,
        "column_count": 0,
        "columns": [],
        "errors": [],
    }

    # Get content
    if file_path:
        try:
            content = Path(file_path).read_text()
        except Exception as e:
            result["errors"].append(f"Could not read file: {e}")
            return result

    if not content:
        result["errors"].append("No content provided")
        return result

    # Parse CSV
    try:
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        if not rows:
            result["errors"].append("Empty CSV")
            return result

        # Get headers and validate consistency
        headers = rows[0]
        result["columns"] = headers
        result["column_count"] = len(headers)
        result["row_count"] = len(rows) - 1

        # Check column consistency
        for i, row in enumerate(rows[1:], start=2):
            if len(row) != len(headers):
                result["errors"].append(f"Row {i} has {len(row)} columns, expected {len(headers)}")

        # Check expected columns
        if expected_columns:
            missing = set(expected_columns) - set(headers)
            if missing:
                result["errors"].append(f"Missing expected columns: {missing}")

        if not result["errors"]:
            result["valid"] = True

    except csv.Error as e:
        result["errors"].append(f"CSV parse error: {e}")

    return result


def validate_artifact_path(filename: str) -> dict:
    """Ensure a filename meets artifact directory requirements.

    Validates that a filename is safe for the /artifacts/ directory:
    - No path separators (must be filename only)
    - No hidden files (starting with .)
    - Valid characters only

    Args:
        filename: The filename to validate (not a full path)

    Returns:
        Dictionary with validation results:
        - valid: bool indicating if filename is valid
        - errors: list of error messages

    Example:
        >>> validate_artifact_path("report.pdf")
        {'valid': True, 'errors': []}
        >>> validate_artifact_path("../etc/passwd")
        {'valid': False, 'errors': ['Path traversal detected...']}
    """
    result = {"valid": False, "errors": []}

    # Check for path separators
    if "/" in filename or "\\" in filename:
        result["errors"].append("Path traversal detected: filename cannot contain / or \\")
        return result

    # Check for hidden files
    if filename.startswith("."):
        result["errors"].append("Hidden files not allowed: filename cannot start with .")
        return result

    # Check for empty or whitespace-only
    if not filename or not filename.strip():
        result["errors"].append("Filename cannot be empty")
        return result

    result["valid"] = True
    return result


def get_file_info(file_path: str) -> dict:
    """Get metadata about a file.

    Returns comprehensive information about a file including
    size, modification time, and detected type.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file metadata:
        - exists: bool indicating if file exists
        - size_bytes: file size in bytes
        - size_human: human-readable size string
        - extension: file extension (lowercase)
        - filename: base filename
        - errors: list of error messages

    Example:
        >>> info = get_file_info("/artifacts/chart.png")
        >>> print(f"{info['filename']}: {info['size_human']}")
        chart.png: 125.3 KB
    """
    result = {
        "exists": False,
        "size_bytes": 0,
        "size_human": "0 B",
        "extension": "",
        "filename": "",
        "errors": [],
    }

    path = Path(file_path)
    result["filename"] = path.name
    result["extension"] = path.suffix.lower()

    if not path.exists():
        result["errors"].append(f"File not found: {file_path}")
        return result

    result["exists"] = True
    size = path.stat().st_size
    result["size_bytes"] = size

    # Human-readable size
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            result["size_human"] = f"{size:.1f} {unit}"
            break
        size /= 1024

    return result
