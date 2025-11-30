"""
Name: Artifact Validation
Description: Validation utility for artifacts saved to /artifacts/, with syntax checking for JSON, Python, and CSV files.
Version: 2.0.0
Dependencies: None

This module provides a single validation function to ensure artifacts meet
requirements: allowed extension, valid path, size limit, no nesting, and
syntax validation for structured file types (JSON, Python, CSV).

Available Functions:
- validate_artifact: Returns JSON string with validation details for artifacts, including checks for: existence, size, path, and syntax
"""

import ast
import csv
import json
import os
from pathlib import Path

# Allowed artifact file extensions
ALLOWED_EXTENSIONS = {".py", ".md", ".txt", ".png", ".csv", ".json"}


def validate_artifact(artifact_path: str) -> dict:
    """Validate an artifact before saving to /artifacts/.

    Performs essential validation checks:
    1. Extension is one of: .py, .md, .txt, .png, .csv, .json
    2. Path exists
    3. File size is less than MCP_ARTIFACT_SIZE_LIMIT_MB (env var, default 50MB)
    4. Path is in /artifacts/ directory with no nested subdirectories
    5. Syntax validation for specific file types:
       - .json: Parse to ensure valid JSON
       - .py: Parse AST to check Python syntax
       - .csv: Parse to ensure valid CSV structure

    Args:
        artifact_path: Full path to the artifact file (e.g., "/artifacts/report.pdf")

    Returns:
        JSON string with validation results:
        - valid: bool indicating if artifact passes all checks
        - errors: list of error messages (empty if valid)
        - file_size_bytes: file size in bytes (0 if file doesn't exist)
        - extension: file extension (lowercase)

    Example:
        >>> result = validate_artifact("/artifacts/data.csv")
        >>> print(result)
    """
    result = {
        "valid": False,
        "errors": [],
        "file_size_bytes": 0,
        "extension": "",
    }

    path = Path(artifact_path)
    ext = path.suffix.lower()
    result["extension"] = ext

    # 1. Extension Validation
    if ext not in ALLOWED_EXTENSIONS:
        result["errors"].append(
            f"Extension '{ext}' not allowed. Must be one of: {sorted(ALLOWED_EXTENSIONS)}"
        )
        # Continue with other checks even if extension is invalid

    # 2. Path Existence
    file_exists = path.exists()
    if not file_exists:
        result["errors"].append(f"File not found: {artifact_path}")
        # Continue with other checks but file_size_bytes remains 0

    # 3. Size Limit Check
    if file_exists:
        # Read from environment variable
        default_size_limit_mb = 50
        size_limit_mb = int(os.getenv("MCP_ARTIFACT_SIZE_LIMIT_MB", default_size_limit_mb))
        size_limit_bytes = size_limit_mb * 1024 * 1024

        file_size_bytes = path.stat().st_size
        result["file_size_bytes"] = file_size_bytes

        if file_size_bytes > size_limit_bytes:
            result["errors"].append(
                f"File size {file_size_bytes} bytes exceeds limit of {size_limit_bytes} bytes "
                f"({size_limit_mb}MB)"
            )

    # 4. Artifact Path Validation
    # Resolve to absolute path to handle symlinks and relative paths
    try:
        resolved_path = path.resolve()
        artifacts_dir = Path("/artifacts").resolve()

        # Check if path is within /artifacts/
        relative_path = resolved_path.relative_to(artifacts_dir)

        # Check for nested directories - should have no parent
        if relative_path.parent != Path("."):
            result["errors"].append(
                "Artifacts cannot be in nested directories. Must be directly in /artifacts/"
            )
    except ValueError:
        result["errors"].append(f"Path must be within /artifacts/ directory, got: {artifact_path}")

    # 5. Syntax Validation (Extension-Specific)
    # Only perform syntax validation if file exists and extension is valid
    if file_exists and ext in ALLOWED_EXTENSIONS:
        # JSON Validation
        if ext == ".json":
            try:
                content = path.read_text()
                json.loads(content)  # Parse to validate JSON
            except json.JSONDecodeError as e:
                result["errors"].append(f"Invalid JSON syntax at line {e.lineno}: {e.msg}")
            except Exception as e:
                result["errors"].append(f"JSON validation error: {e}")

        # Python Validation
        elif ext == ".py":
            try:
                content = path.read_text()
                ast.parse(content)  # Parse AST to validate Python syntax
            except SyntaxError as e:
                result["errors"].append(f"Python syntax error at line {e.lineno}: {e.msg}")
            except Exception as e:
                result["errors"].append(f"Python validation error: {e}")

        # CSV Validation
        elif ext == ".csv":
            try:
                sample_row_count = 10
                rows = []
                with open(path) as fin:
                    reader = csv.reader(fin)
                    for k, row in enumerate(reader, start=1):
                        rows.append(row)
                        if k == sample_row_count:
                            break

                if not rows:
                    result["errors"].append("CSV file is empty")
                else:
                    # Check column consistency
                    header_count = len(rows[0])
                    for i, row in enumerate(rows[1:], start=2):
                        if len(row) != header_count:
                            result["errors"].append(
                                f"CSV row {i} has {len(row)} columns, expected {header_count}"
                            )
                            break  # Only report first inconsistency

            except csv.Error as e:
                result["errors"].append(f"Invalid CSV format: {e}")
            except Exception as e:
                result["errors"].append(f"CSV validation error: {e}")

    # Set valid flag based on whether there are any errors
    result["valid"] = len(result["errors"]) == 0

    return json.dumps(result, separators=(":", ","), sort_keys=True)
