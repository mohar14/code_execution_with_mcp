# Docker image for secure code execution environment
# Python 3.12 with non-root user for AI agent code execution

FROM python:3.12-slim

# Install bash and other essential utilities
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for code execution
RUN useradd -m -u 1000 -s /bin/bash coderunner

# Create mount point directories for tools and skills
RUN mkdir -p /tools /skills && \
    chown root:root /tools /skills && \
    chmod 755 /tools /skills

# Create a workspace directory for user files
RUN mkdir -p /workspace && \
    chown coderunner:coderunner /workspace && \
    chmod 755 /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER coderunner

# Default command
CMD ["/bin/bash"]
