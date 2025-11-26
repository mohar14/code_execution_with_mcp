# Running MCP Code Executor in Docker (Docker-in-Docker)

This guide explains how to run the MCP code execution system from within a Docker container, allowing a containerized MCP server to manage code execution containers.

---

## Table of Contents

1. [Overview](#overview)
2. [Approach: Docker Socket Mounting](#approach-docker-socket-mounting)
3. [Quick Start](#quick-start)
4. [Production Setup](#production-setup)
5. [Security Considerations](#security-considerations)
6. [Alternative Approaches](#alternative-approaches)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### The Challenge

The `DockerExecutionClient` needs to create and manage Docker containers. When running the MCP server itself in a container, we need to give it access to Docker.

### Solution Options

| Approach | Pros | Cons | Recommended |
|----------|------|------|-------------|
| **Docker Socket Mounting** | Simple, efficient, uses host Docker | Security risks, needs socket access | ✅ Development |
| **Docker-in-Docker (DinD)** | Isolated Docker daemon | Complex, privileged mode required | ⚠️ CI/CD only |
| **Remote Docker API** | Network isolation possible | Additional infrastructure | 🔧 Production |

---

## Approach: Docker Socket Mounting

Mount the host's Docker socket into the container, allowing the containerized MCP server to control the host's Docker daemon.

### Architecture

```
Host Machine
├── Docker Daemon (socket: /var/run/docker.sock)
│
├── MCP Server Container
│   ├── Python app (DockerExecutionClient)
│   ├── Mounted: /var/run/docker.sock
│   └── Creates → Code Execution Containers (siblings on host)
│
└── Code Execution Containers (managed by MCP)
    ├── user1-container
    ├── user2-container
    └── ...
```

**Note:** Execution containers run as **siblings** to the MCP container, not children.

---

## Quick Start

### Option 1: Docker Run Command

```bash
# Build the MCP server image (create this Dockerfile separately)
docker build -t mcp-server -f mcp/docker/Dockerfile.server .

# Run with Docker socket mounted
docker run -d \
  --name mcp-server \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/tools:/tools:ro \
  -v $(pwd)/skills:/skills:ro \
  -p 8000:8000 \
  mcp-server
```

### Option 2: Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mcp-server:
    build:
      context: .
      dockerfile: mcp/docker/Dockerfile.server
    container_name: mcp-server
    volumes:
      # Mount Docker socket for container management
      - /var/run/docker.sock:/var/run/docker.sock
      # Mount tools and skills as read-only
      - ./tools:/tools:ro
      - ./skills:/skills:ro
      # Optional: persist data
      - mcp-data:/app/data
    ports:
      - "8000:8000"
    environment:
      - DOCKER_HOST=unix:///var/run/docker.sock
      - MCP_EXECUTOR_IMAGE=mcp-code-executor:latest
    restart: unless-stopped
    # Add docker group GID to allow socket access
    group_add:
      - ${DOCKER_GID:-999}

volumes:
  mcp-data:
```

**Start the system:**

```bash
# Set Docker group ID (find with: getent group docker | cut -d: -f3)
export DOCKER_GID=$(getent group docker | cut -d: -f3)

# Start services
docker-compose up -d

# View logs
docker-compose logs -f mcp-server
```

---

## Production Setup

### 1. Create MCP Server Dockerfile

Create `mcp/docker/Dockerfile.server`:

```dockerfile
FROM python:3.12-slim

# Install Docker CLI (not daemon - we'll use host's daemon)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | \
       gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create app user (will be added to docker group at runtime)
RUN useradd -m -u 1000 -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mcp/ ./mcp/
COPY tools/ /tools/
COPY skills/ /skills/

# Create data directory
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Switch to app user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the MCP server
CMD ["python", "-m", "mcp.server"]
```

### 2. Handle Docker Socket Permissions

**Option A: Add user to docker group (in entrypoint script)**

Create `mcp/docker/entrypoint.sh`:

```bash
#!/bin/bash
set -e

# Get Docker socket GID
DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)

# Add appuser to a group with that GID
if ! getent group $DOCKER_SOCKET_GID > /dev/null; then
    sudo groupadd -g $DOCKER_SOCKET_GID dockerhost
fi
sudo usermod -aG $DOCKER_SOCKET_GID appuser

# Execute the main command
exec "$@"
```

**Option B: Run as root (simpler but less secure)**

```dockerfile
# In Dockerfile.server, remove USER appuser line
# Container runs as root, but execution containers still run as non-root
```

### 3. Pre-pull Code Executor Image

Ensure the execution container image is available:

```bash
# Build the code executor image on host
cd mcp/docker
./build.sh

# Or add to docker-compose.yml
services:
  code-executor-builder:
    build:
      context: .
      dockerfile: mcp/docker/Dockerfile
    image: mcp-code-executor:latest
    command: /bin/true  # Just build, don't run
```

### 4. Update DockerExecutionClient

Ensure the client can find the Docker socket:

```python
# mcp/docker_client.py
import docker
import os

class DockerExecutionClient:
    def __init__(
        self,
        image_name: str = "mcp-code-executor:latest",
        tools_path: str | None = None,
        skills_path: str | None = None,
    ):
        # Use environment variable or default socket
        docker_host = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
        self.client = docker.DockerClient(base_url=docker_host)
        # ... rest of initialization
```

---

## Security Considerations

### ⚠️ Critical Warnings

1. **Docker Socket = Root Access**
   - Mounting `/var/run/docker.sock` gives **full control** of the host Docker daemon
   - Any container with socket access can create privileged containers
   - Equivalent to giving root access to the host

2. **Container Escape Risk**
   - A compromised MCP server container can compromise the entire host
   - Malicious code could create privileged containers and escape

### 🔒 Mitigation Strategies

#### 1. Use Docker Socket Proxy (Recommended for Production)

```yaml
services:
  docker-proxy:
    image: tecnativa/docker-socket-proxy
    container_name: docker-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      CONTAINERS: 1
      IMAGES: 1
      VOLUMES: 1
      NETWORKS: 0
      BUILD: 0
      COMMIT: 0
      CONFIGS: 0
      DISTRIBUTION: 0
      EXEC: 1
      GRPC: 0
      INFO: 1
      PLUGINS: 0
      POST: 1
      SECRETS: 0
      SERVICES: 0
      SWARM: 0
      SYSTEM: 0
      TASKS: 0
      VERSION: 1
    restart: unless-stopped

  mcp-server:
    # ... other config ...
    environment:
      - DOCKER_HOST=tcp://docker-proxy:2375
    depends_on:
      - docker-proxy
    # Remove /var/run/docker.sock volume
```

#### 2. Network Isolation

```yaml
services:
  mcp-server:
    networks:
      - mcp-internal
      - execution-network

networks:
  mcp-internal:
    driver: bridge
    internal: true  # No external access
  execution-network:
    driver: bridge
```

#### 3. Read-Only Filesystem

```yaml
services:
  mcp-server:
    read_only: true
    tmpfs:
      - /tmp
      - /app/data
```

#### 4. Resource Limits

```yaml
services:
  mcp-server:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

#### 5. Audit Logging

```python
# Add to DockerExecutionClient
import logging

logger = logging.getLogger(__name__)

def _get_or_create_container(self, user_id: str):
    logger.info(f"Container requested for user: {user_id}")
    # ... existing code ...
    logger.info(f"Container created: {container.id} for user: {user_id}")
```

---

## Alternative Approaches

### Option 1: Docker-in-Docker (True DinD)

**When to use:** CI/CD pipelines, complete isolation needed

```yaml
services:
  mcp-server:
    image: docker:dind
    privileged: true
    volumes:
      - docker-certs:/certs
      - ./app:/app
    environment:
      - DOCKER_TLS_CERTDIR=/certs
```

**Pros:** Isolated Docker daemon
**Cons:** Requires privileged mode, complex setup, slower

### Option 2: Remote Docker Host

**When to use:** Production with dedicated Docker hosts

```python
# Configure remote Docker
client = docker.DockerClient(base_url='tcp://remote-docker-host:2376')
```

**Pros:** Complete isolation, scalable
**Cons:** Network latency, additional infrastructure

### Option 3: Kubernetes with KinD

**When to use:** Kubernetes environments

Use Kind (Kubernetes in Docker) or similar solutions for container orchestration.

---

## Troubleshooting

### Issue: Permission denied accessing Docker socket

```bash
# Check socket permissions
ls -l /var/run/docker.sock

# Solution 1: Add user to docker group
docker exec -it mcp-server bash
sudo usermod -aG docker appuser

# Solution 2: Change socket permissions (not recommended)
sudo chmod 666 /var/run/docker.sock

# Solution 3: Run container as root
docker run --user root ...
```

### Issue: Cannot connect to Docker daemon

```bash
# Check if socket is mounted
docker exec mcp-server ls -l /var/run/docker.sock

# Check DOCKER_HOST environment variable
docker exec mcp-server env | grep DOCKER_HOST

# Test Docker access from within container
docker exec mcp-server docker ps
```

### Issue: Code executor image not found

```bash
# List images visible to container
docker exec mcp-server docker images

# Build image on host
cd mcp/docker && ./build.sh

# Verify image exists
docker images | grep mcp-code-executor
```

### Issue: Containers created but not on expected network

```bash
# Check networks
docker network ls

# Inspect container network
docker inspect <container-id> | grep NetworkMode

# Ensure tools/skills paths are accessible
docker exec mcp-server ls -la /tools
```

---

## Testing the Setup

### 1. Verify Docker Access

```bash
# Enter MCP container
docker exec -it mcp-server bash

# Test Docker command
docker ps
docker images

# Test creating a simple container
docker run --rm alpine echo "Hello from nested container"
```

### 2. Test DockerExecutionClient

```python
# In MCP server container
python3 << 'EOF'
import asyncio
from mcp.docker_client import DockerExecutionClient

async def test():
    client = DockerExecutionClient()
    code, stdout, stderr = await client.execute_bash(
        "test_user",
        "python -c 'import sys; print(sys.version)'"
    )
    print(f"Exit code: {code}")
    print(f"Output: {stdout}")
    client.cleanup_all()

asyncio.run(test())
EOF
```

### 3. Monitor Container Creation

```bash
# In separate terminal, watch containers being created
watch -n 1 'docker ps -a'

# Check logs
docker logs -f mcp-server
```

---

## Complete Example: Full Stack

```yaml
# docker-compose.full.yml
version: '3.8'

services:
  # Docker socket proxy for security
  docker-proxy:
    image: tecnativa/docker-socket-proxy
    container_name: docker-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      CONTAINERS: 1
      IMAGES: 1
      VOLUMES: 1
      EXEC: 1
      POST: 1
    networks:
      - docker-api
    restart: unless-stopped

  # MCP Server
  mcp-server:
    build:
      context: .
      dockerfile: mcp/docker/Dockerfile.server
    container_name: mcp-server
    environment:
      - DOCKER_HOST=tcp://docker-proxy:2375
      - MCP_EXECUTOR_IMAGE=mcp-code-executor:latest
      - LOG_LEVEL=INFO
    volumes:
      - ./tools:/tools:ro
      - ./skills:/skills:ro
      - mcp-data:/app/data
    ports:
      - "8000:8000"
    networks:
      - docker-api
      - frontend
    depends_on:
      - docker-proxy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  # Frontend (Gradio UI)
  frontend:
    build:
      context: ./frontend
    container_name: mcp-frontend
    ports:
      - "7860:7860"
    environment:
      - MCP_SERVER_URL=http://mcp-server:8000
    networks:
      - frontend
    depends_on:
      - mcp-server
    restart: unless-stopped

networks:
  docker-api:
    driver: bridge
    internal: true
  frontend:
    driver: bridge

volumes:
  mcp-data:
```

**Launch:**

```bash
# Build code executor image first
cd mcp/docker && ./build.sh && cd ../..

# Start all services
docker-compose -f docker-compose.full.yml up -d

# Check status
docker-compose -f docker-compose.full.yml ps

# View logs
docker-compose -f docker-compose.full.yml logs -f

# Stop all
docker-compose -f docker-compose.full.yml down
```

---

## Best Practices

1. **Always use Docker Socket Proxy in production**
2. **Set resource limits on all containers**
3. **Use read-only mounts where possible**
4. **Enable audit logging for all Docker operations**
5. **Regularly update base images**
6. **Monitor container creation and cleanup**
7. **Implement rate limiting for container creation**
8. **Use non-root users in all containers**
9. **Scan images for vulnerabilities**
10. **Have a cleanup strategy for orphaned containers**

---

## References

- [Docker-in-Docker Considerations](https://jpetazzo.github.io/2015/09/03/do-not-use-docker-in-docker-for-ci/)
- [Docker Socket Proxy](https://github.com/Tecnativa/docker-socket-proxy)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Python Docker SDK](https://docker-py.readthedocs.io/)

---

*Last Updated: 2025-11-23*
