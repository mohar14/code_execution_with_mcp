#!/bin/bash

# Test script for Gradio UI startup
echo "Testing Gradio UI with auto-start services..."

# Start the Gradio app in background
uv run python gradio_ui/app.py > /tmp/gradio_test.log 2>&1 &
GRADIO_PID=$!
echo "Started Gradio app with PID: $GRADIO_PID"

# Wait for services to start
echo "Waiting for services to initialize (20 seconds)..."
sleep 20

echo ""
echo "=== Checking Running Processes ==="
ps aux | grep -E "(mcp_server|agent_api)" | grep -v grep

echo ""
echo "=== Checking MCP Server Health ==="
curl -s http://localhost:8989/health || echo "MCP Server not responding"

echo ""
echo "=== Checking Agent API Health ==="
curl -s http://localhost:8000/health || echo "Agent API not responding"

echo ""
echo "=== Gradio Startup Logs ==="
cat /tmp/gradio_test.log

echo ""
echo "=== Cleaning Up ==="
kill $GRADIO_PID 2>/dev/null
pkill -f "mcp_server.server" 2>/dev/null
pkill -f "agent_api.server" 2>/dev/null
sleep 2

echo "Test complete!"
