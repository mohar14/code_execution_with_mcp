# Implementation Plan: Artifact Management Methods

## Overview
Add two new async methods to `DockerExecutionClient` for managing artifacts stored in `/artifacts/` directory within user containers, following existing codebase patterns.

## Requirements Summary
1. **list_artifacts(user_id)** - List files in `/artifacts/` for a user
2. **get_artifact(user_id, artifact_path)** - Return base64-encoded artifact data with validation:
   - File must exist
   - File must be directly in `/artifacts/` (no nested paths)
   - File must be under size limit (50 MB default, configurable via env var)

## Implementation Details

### 1. DockerExecutionClient Changes (mcp_server/docker_client.py)

#### A. Environment Variable Configuration
Add to `__init__` method after existing env var setup:
```python
# Add after line 53 (after self.skills_path)
default_size_limit_mb = 50
size_limit_mb = int(os.getenv("MCP_ARTIFACT_SIZE_LIMIT_MB", default_size_limit_mb))
self.artifact_size_limit_bytes = size_limit_mb * 1024 * 1024
```

Update module docstring (lines 6-10) to document new env var:
```python
Environment Variables:
    MCP_EXECUTOR_IMAGE: Docker image name (default: mcp-code-executor:latest)
    MCP_TOOLS_PATH: Path to tools directory (default: ./tools)
    MCP_SKILLS_PATH: Path to skills directory (default: ./skills)
    MCP_ARTIFACT_SIZE_LIMIT_MB: Max artifact file size in MB (default: 50)
```

#### B. Method: list_artifacts
Add after `read_file_docstring` method (after line 264):

```python
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
    artifacts = [f.strip() for f in stdout.strip().split('\n') if f.strip()]
    return sorted(artifacts)
```

#### C. Method: get_artifact
Add after `list_artifacts` method:

```python
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
        raise RuntimeError(
            f"Invalid artifact path '{artifact_path}': cannot start with '.'"
        )

    # Step 2: File existence check
    exit_code, stdout, _ = await self.execute_bash(
        user_id,
        f"test -f /artifacts/{artifact_path} && echo 'exists'"
    )
    if exit_code != 0 or "exists" not in stdout:
        raise RuntimeError(f"Artifact not found: {artifact_path}")

    # Step 3: Size check
    exit_code, size_str, stderr = await self.execute_bash(
        user_id,
        f"wc -c < /artifacts/{artifact_path}"
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
        user_id,
        f"base64 -w 0 /artifacts/{artifact_path}"
    )
    if exit_code != 0:
        raise RuntimeError(f"Failed to encode artifact: {stderr}")

    return stdout.strip()
```

### 2. REST Endpoints Integration (mcp_server/server.py)

Add two new REST endpoints after the skills endpoints (after line 386):

#### A. List Artifacts Endpoint
```python
@mcp.custom_route("/{user_id}/artifacts", methods=["GET"])
async def list_user_artifacts(request: Request):
    """List all artifacts for a specific user.

    Args:
        request: Starlette request object (user_id extracted from path)

    Returns:
        JSON response with list of artifacts and count

    Example Response:
        {
            "artifacts": ["report.pdf", "analysis.py", "chart.png"],
            "count": 3
        }
    """
    user_id = request.path_params.get("user_id")
    logger.info(f"Listing artifacts for user {user_id}")

    try:
        artifacts = await docker_client.list_artifacts(user_id=user_id)
        logger.info(f"Found {len(artifacts)} artifacts for user {user_id}")

        return JSONResponse(
            {
                "artifacts": artifacts,
                "count": len(artifacts),
            }
        )

    except Exception as e:
        logger.error(f"Error listing artifacts for user {user_id}: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500,
        )
```

