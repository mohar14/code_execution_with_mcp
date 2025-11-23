#!/bin/bash
# Build script for MCP code execution Docker image

set -e  # Exit on error

# Color output for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Building MCP code execution Docker image..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build the Docker image
if docker build -t mcp-code-executor:latest "$SCRIPT_DIR"; then
    echo -e "${GREEN}✓ Docker image built successfully: mcp-code-executor:latest${NC}"
    echo ""
    echo "You can now run containers using:"
    echo "  docker run -it --rm mcp-code-executor:latest"
    exit 0
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi
