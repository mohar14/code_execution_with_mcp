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

# Create a workspace and artifacts directory for user files
RUN mkdir -p /workspace && \
    chown coderunner:coderunner /workspace && \
    chmod 755 /workspace && \
    mkdir -p /artifacts && \
    chown coderunner:coderunner /artifacts && \
    chmod 755 /artifacts

# Install common data analysis and statistics libraries
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    pandas==2.2.0 \
    scipy==1.12.0 \
    matplotlib==3.8.2 \
    seaborn==0.13.2 \
    scikit-learn==1.4.0 \
    statsmodels==0.14.1 \
    jupyter==1.0.0 \
    openpyxl==3.1.2 \
    requests==2.31.0 \
    plotly==5.18.0 \
    sympy==1.12

# Add /tools to PYTHONPATH so tools can be imported
ENV PYTHONPATH=/tools

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER coderunner

# Default command
CMD ["/bin/bash"]
