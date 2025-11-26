# Testing the Docker Execution Environment

This document provides instructions for testing the Docker-based code execution environment.

## Prerequisites

1. Docker must be installed and running
2. Current user must have Docker permissions (add user to `docker` group or use sudo)

## Building the Docker Image

```bash
cd /home/jonathankadowaki/mcp-hackathon/code_execution_with_mcp/mcp/docker
./build.sh
```

This will build the `mcp-code-executor:latest` image.

## Manual Testing

### Test 1: Verify Non-Root User

```bash
docker run --rm mcp-code-executor:latest whoami
```

Expected output: `coderunner`

### Test 2: Verify Python 3.12

```bash
docker run --rm mcp-code-executor:latest python --version
```

Expected output: `Python 3.12.x`

### Test 3: Verify Bash

```bash
docker run --rm mcp-code-executor:latest bash -c "echo Hello from bash"
```

Expected output: `Hello from bash`

### Test 4: Verify Mount Points

```bash
docker run --rm mcp-code-executor:latest ls -la / | grep -E 'tools|skills'
```

Expected: Directories `/tools` and `/skills` should be listed

### Test 5: Test with Volume Mounts

```bash
docker run --rm \
  -v /home/jonathankadowaki/mcp-hackathon/code_execution_with_mcp/tools:/tools:ro \
  -v /home/jonathankadowaki/mcp-hackathon/code_execution_with_mcp/skills:/skills:ro \
  mcp-code-executor:latest \
  ls -la /tools
```

Expected: Should list contents of the tools directory

### Test 6: Verify Read-Only Mounts

```bash
docker run --rm \
  -v /home/jonathankadowaki/mcp-hackathon/code_execution_with_mcp/tools:/tools:ro \
  mcp-code-executor:latest \
  bash -c "touch /tools/test.txt"
```

Expected: Should fail with permission denied error

## Testing DockerExecutionClient

Create a test script:

```python
import asyncio
from mcp import DockerExecutionClient

async def test_client():
    client = DockerExecutionClient()

    # Test bash execution
    exit_code, stdout, stderr = await client.execute_bash(
        "test_user_1",
        "echo 'Hello from container'"
    )
    print(f"Exit code: {exit_code}")
    print(f"Output: {stdout}")

    # Test file writing
    await client.write_file(
        "test_user_1",
        "/workspace/test.txt",
        "This is a test file"
    )

    # Test file reading
    content = await client.read_file(
        "test_user_1",
        "/workspace/test.txt"
    )
    print(f"File content: {content}")

    # Test docstring reading
    docstring = await client.read_docstring("tools.example", "greet")
    print(f"Docstring: {docstring}")

    # Cleanup
    client.cleanup_all()

if __name__ == "__main__":
    asyncio.run(test_client())
```

## Troubleshooting

### Permission Denied for Docker Socket

If you get "permission denied" errors:

```bash
# Option 1: Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Option 2: Use sudo (not recommended for production)
sudo ./build.sh
```

### Image Not Found

If containers can't find the image:

```bash
# Verify image exists
docker images | grep mcp-code-executor

# Rebuild if necessary
./build.sh
```
