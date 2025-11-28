# Gradio UI Tests

This directory contains tests for the Gradio UI and its auto-start functionality.

## Test Files

### `test_startup.sh`

Tests the complete startup sequence of the Gradio UI with automatic service initialization.

**What it tests:**
- MCP Server auto-start
- Agent API auto-start
- Service health checks
- Process management
- Clean shutdown

**How to run:**
```bash
cd /Users/mohardey/Projects/code-execution-with-mcp
chmod +x tests/test_gradio_ui/test_startup.sh
./tests/test_gradio_ui/test_startup.sh
```

**Expected output:**
```
Testing Gradio UI with auto-start services...
Started Gradio app with PID: 12345
Waiting for services to initialize (20 seconds)...

=== Checking Running Processes ===
[Shows MCP server and Agent API processes]

=== Checking MCP Server Health ===
{"status":"healthy","service":"mcp-code-executor","client_initialized":true}

=== Checking Agent API Health ===
{"status":"healthy","service":"agent-api","mcp_server_connected":true,...}

=== Gradio Startup Logs ===
[Shows initialization sequence and successful startup]

=== Cleaning Up ===
[Shows clean shutdown of all services]

Test complete!
```

## Adding New Tests

To add new tests for the Gradio UI:

1. Create a new test script or Python test file in this directory
2. Follow the naming convention: `test_*.sh` or `test_*.py`
3. Ensure tests clean up after themselves (kill processes, remove temp files)
4. Update this README with test description

### Example Test Structure

```bash
#!/bin/bash

# Test description
echo "Testing [feature name]..."

# Setup
# ... start services, create test data ...

# Run test
# ... execute test steps ...

# Verify
# ... check results ...

# Cleanup
# ... stop services, remove test data ...

echo "Test complete!"
```

## Test Checklist

Before submitting new Gradio UI features, ensure:

- [ ] Services start successfully
- [ ] Health checks pass
- [ ] UI loads without errors
- [ ] Chat functionality works
- [ ] Activity monitor displays correctly
- [ ] Services shut down cleanly
- [ ] No orphaned processes remain
- [ ] Ports are released after shutdown

## Troubleshooting Tests

### Test Fails to Start Services

Check:
- Docker is running: `docker ps`
- Ports are available: `lsof -i:7860,8000,8989`
- Docker image exists: `docker images | grep code-executor`

### Test Hangs

- Services might not be starting
- Increase wait time in test script
- Check logs in `/tmp/gradio_test.log`

### Cleanup Fails

Manually clean up:
```bash
pkill -f "gradio_ui/app.py"
pkill -f "mcp_server.server"
pkill -f "agent_api.server"
```

## CI/CD Integration

To run these tests in CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Test Gradio UI Startup
  run: |
    chmod +x tests/test_gradio_ui/test_startup.sh
    ./tests/test_gradio_ui/test_startup.sh
```

Ensure Docker is available in your CI environment.

## Future Test Ideas

- [ ] End-to-end conversation test
- [ ] Tool call execution test
- [ ] Container isolation test
- [ ] Session management test
- [ ] Error handling test
- [ ] Performance/load test
- [ ] UI component rendering test
- [ ] Health check recovery test

---

For integration tests of the complete system, see the main `tests/` directory.
