#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

MERMAID_CODE = """flowchart TB
    subgraph Frontend["🎨 Frontend Layer"]
        UI["💬 Gradio UI<br/>━━━━━━━━━━━<br/>👤 User Authentication<br/>📡 Real-time Streaming<br/>📊 Artifact Viewer"]
    end

    subgraph AgentAPI["🤖 Agent API Layer"]
        API["⚡ OpenAI-Compatible API<br/>━━━━━━━━━━━<br/>🔥 FastAPI + Google ADK<br/>💭 Agent Reasoning Loop<br/>🌊 Streaming Responses"]
    end

    subgraph MCPServer["🔧 MCP Server Layer"]
        MCP{"🎯 FastMCP Server<br/>━━━━━━━━━━━<br/>🛠️ Tool Registry<br/>👥 User Context"}
        T1[["⚙️ execute_bash<br/>Run Commands"]]
        T2[["📖 read_file<br/>Read Files"]]
        T3[["✍️ write_file<br/>Write Files"]]
        T4[["📚 read_docstring<br/>Get Docs"]]
    end

    subgraph ExecClient["🐳 Execution Client Layer"]
        CLIENT[("🎮 DockerExecutionClient<br/>━━━━━━━━━━━<br/>📦 Container Manager<br/>⚡ Async Executor<br/>🔐 User Isolation")]
    end

    subgraph Containers["🏠 Container Isolation Layer"]
        C1{{"🐍 User Container 1<br/>━━━━━━━━━━━<br/>Python 3.12<br/>👤 Non-root User<br/>📁 /workspace"}}
        CN{{"🐍 User Container N<br/>━━━━━━━━━━━<br/>Python 3.12<br/>👤 Non-root User<br/>📁 /workspace"}}
    end

    subgraph Resources["📦 Shared Resources"]
        TOOLS[["🔨 Tools Directory<br/>🔒 Read-only"]]
        SKILLS[["✨ Skills Directory<br/>🔒 Read-only"]]
    end

    UI ==>|"📨 HTTP Requests"| API
    API ==>|"🔌 MCP Protocol"| MCP
    MCP -.->|invoke| T1
    MCP -.->|invoke| T2
    MCP -.->|invoke| T3
    MCP -.->|invoke| T4
    T1 -->|execute| CLIENT
    T2 -->|execute| CLIENT
    T3 -->|execute| CLIENT
    T4 -->|execute| CLIENT
    CLIENT ==>|"🚀 Creates & Manages"| C1
    CLIENT ==>|"🚀 Creates & Manages"| CN

    TOOLS -.-o|"📌 mount /tools"| C1
    TOOLS -.-o|"📌 mount /tools"| CN
    SKILLS -.-o|"📌 mount /skills"| C1
    SKILLS -.-o|"📌 mount /skills"| CN

    style UI fill:#e3f2fd,stroke:#1565c0,stroke-width:3px,color:#000
    style API fill:#fff3e0,stroke:#e65100,stroke-width:3px,color:#000
    style MCP fill:#f3e5f5,stroke:#6a1b9a,stroke-width:3px,color:#000
    style CLIENT fill:#e8f5e9,stroke:#2e7d32,stroke-width:3px,color:#000
    style C1 fill:#fff9c4,stroke:#f57f17,stroke-width:3px,color:#000
    style CN fill:#fff9c4,stroke:#f57f17,stroke-width:3px,color:#000
    style TOOLS fill:#ffebee,stroke:#c62828,stroke-width:3px,color:#000
    style SKILLS fill:#fce4ec,stroke:#ad1457,stroke-width:3px,color:#000
    style T1 fill:#b3e5fc,stroke:#0277bd,stroke-width:2px,color:#000
    style T2 fill:#b3e5fc,stroke:#0277bd,stroke-width:2px,color:#000
    style T3 fill:#b3e5fc,stroke:#0277bd,stroke-width:2px,color:#000
    style T4 fill:#b3e5fc,stroke:#0277bd,stroke-width:2px,color:#000

    style Frontend fill:#e8eaf6,stroke:#3f51b5,stroke-width:3px,stroke-dasharray: 5 5
    style AgentAPI fill:#fff8e1,stroke:#ff6f00,stroke-width:3px,stroke-dasharray: 5 5
    style MCPServer fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px,stroke-dasharray: 5 5
    style ExecClient fill:#e0f2f1,stroke:#00695c,stroke-width:3px,stroke-dasharray: 5 5
    style Containers fill:#fffde7,stroke:#f9a825,stroke-width:3px,stroke-dasharray: 5 5
    style Resources fill:#fce4ec,stroke:#c2185b,stroke-width:3px,stroke-dasharray: 5 5
"""


def check_mmdc_installed():
    try:
        subprocess.run(["mmdc", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_instructions():
    print("\n" + "=" * 80)
    print("ERROR: mermaid-cli (mmdc) is not installed")
    print("=" * 80)
    print("\nTo generate the diagram locally, install mermaid-cli:")
    print("\nOption 1 - Using npm (recommended):")
    print("  npm install -g @mermaid-js/mermaid-cli")
    print("\nOption 2 - Using Docker:")
    print("  docker pull minlag/mermaid-cli")
    print("\nAfter installation, run this script again.")
    print("=" * 80 + "\n")


def generate_diagram():
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    mermaid_file = docs_dir / "architecture.mmd"
    with open(mermaid_file, "w") as f:
        f.write(MERMAID_CODE)

    print(f"✓ Mermaid code written to {mermaid_file}")

    if not check_mmdc_installed():
        install_instructions()
        return False

    output_png = docs_dir / "architecture.png"
    print("\nGenerating PNG diagram...")
    try:
        subprocess.run(
            [
                "mmdc",
                "-i",
                str(mermaid_file),
                "-o",
                str(output_png),
                "-b",
                "transparent",
                "-w",
                "2000",
            ],
            check=True,
        )
        print(f"✓ PNG diagram generated: {output_png}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to generate PNG: {e}")
        return False

    output_svg = docs_dir / "architecture.svg"
    print("\nGenerating SVG diagram...")
    try:
        subprocess.run(
            [
                "mmdc",
                "-i",
                str(mermaid_file),
                "-o",
                str(output_svg),
                "-b",
                "transparent",
            ],
            check=True,
        )
        print(f"✓ SVG diagram generated: {output_svg}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to generate SVG: {e}")
        return False

    print("\n" + "=" * 80)
    print("SUCCESS! Diagram generated successfully")
    print("=" * 80)
    print("\nFiles created:")
    print(f"  - {output_png}")
    print(f"  - {output_svg}")
    print("\nAdd to README.md:")
    print("  ![Architecture Diagram](docs/architecture.png)")
    print("=" * 80 + "\n")

    return True


if __name__ == "__main__":
    success = generate_diagram()
    sys.exit(0 if success else 1)