#### B. Get Artifact Endpoint
```python
@mcp.custom_route("/{user_id}/artifacts/{artifact_id}", methods=["GET"])
async def get_user_artifact(request: Request):
    """Retrieve a specific artifact as base64-encoded string.

    Args:
        request: Starlette request object (user_id and artifact_id from path)

    Returns:
        JSON response with base64-encoded artifact data

    Example Response:
        {
            "artifact_id": "report.pdf",
            "data": "JVBERi0xLjQKJeLjz9MKMy...",
            "encoding": "base64"
        }

    Error Response (404):
        {
            "error": "Artifact not found: report.pdf"
        }

    Error Response (400):
        {
            "error": "Artifact 'large.zip' is 52428800 bytes, exceeds limit of 52428800 bytes"
        }
    """
    user_id = request.path_params.get("user_id")
    artifact_id = request.path_params.get("artifact_id")
    logger.info(f"Retrieving artifact for user {user_id}: {artifact_id}")

    try:
        encoded = await docker_client.get_artifact(
            user_id=user_id,
            artifact_path=artifact_id,
        )

        logger.info(f"Successfully retrieved artifact {artifact_id} for user {user_id}")
        return JSONResponse(
            {
                "artifact_id": artifact_id,
                "data": encoded,
                "encoding": "base64",
            }
        )

    except RuntimeError as e:
        error_msg = str(e)
        logger.error(f"Error retrieving artifact for user {user_id}: {error_msg}")

        # Determine appropriate status code
        if "not found" in error_msg.lower():
            status_code = 404
        elif "invalid" in error_msg.lower() or "exceeds limit" in error_msg.lower():
            status_code = 400
        else:
            status_code = 500

        return JSONResponse(
            {"error": error_msg},
            status_code=status_code,
        )

    except Exception as e:
        logger.error(f"Unexpected error retrieving artifact for user {user_id}: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500,
        )
```

## Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| **Use `find` for listing** | Explicitly filters to regular files only; `-maxdepth 1` ensures no nested files |
| **Path validation via string checks** | Simple, fast, prevents path traversal attacks |
| **Size check before encoding** | Prevents wasting resources encoding oversized files; `wc -c` works on all Unix |
| **Base64 encoding via bash** | Handles binary files correctly; consistent with existing execute_bash pattern |
| **Env var: MCP_ARTIFACT_SIZE_LIMIT_MB** | Follows existing `MCP_*` naming convention; MB units are user-friendly |
| **Return filenames only (not paths)** | Cleaner API; matches the artifact_path parameter convention |
| **Sorted artifact list** | Predictable, testable output |

## Security Considerations

1. **Path Traversal Prevention**: Rejects any `artifact_path` containing `/`, `\`, or starting with `.`
2. **Type Validation**: Uses `find -type f` to ensure only regular files are listed
3. **Size Limits**: Enforces configurable size limit to prevent resource exhaustion
4. **User Isolation**: Leverages existing per-user container isolation

## Error Handling

All methods follow existing patterns:
- Raise `RuntimeError` with descriptive messages
- Log errors via `logger.error`
- MCP tools re-raise exceptions (let MCP framework handle them)

## Edge Cases Handled

1. **Empty /artifacts/ directory**: `list_artifacts` returns `[]` (not an error)
2. **File exactly at size limit**: Allowed (uses `>` not `>=`)
3. **Non-existent directory**: Raises RuntimeError with clear message
4. **Special characters in filenames**: Handled by bash command quoting
5. **Binary files**: Base64 encoding handles all file types

## Files to Modify

1. **mcp_server/docker_client.py**
   - Add env var configuration in `__init__` (line ~53)
   - Update module docstring (lines 6-10)
   - Add `list_artifacts` method (after line 264)
   - Add `get_artifact` method (after `list_artifacts`)

2. **mcp_server/server.py**
   - Add REST endpoint `GET /{user_id}/artifacts` (after line 386)
   - Add REST endpoint `GET /{user_id}/artifacts/{artifact_id}` (after list endpoint)

## Testing Recommendations

1. Test path validation (reject nested paths, paths with `.`)
2. Test size limit enforcement (files at, below, above limit)
3. Test empty artifacts directory
4. Test non-existent files
5. Test binary file encoding/decoding roundtrip
6. Test MCP tool integration with real containers
